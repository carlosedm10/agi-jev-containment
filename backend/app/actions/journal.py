from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from app.actions.models import (
    ActionRecord,
    ActionTransition,
    DispatchAccepted,
    IncidentActionState,
    RowStatus,
)

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_TERMINAL = {"ok", "partial", "failed", "canceled"}


class ActionJournal:
    def __init__(self, run_log_dir: str | Path) -> None:
        self.root = Path(run_log_dir) / "demo-actions"
        self._recovery_paths = set(self.root.glob("*.jsonl")) if self.root.exists() else set()

    def _path(self, incident_id: str) -> Path:
        slug = (_UNSAFE.sub("_", incident_id) or "_")[:80]
        digest = sha256(incident_id.encode()).hexdigest()
        return self.root / f"{slug}--{digest}.jsonl"

    def append(self, record: ActionRecord) -> None:
        path = self._path(record.incident_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.model_dump(mode="json"), separators=(",", ":"))
        with path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def read(self, incident_id: str) -> list[ActionRecord]:
        path = self._path(incident_id)
        if not path.exists():
            return []

        records: list[ActionRecord] = []
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if payload.get("kind") == "dispatch_accepted":
                    records.append(DispatchAccepted.model_validate(payload))
                elif payload.get("kind") == "action_transition":
                    records.append(ActionTransition.model_validate(payload))
                else:
                    raise ValueError(f"unknown action journal record kind: {payload.get('kind')!r}")
        return records

    def state(self, incident_id: str) -> IncidentActionState:
        records = self.read(incident_id)
        accepted = [record for record in records if isinstance(record, DispatchAccepted)]
        accepted_level = max((record.level for record in accepted), default=0)
        requested_by = next(
            (record.source for record in reversed(accepted) if record.source != "monitor"),
            "monitor",
        )
        # What the monitor wanted but held back from doing, still open for a human.
        wanted = max((record.requested_level for record in accepted), default=0)
        awaiting = wanted if wanted > accepted_level else 0
        actions = [record for record in records if isinstance(record, ActionTransition)]

        recovered = (
            self._recover_interrupted(accepted, actions)
            if self._path(incident_id) in self._recovery_paths
            else []
        )
        for transition in recovered:
            self.append(transition)
        actions.extend(recovered)

        rows: dict[int, RowStatus] = {level: "idle" for level in range(1, 6)}
        statuses_by_row: dict[int, list[str]] = defaultdict(list)
        latest_by_action: dict[str, ActionTransition] = {}
        for action in actions:
            latest_by_action[action.action_id] = action
        for action in latest_by_action.values():
            if action.ladder_level is not None:
                statuses_by_row[action.ladder_level].append(action.status)
        for level, statuses in statuses_by_row.items():
            rows[level] = self._aggregate(statuses)

        pager_actions = [
            action for action in latest_by_action.values() if action.ladder_level is None
        ]
        latest_pager = (
            max(pager_actions, key=lambda action: action.timestamp)
            if pager_actions
            else None
        )
        pager_status = latest_pager.status if latest_pager is not None else "idle"
        call_status = (
            latest_pager.call_status
            if latest_pager is not None and latest_pager.call_status is not None
            else "idle"
        )
        updated_at = max((record.timestamp for record in [*records, *recovered]), default=None)
        return IncidentActionState(
            incident_id=incident_id,
            accepted_level=accepted_level,
            rows=rows,
            actions=actions,
            pager_status=pager_status,
            call_status=call_status,
            requested_by=requested_by,
            awaiting_authorization=awaiting,
            updated_at=updated_at,
        )

    def latest(self) -> IncidentActionState | None:
        if not self.root.exists():
            return None
        candidates: list[tuple[datetime, str]] = []
        for path in self.root.glob("*.jsonl"):
            records = self._read_path(path)
            if records:
                newest = max(record.timestamp for record in records)
                candidates.append((newest, records[-1].incident_id))
        if not candidates:
            return None
        return self.state(max(candidates)[1])

    def _read_path(self, path: Path) -> list[ActionRecord]:
        records: list[ActionRecord] = []
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                payload = json.loads(line)
                model = (
                    DispatchAccepted
                    if payload.get("kind") == "dispatch_accepted"
                    else ActionTransition
                )
                records.append(model.model_validate(payload))
        return records

    @staticmethod
    def _recover_interrupted(
        accepted: Iterable[DispatchAccepted],
        actions: list[ActionTransition],
    ) -> list[ActionTransition]:
        latest = {action.action_id: action for action in actions}
        recovered: list[ActionTransition] = []
        for dispatch in accepted:
            for planned in dispatch.planned_actions:
                prior = latest.get(planned.action_id)
                if prior is not None and prior.status in _TERMINAL:
                    continue
                transition = ActionTransition(
                    incident_id=dispatch.incident_id,
                    level=dispatch.level,
                    action_id=planned.action_id,
                    name=planned.name,
                    ladder_level=planned.ladder_level,
                    mode=planned.mode,
                    status="failed",
                    source=dispatch.source,
                    detail="Backend restarted before the action completed.",
                    error_code="interrupted",
                    call_status="failed" if planned.is_pager else None,
                )
                latest[planned.action_id] = transition
                recovered.append(transition)
        return recovered

    @staticmethod
    def _aggregate(statuses: list[str]) -> RowStatus:
        if any(status in {"queued", "running"} for status in statuses):
            return "running"
        if all(status == "ok" for status in statuses):
            return "ok"
        if all(status == "failed" for status in statuses):
            return "failed"
        if len(statuses) == 1 and statuses[0] == "canceled":
            return "canceled"
        return "partial"
