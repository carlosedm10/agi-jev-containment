from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.actions.journal import ActionJournal
from app.actions.models import ActionTransition, DispatchAccepted


def accepted(
    incident_id: str,
    level: int,
    action_ids: list[str],
    *,
    timestamp: datetime | None = None,
) -> DispatchAccepted:
    return DispatchAccepted(
        incident_id=incident_id,
        level=level,
        planned_action_ids=action_ids,
        timestamp=timestamp or datetime.now(UTC),
    )


def transition(
    incident_id: str,
    action_id: str,
    status: str,
    *,
    level: int = 1,
    ladder_level: int | None = 1,
    timestamp: datetime | None = None,
) -> ActionTransition:
    return ActionTransition(
        incident_id=incident_id,
        level=level,
        action_id=action_id,
        name=action_id,
        ladder_level=ladder_level,
        mode="real" if ladder_level is None else "simulated",
        status=status,
        timestamp=timestamp or datetime.now(UTC),
    )


def test_sanitizes_incident_path_and_writes_jsonl(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("../../incident one", 1, ["tag"]))

    files = list((tmp_path / "demo-actions").iterdir())
    assert [path.name for path in files] == [".._.._incident_one.jsonl"]
    assert json.loads(files[0].read_text())["kind"] == "dispatch_accepted"


def test_incidents_use_independent_files_and_reads(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("alpha", 1, ["tag"]))
    journal.append(accepted("beta", 2, ["supervisor"]))

    assert [record.incident_id for record in journal.read("alpha")] == ["alpha"]
    assert [record.incident_id for record in journal.read("beta")] == ["beta"]


def test_state_replays_highest_accepted_level(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("incident", 2, []))
    journal.append(accepted("incident", 4, []))
    journal.append(accepted("incident", 3, []))

    assert journal.state("incident").accepted_level == 4


def test_state_recovers_planned_action_without_transition(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("incident", 1, ["incident:tag"]))

    state = ActionJournal(tmp_path).state("incident")

    recovered = state.actions[-1]
    assert recovered.action_id == "incident:tag"
    assert recovered.status == "failed"
    assert recovered.error_code == "interrupted"
    assert journal.read("incident")[-1] == recovered


def test_state_does_not_interrupt_work_accepted_by_current_process(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("incident", 1, ["incident:tag"]))

    assert journal.state("incident").actions == []


def test_rows_aggregate_action_statuses_with_required_precedence(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("incident", 5, []))
    cases = {
        1: [("a", "ok"), ("b", "ok")],
        2: [("a", "failed"), ("b", "failed")],
        3: [("a", "ok"), ("b", "failed")],
        4: [("a", "canceled")],
        5: [("a", "ok"), ("b", "queued")],
    }
    for ladder_level, statuses in cases.items():
        for suffix, status in statuses:
            journal.append(
                transition(
                    "incident",
                    f"incident:{ladder_level}:{suffix}",
                    status,
                    level=5,
                    ladder_level=ladder_level,
                )
            )

    assert journal.state("incident").rows == {
        1: "ok",
        2: "failed",
        3: "partial",
        4: "canceled",
        5: "running",
    }


def test_pager_action_does_not_change_ladder_rows(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(accepted("incident", 4, []))
    journal.append(
        transition(
            "incident",
            "incident:pager:l4",
            "running",
            level=4,
            ladder_level=None,
        )
    )

    state = journal.state("incident")
    assert state.rows == {1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle"}
    assert state.pager_status == "running"


def test_latest_selects_most_recently_updated_incident(tmp_path):
    journal = ActionJournal(tmp_path)
    now = datetime.now(UTC)
    journal.append(accepted("newer-file", 1, [], timestamp=now))
    journal.append(accepted("latest-event", 2, [], timestamp=now + timedelta(seconds=1)))
    journal.append(
        transition(
            "newer-file",
            "newer-file:tag",
            "ok",
            timestamp=now - timedelta(seconds=1),
        )
    )

    assert journal.latest().incident_id == "latest-event"


def test_latest_returns_none_without_incidents(tmp_path):
    assert ActionJournal(tmp_path).latest() is None
