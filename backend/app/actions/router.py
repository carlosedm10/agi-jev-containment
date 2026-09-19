from __future__ import annotations

import asyncio
import random
import secrets
import uuid
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.actions.journal import ActionJournal
from app.actions.models import IncidentActionState
from app.actions.pager import HappyRobotPager
from app.actions.service import ActionService
from app.config import settings
from app.evals import trace_generator
from app.evals.demo_chains import CHAINS, build_chain, chain_levels
from app.runs import service as runs_service

router = APIRouter()


class DispatchRequest(BaseModel):
    level: int = Field(ge=1, le=5)
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
    response.status_code = status.HTTP_202_ACCEPTED if was_accepted else status.HTTP_200_OK
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


class TriggerRequest(BaseModel):
    scenario: str | None = Field(default=None)
    delay_ms: int = Field(default=400, ge=0, le=10_000)


class TriggerResponse(BaseModel):
    run_id: str
    scenario: str | None
    event_count: int


@router.get("/scenarios")
def scenarios() -> list[dict]:
    return [
        {
            "id": key,
            "title": title,
            "steps": [step["content"] for step in steps],
            "levels": chain_levels(key),
            "simulation": True,
        }
        for key, (title, steps) in CHAINS.items()
    ]


# ponytail: process-local demo controls; use a shared job store for multiple API workers.
_trigger_stops: dict[str, asyncio.Event] = {}
_scenario_bag: list[str] = []
_previous_scenario: str | None = None


@router.get("/trigger/{run_id}")
async def trigger_status(run_id: str) -> dict[str, bool]:
    return {"active": run_id in _trigger_stops}


@router.post("/trigger/{run_id}/stop")
async def stop_trigger(run_id: str) -> dict[str, bool]:
    stop = _trigger_stops.get(run_id)
    if stop is not None:
        stop.set()
    return {"active": stop is not None}


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_run(
    body: TriggerRequest,
    background: BackgroundTasks,
) -> TriggerResponse:
    global _previous_scenario
    scenario = body.scenario
    if scenario is None:
        if not _scenario_bag:
            _scenario_bag.extend(CHAINS)
            random.shuffle(_scenario_bag)
            if _scenario_bag[-1] == _previous_scenario:
                _scenario_bag[0], _scenario_bag[-1] = _scenario_bag[-1], _scenario_bag[0]
        scenario = _scenario_bag.pop()
    if scenario not in CHAINS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario}")

    run_id = f"trigger-{uuid.uuid4().hex[:8]}"
    events = build_chain(run_id, scenario)
    _previous_scenario = scenario

    stop = asyncio.Event()
    _trigger_stops[run_id] = stop

    async def _ingest() -> None:
        try:
            async with httpx.AsyncClient() as client:
                for event, level in zip(events, chain_levels(scenario), strict=True):
                    if stop.is_set():
                        break
                    trace_generator.normalize_event_payload(event)
                    await runs_service.ingest(run_id, event, client, demo_level=level)
                    await get_action_service().wait_for_actions(run_id)
                    if body.delay_ms:
                        try:
                            await asyncio.wait_for(stop.wait(), body.delay_ms / 1000)
                        except TimeoutError:
                            pass
        finally:
            _trigger_stops.pop(run_id, None)

    background.add_task(_ingest)
    return TriggerResponse(
        run_id=run_id,
        scenario=scenario,
        event_count=len(events),
    )
