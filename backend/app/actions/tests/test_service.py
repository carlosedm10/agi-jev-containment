from __future__ import annotations

import asyncio
from dataclasses import dataclass
from itertools import pairwise

import pytest

from app.actions.journal import ActionJournal
from app.actions.models import ActionTransition, DispatchAccepted
from app.actions.service import ActionService
from app.config import Settings


@dataclass
class Request:
    level: int
    intent: str | None = "sandbox_escape"
    rationale: str | None = None


class FakePager:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str]] = []

    async def page(self, level, incident_id, intent, transition):
        self.calls.append((level, incident_id, intent))
        await transition("running")
        await transition("ok")


class FailingPager:
    async def page(self, level, incident_id, intent, transition):
        raise RuntimeError("pager unavailable")


async def finish_background_work(service: ActionService) -> None:
    while service._tasks:
        await asyncio.gather(*tuple(service._tasks))
        await asyncio.sleep(0)  # Drain done callbacks, including already-finished pager tasks.


def accepted_record(journal: ActionJournal, incident_id: str) -> DispatchAccepted:
    return next(
        record for record in journal.read(incident_id) if isinstance(record, DispatchAccepted)
    )


def transitions(journal: ActionJournal, incident_id: str) -> list[ActionTransition]:
    return [record for record in journal.read(incident_id) if isinstance(record, ActionTransition)]


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (1, []),
        (2, []),
        (3, [("tag_run", 3, "simulated", False)]),
        (
            4,
            [
                ("contain_agent", 4, "simulated", False),
                ("notify_sms", 4, "simulated", False),
            ],
        ),
        (
            5,
            [
                ("copy_forensics", 5, "simulated", False),
                ("cut_environment_egress", 5, "simulated", False),
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


async def test_l1_and_l2_accept_the_level_without_playbook_work(tmp_path):
    journal = ActionJournal(tmp_path)
    pager = FakePager()
    service = ActionService(journal, pager, simulation_delay=0)

    accepted = await service.dispatch("incident", Request(1))
    await finish_background_work(service)

    assert accepted is not None
    assert accepted.planned_actions == []
    assert transitions(journal, "incident") == []
    assert pager.calls == []
    assert service.get_state("incident").accepted_level == 1

    accepted = await service.dispatch("incident", Request(2))
    await finish_background_work(service)

    assert accepted is not None
    assert accepted.planned_actions == []
    assert transitions(journal, "incident") == []
    assert pager.calls == []
    assert service.get_state("incident").accepted_level == 2


async def test_l3_tags_and_does_not_page(tmp_path):
    journal = ActionJournal(tmp_path)
    pager = FakePager()
    service = ActionService(journal, pager, simulation_delay=0)

    await service.dispatch("incident", Request(3))
    await finish_background_work(service)

    by_name: dict[str, list[str]] = {}
    for event in transitions(journal, "incident"):
        by_name.setdefault(event.name, []).append(event.status)
    assert by_name == {"tag_run": ["queued", "running", "ok"]}
    assert pager.calls == []


async def test_l5_after_l4_still_calls_oncall(tmp_path):
    journal = ActionJournal(tmp_path)
    pager = FakePager()
    service = ActionService(journal, pager, simulation_delay=0)

    await service.dispatch("incident", Request(4))
    await finish_background_work(service)
    sms = next(
        event
        for event in transitions(journal, "incident")
        if event.name == "notify_sms" and event.status == "ok"
    )
    assert sms.detail == "Fake SMS to on-call (not sent)."
    await service.dispatch("incident", Request(5))
    await finish_background_work(service)

    assert [call[0] for call in pager.calls] == [5]
    l4 = next(
        record
        for record in journal.read("incident")
        if isinstance(record, DispatchAccepted) and record.level == 4
    )
    l5 = next(
        record
        for record in journal.read("incident")
        if isinstance(record, DispatchAccepted) and record.level == 5
    )
    assert [action.name for action in l4.planned_actions] == [
        "contain_agent",
        "notify_sms",
    ]
    assert [action.name for action in l5.planned_actions] == [
        "copy_forensics",
        "cut_environment_egress",
        "kill_agent_swarm",
        "page_oncall",
    ]


async def test_direct_l5_pages_once(tmp_path):
    pager = FakePager()
    service = ActionService(ActionJournal(tmp_path), pager, simulation_delay=0)

    await service.dispatch("incident", Request(5))
    await finish_background_work(service)

    assert [call[0] for call in pager.calls] == [5]
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
    cut_queued = next(
        event
        for event in events
        if event.name == "cut_environment_egress" and event.status == "queued"
    )
    assert events.index(copied) < events.index(cut_queued)
    assert events.index(cut_queued) < events.index(kill_queued)
    page_queued = next(
        event for event in events if event.name == "page_oncall" and event.status == "queued"
    )
    assert events.index(kill_queued) < events.index(page_queued)


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
    assert sum(isinstance(record, DispatchAccepted) for record in journal.read("incident")) == 1


async def test_pager_failure_does_not_cancel_simulated_siblings(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FailingPager(), simulation_delay=0)

    await service.dispatch("incident", Request(5))
    await finish_background_work(service)

    latest = {event.name: event for event in transitions(journal, "incident")}
    assert latest["copy_forensics"].status == "ok"
    assert latest["cut_environment_egress"].status == "ok"
    assert latest["kill_agent_swarm"].status == "ok"
    assert latest["page_oncall"].status == "failed"
    assert latest["page_oncall"].error_code == "pager_error"


async def test_dispatch_keeps_background_task_references(tmp_path):
    service = ActionService(ActionJournal(tmp_path), FakePager(), simulation_delay=0.01)

    await service.dispatch("incident", Request(3))

    assert service._tasks
    await finish_background_work(service)
    assert not service._tasks


async def test_escalations_finish_containment_before_starting_swarm_kill(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0.001)
    await service.dispatch("incident", Request(3))
    await service.dispatch("incident", Request(4))
    await service.dispatch("incident", Request(5))
    await service.wait_for_actions("incident")
    await finish_background_work(service)
    events = transitions(journal, "incident")
    steps = [
        "tag_run",
        "contain_agent",
        "copy_forensics",
        "cut_environment_egress",
        "kill_agent_swarm",
    ]
    for before, after in pairwise(steps):
        completed = next(
            i for i, event in enumerate(events) if event.name == before and event.status == "ok"
        )
        started = next(
            i for i, event in enumerate(events) if event.name == after and event.status == "running"
        )
        assert completed < started
    assert all(event.level == 5 for event in events if event.name == "kill_agent_swarm")


def test_action_step_delay_setting_defaults_to_point_three_five():
    assert Settings(_env_file=None).action_step_delay == 0.35


def test_service_default_delay_comes_from_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("app.actions.service.settings.action_step_delay", 0.17)

    service = ActionService(ActionJournal(tmp_path), FakePager())

    assert service._simulation_delay == 0.17


@pytest.mark.parametrize("level", [0, 6])
async def test_dispatch_rejects_levels_outside_playbook_range(tmp_path, level):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    with pytest.raises(ValueError, match="integer from 1 through 5"):
        await service.dispatch("incident", Request(level))

    assert journal.read("incident") == []
    assert not service._tasks
