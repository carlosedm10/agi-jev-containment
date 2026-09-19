from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ActionMode = Literal["simulated", "real"]
ActionStatus = Literal["queued", "running", "ok", "partial", "failed", "canceled"]
RowStatus = Literal["idle", "running", "ok", "partial", "failed", "canceled"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class PlannedAction(BaseModel):
    action_id: str
    name: str
    ladder_level: int | None = Field(default=None, ge=1, le=5)
    mode: ActionMode
    is_pager: bool


class DispatchAccepted(BaseModel):
    kind: Literal["dispatch_accepted"] = "dispatch_accepted"
    incident_id: str
    level: int = Field(ge=1, le=5)
    planned_actions: list[PlannedAction]
    timestamp: datetime = Field(default_factory=utc_now)

    @property
    def planned_action_ids(self) -> list[str]:
        return [action.action_id for action in self.planned_actions]


class ActionTransition(BaseModel):
    kind: Literal["action_transition"] = "action_transition"
    incident_id: str
    level: int = Field(ge=1, le=5)
    action_id: str
    name: str
    ladder_level: int | None = Field(default=None, ge=1, le=5)
    mode: ActionMode
    status: ActionStatus
    timestamp: datetime = Field(default_factory=utc_now)
    detail: str | None = None
    error_code: str | None = None


ActionRecord = DispatchAccepted | ActionTransition


class IncidentActionState(BaseModel):
    incident_id: str
    accepted_level: int = 0
    rows: dict[int, RowStatus]
    actions: list[ActionTransition]
    pager_status: ActionStatus | Literal["idle"] = "idle"
    updated_at: datetime | None = None
