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


def PhoneRequest(level: int):
    """A request arriving from the on-call during the call, not from the monitor."""
    request = Request(level)
    request.intent = "oncall_phone_request"
    request.source = "oncall_phone"
    return request


class FakePager:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, str]] = []

    async def page(self, level, incident_id, intent, transition, on_accepted=None):
        self.calls.append((level, incident_id, intent))
        await transition("running")
        if on_accepted is not None:
            on_accepted()
        await transition("ok")


class FailingPager:
    async def page(self, level, incident_id, intent, transition, on_accepted=None):
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
                ("copy_forensics", 4, "simulated", False),
                ("contain_agent", 4, "simulated", False),
                ("page_oncall", None, "real", True),
            ],
        ),
        (
            5,
            [
                ("copy_forensics", 4, "simulated", False),
                ("contain_agent", 4, "simulated", False),
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


async def test_monitor_holds_short_of_the_plug_and_calls_instead(tmp_path):
    """The monitor may contain one agent; pulling the environment's plug is a human call."""
    journal = ActionJournal(tmp_path)
    pager = FakePager()
    service = ActionService(journal, pager, simulation_delay=0)

    # The monitor judges the worst it can judge.
    await service.dispatch("incident", Request(5))
    await finish_background_work(service)

    state = service.get_state("incident")
    assert state.accepted_level == 4, "the monitor must not reach L5 on its own"
    assert state.awaiting_authorization == 5, "and must record what it wanted to do"
    assert [call[0] for call in pager.calls] == [4], "it calls to ask, at L4"
    # Logs are already safe and the agent is already paused before anyone picks up.
    assert {action.name for action in state.actions} == {
        "copy_forensics",
        "contain_agent",
        "page_oncall",
    }
    assert "cut_environment_egress" not in {action.name for action in state.actions}


async def test_no_answer_leaves_the_environment_contained_at_l4(tmp_path):
    """Nobody picks up: nothing further happens, by design."""
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    await service.dispatch("incident", Request(5))
    await finish_background_work(service)
    # The monitor tries again and still cannot talk itself into the cut.
    assert await service.dispatch("incident", Request(5)) is None
    await finish_background_work(service)

    state = service.get_state("incident")
    assert state.accepted_level == 4
    assert "kill_agent_swarm" not in {action.name for action in state.actions}


async def test_a_held_back_judgement_is_recorded_not_dropped(tmp_path):
    """Reaching L4 first must not swallow a later L5 judgement.

    Once the incident sits at L4 a monitor request for L5 clamps to 4 and is no
    longer an escalation. Without recording it, the fact that the cut is recommended
    and waiting on a human would disappear, and the on-call would have no signal.
    """
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FakePager(), simulation_delay=0)

    await service.dispatch("incident", Request(4))
    await finish_background_work(service)
    assert service.get_state("incident").awaiting_authorization == 0

    # The chain gets worse; the monitor judges L5 but may not act on it.
    assert await service.dispatch("incident", Request(5)) is None
    await finish_background_work(service)

    state = service.get_state("incident")
    assert state.accepted_level == 4
    assert state.awaiting_authorization == 5, "the recommendation must survive"
    assert "cut_environment_egress" not in {action.name for action in state.actions}


async def test_only_the_on_call_can_authorize_the_environment_cut(tmp_path):
    journal = ActionJournal(tmp_path)
    pager = FakePager()
    service = ActionService(journal, pager, simulation_delay=0)

    await service.dispatch("incident", Request(5))
    await finish_background_work(service)
    # The decision taken on the call.
    await service.dispatch("incident", PhoneRequest(5))
    await finish_background_work(service)

    state = service.get_state("incident")
    assert state.accepted_level == 5
    assert state.requested_by == "oncall_phone"
    assert state.awaiting_authorization == 0
    assert {action.name for action in state.actions} == {
        "copy_forensics",
        "contain_agent",
        "page_oncall",
        "cut_environment_egress",
        "kill_agent_swarm",
    }
    # One incident, one call: authorizing does not ring the phone again.
    assert [call[0] for call in pager.calls] == [4]

    events = transitions(journal, "incident")
    names = [event.name for event in events if event.status == "queued"]
    # Forensics are preserved before the agent is paused, and long before the cut.
    assert names.index("copy_forensics") < names.index("contain_agent")
    assert names.index("contain_agent") < names.index("cut_environment_egress")
    assert names.index("cut_environment_egress") < names.index("kill_agent_swarm")
    # The step the human authorized is attributable to them.
    by_source = {event.name: event.source for event in events}
    assert by_source["contain_agent"] == "monitor"
    assert by_source["cut_environment_egress"] == "oncall_phone"


async def test_pager_failure_does_not_cancel_simulated_siblings(tmp_path):
    journal = ActionJournal(tmp_path)
    service = ActionService(journal, FailingPager(), simulation_delay=0)

    await service.dispatch("incident", Request(5))
    await finish_background_work(service)

    latest = {event.name: event for event in transitions(journal, "incident")}
    # A dead pager must not cost us the logs or leave the agent running.
    assert latest["copy_forensics"].status == "ok"
    assert latest["contain_agent"].status == "ok"
    assert latest["page_oncall"].status == "failed"
    assert latest["page_oncall"].error_code == "pager_error"
    # And it must not cut the environment on its own: nobody authorized that.
    assert "cut_environment_egress" not in latest


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
    await service.wait_for_actions("incident")
    await finish_background_work(service)
    # The monitor stops here; the cut needs the decision taken on the call.
    await service.dispatch("incident", PhoneRequest(5))
    await service.wait_for_actions("incident")
    await finish_background_work(service)
    events = transitions(journal, "incident")
    steps = [
        "tag_run",
        "copy_forensics",
        "contain_agent",
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
