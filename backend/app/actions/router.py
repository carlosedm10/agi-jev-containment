from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, StrictInt

from app.actions.journal import ActionJournal
from app.actions.models import IncidentActionState
from app.actions.pager import HappyRobotPager
from app.actions.service import ActionService
from app.config import settings

router = APIRouter()


class DispatchRequest(BaseModel):
    level: StrictInt = Field(ge=1, le=5)
    intent: str | None = None
    rationale: str | None = None


class DispatchResponse(BaseModel):
    accepted: bool
    state: IncidentActionState


@lru_cache
def get_action_service() -> ActionService:
    pager = HappyRobotPager(
        hook_url=settings.happyrobot_hook_url,
        api_key=settings.happyrobot_api_key,
        api_base=settings.happyrobot_api_base or None,
        phone=settings.oncall_phone,
        name=settings.oncall_name,
        poll_interval=settings.happyrobot_poll_interval,
        poll_timeout=settings.happyrobot_poll_timeout,
    )
    return ActionService(
        ActionJournal(settings.run_log_dir),
        pager,
        simulation_delay=settings.action_step_delay,
    )


def require_dispatch_token(
    dispatch_token: str | None = Header(default=None, alias="X-Dispatch-Token"),
) -> None:
    configured_token = settings.action_dispatch_token
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Action dispatch is not configured.",
        )
    if dispatch_token is None or not secrets.compare_digest(
        dispatch_token.encode(), configured_token.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dispatch token.",
        )


ActionServiceDependency = Annotated[ActionService, Depends(get_action_service)]


@router.post(
    "/incidents/{incident_id}/dispatch",
    response_model=DispatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_200_OK: {
            "model": DispatchResponse,
            "description": "Duplicate or lower-level dispatch; no new work accepted.",
        }
    },
    dependencies=[Depends(require_dispatch_token)],
)
async def dispatch_incident(
    incident_id: str,
    request: DispatchRequest,
    response: Response,
    service: ActionServiceDependency,
) -> DispatchResponse:
    accepted = await service.dispatch(incident_id, request)
    was_accepted = accepted is not None
    response.status_code = (
        status.HTTP_202_ACCEPTED if was_accepted else status.HTTP_200_OK
    )
    return DispatchResponse(
        accepted=was_accepted,
        state=service.get_state(incident_id),
    )


@router.get("/incidents/latest", response_model=IncidentActionState)
def get_latest_incident(service: ActionServiceDependency) -> IncidentActionState:
    state = service.latest_state()
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No demo incidents found.",
        )
    return state


@router.get("/incidents/{incident_id}", response_model=IncidentActionState)
def get_incident(
    incident_id: str,
    service: ActionServiceDependency,
) -> IncidentActionState:
    return service.get_state(incident_id)
