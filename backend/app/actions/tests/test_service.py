from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.actions.journal import ActionJournal
from app.actions.models import ActionTransition, DispatchAccepted
from app.actions.service import ActionService


@dataclass
class Request:
    level: int
    intent: str | None = "sandbox_escape"
    rationale: str | None = None


class FakePager:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str, str]] = []

    async def page(self, level, incident_id, intent, action_taken, transition):
        self.calls.append((level, incident_id, intent, action_taken))
        await transition("running")
        await transition("ok")


class FailingPager:
    async def page(self, level, incident_id, intent, action_taken, transition):
        raise RuntimeError("pager unavailable")


async def finish_background_work(service: ActionService) -> None:
    while service._tasks:
        await asyncio.gather(*tuple(service._tasks))


def accepted_record(journal: ActionJournal, incident_id: str) -> DispatchAccepted:
    return next(
        record
        for record in journal.read(incident_id)
        if isinstance(record, DispatchAccepted)
    )


def transitions(journal: ActionJournal, incident_id: str) -> list[ActionTransition]:
    return [
        record
        for record in journal.read(incident_id)
        if isinstance(record, ActionTransition)
    ]


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (1, [("tag_run", 1, "simulated", False)]),
        (
            2,
            [
                ("tag_run", 1, "simulated", False),
                ("supervise_run", 2, "simulated", False),
            ],
        ),
        (3, [("contain_agent", 3, "simulated", False)]),
        (
            4,
            [
                ("contain_all_runs", 3, "simulated", False),
                ("cut_environment_egress", 4, "simulated", False),
                ("page_oncall", None, "real", True),
            ],
        ),
        (
            5,
            [
                ("copy_forensics", 5, "simulated", False),
                ("kill_agent_swarm", 5, "simulated", False),
                ("page_oncall", None, "real", True),
            ],
        ),
    ],
)
async def test_dispatches_exact_level_plan_with_mode_labels(tmp_path, level, expected):
    journal = ActionJournal(tmp_path)
    pager = FakePager()
    service = ActionService(journal, pager, simulation_delay=0)

    accepted = await service.dispatch(f"incident-{level}", Request(level))
    await finish_background_work(service)

    assert accepted is not None
    assert [
        (action.name, action.ladder_level, action.mode, action.is_pager)
        for action in accepted_record(journal, f"incident-{level}").planned_actions
    ] == expected
    assert all(
        transition.mode == ("real" if transition.ladder_level is None else "simulated")
        for transition in transitions(journal, f"incident-{level}")
    )


async def test_simulation_transitions_and_persistent_supervision(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    await service.dispatch("incident", Request(2))
    await finish_background_work(service)

    by_name: dict[str, list[str]] = {}
    for event in transitions(journal, "incident"):
        by_name.setdefault(event.name, []).append(event.status)
    assert by_name == {
        "tag_run": ["queued", "running", "ok"],
        "supervise_run": ["queued", "running"],
    }


async def test_l3_cancels_running_supervision_before_containment(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)
    await service.dispatch("incident", Request(2))
    await finish_background_work(service)

    await service.dispatch("incident", Request(3))
    await finish_background_work(service)

    events = transitions(journal, "incident")
    canceled = next(event for event in events if event.status == "canceled")
    containment_queued = next(
        event for event in events if event.name == "contain_agent" and event.status == "queued"
    )
    assert canceled.name == "supervise_run"
    assert events.index(canceled) < events.index(containment_queued)
    assert service.get_state("incident").rows[2] == "canceled"


async def test_l5_copies_forensics_before_killing_swarm(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    await service.dispatch("incident", Request(5))
    await finish_background_work(service)

    events = transitions(journal, "incident")
    copied = next(
        event for event in events if event.name == "copy_forensics" and event.status == "ok"
    )
    kill_queued = next(
        event for event in events if event.name == "kill_agent_swarm" and event.status == "queued"
    )
    assert events.index(copied) < events.index(kill_queued)


async def test_levels_only_escalate_and_duplicates_are_noops(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    assert await service.dispatch("incident", Request(3)) is not None
    await finish_background_work(service)
    records_after_first = journal.read("incident")

    assert await service.dispatch("incident", Request(3)) is None
    assert await service.dispatch("incident", Request(2)) is None

    assert journal.read("incident") == records_after_first
    assert service.get_state("incident").accepted_level == 3
    assert service.latest_state().incident_id == "incident"


async def test_concurrent_duplicate_dispatch_writes_one_acceptance(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    results = await asyncio.gather(
        service.dispatch("incident", Request(4)),
        service.dispatch("incident", Request(4)),
    )
    await finish_background_work(service)

    assert sum(result is not None for result in results) == 1
    assert (
        sum(
            isinstance(record, DispatchAccepted)
            for record in journal.read("incident")
        )
        == 1
    )


async def test_pager_failure_does_not_cancel_simulated_siblings(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FailingPager(), simulation_delay=0)

    await service.dispatch("incident", Request(4))
    await finish_background_work(service)

    latest = {
        event.name: event
        for event in transitions(journal, "incident")
    }
    assert latest["contain_all_runs"].status == "ok"
    assert latest["cut_environment_egress"].status == "ok"
    assert latest["page_oncall"].status == "failed"
    assert latest["page_oncall"].error_code == "pager_error"


async def test_dispatch_keeps_background_task_references(tmp_path):
    service = ActionService(ActionJournal(tmp_path), FakePager(), simulation_delay=0.01)

    await service.dispatch("incident", Request(1))

    assert service._tasks
    await finish_background_work(service)
    assert not service._tasks
