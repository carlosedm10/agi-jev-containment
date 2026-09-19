from __future__ import annotations

import threading
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.classification.models import Level
from app.events import EventPhase, MonitorEvent
from app.monitor.models import MonitorAssessment
from app.monitor.policy import DEFAULT_POLICY


class DispatchAction(BaseModel):
    id: str
    run_id: str
    kind: str
    state: str = "recorded"
    counter_template: str | None = None
    source_event_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Dispatcher:
    """Idempotent mapping from incident transitions to prewritten responses."""

    def __init__(self) -> None:
        self._actions: dict[str, DispatchAction] = {}
        self._armed: dict[str, list[DispatchAction]] = {}
        self._lock = threading.RLock()

    def clear(self) -> None:
        with self._lock:
            self._actions.clear()
            self._armed.clear()

    def arm_counter(self, event: MonitorEvent) -> DispatchAction | None:
        if event.phase not in {EventPhase.REQUESTED, EventPhase.COMPLETED} or not event.tool:
            return None
        policy = DEFAULT_POLICY.tools.get(event.tool)
        if policy is None or policy.counter_action is None:
            return None
        action = DispatchAction(
            id=f"counter:{event.id}",
            run_id=event.run_id,
            kind="counter_action",
            state="armed" if event.phase == EventPhase.COMPLETED else "pending",
            counter_template=policy.counter_action,
            source_event_id=event.id,
        )
        with self._lock:
            existing = self._actions.get(action.id)
            if existing is not None:
                return existing
            self._actions[action.id] = action
            self._armed.setdefault(event.run_id, []).append(action)
        return action

    def handle(
        self,
        event: MonitorEvent,
        assessment: MonitorAssessment,
    ) -> list[DispatchAction]:
        self.arm_counter(event)
        level = assessment.gate.incident_level
        kinds = _playbook(level)
        created: list[DispatchAction] = []
        with self._lock:
            for kind in kinds:
                action_id = f"{kind}:{event.run_id}:L{int(level)}"
                if action_id in self._actions:
                    continue
                action = DispatchAction(
                    id=action_id,
                    run_id=event.run_id,
                    kind=kind,
                    source_event_id=event.id,
                )
                self._actions[action_id] = action
                created.append(action)

            if level >= Level.SEVERE:
                for counter in reversed(self._armed.get(event.run_id, [])):
                    if counter.state == "armed":
                        counter.state = "executed"
                        created.append(counter)
        return created

    def actions(self, run_id: str) -> list[DispatchAction]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._actions.values() if item.run_id == run_id]


def _playbook(level: Level) -> list[str]:
    if level == Level.MILD:
        return ["tag_run"]
    if level == Level.MODERATE:
        return ["tag_run", "start_supervisor"]
    if level == Level.SEVERE:
        return ["contain_run", "revoke_token"]
    if level == Level.CRITICAL:
        return ["contain_all_runs", "cut_egress", "page_oncall"]
    if level == Level.CATASTROPHIC:
        return ["snapshot_forensics", "kill_swarm", "page_oncall"]
    return []


dispatcher = Dispatcher()
