from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.actions.call_status import CallStatus
from app.actions.types import ActionStatus

ActionMode = Literal["simulated", "real"]
RowStatus = Literal["idle", "running", "ok", "partial", "failed", "canceled"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class PlannedAction(BaseModel):
    action_id: str
    name: str
    ladder_level: int | None = Field(default=None, ge=1, le=5)
    mode: ActionMode
    is_pager: bool

    @model_validator(mode="after")
    def validate_pager_classification(self) -> Self:
        if self.is_pager != (self.ladder_level is None):
            raise ValueError(
                "pager actions require no ladder level; ladder actions require a ladder level"
            )
        return self


class DispatchAccepted(BaseModel):
    kind: Literal["dispatch_accepted"] = "dispatch_accepted"
    incident_id: str
    level: int = Field(ge=1, le=5)
    planned_actions: list[PlannedAction]
    timestamp: datetime = Field(default_factory=utc_now)


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
    call_status: CallStatus | None = None


ActionRecord = DispatchAccepted | ActionTransition


class IncidentActionState(BaseModel):
    incident_id: str
    accepted_level: int = 0
    rows: dict[int, RowStatus]
    actions: list[ActionTransition]
    pager_status: ActionStatus | Literal["idle"] = "idle"
    call_status: CallStatus = "idle"
    updated_at: datetime | None = None
