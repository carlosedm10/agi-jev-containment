from __future__ import annotations

import asyncio
import random
import secrets
import uuid
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.actions.journal import ActionJournal
from app.actions.models import DispatchSource, IncidentActionState
from app.actions.pager import HappyRobotPager
from app.actions.service import ActionService
from app.config import settings
from app.evals import trace_generator
from app.evals.demo_chains import CHAINS, build_chain, chain_levels
from app.runs import service as runs_service

router = APIRouter()


# What the voice workflow's tool sends instead of a number. Keeping the mapping here
# means the spoken vocabulary can grow without the workflow and the API drifting apart.
ACTIONS = {
    "marcar_conversacion": 3,
    "etiquetar_run": 3,
    "pausar_agente": 4,
    "contener_agente": 4,
    "cortar_internet": 5,
    "cortar_acceso": 5,
    "cortar_egress": 5,
    "apagar_todo": 5,
    "apagar_sistema": 5,
    "apagar_agentes": 5,
}


class DispatchRequest(BaseModel):
    # Either a level or a named action. The tool sends `accion`; the monitor sends
    # `level`. Requiring `level` alone made every spoken request fail validation.
    level: int = Field(default=0, ge=0, le=5)
    accion: str | None = None

    @model_validator(mode="after")
    def resolve_level(self) -> DispatchRequest:
        if not self.level and self.accion:
            mapped = ACTIONS.get(self.accion.strip().lower().replace(" ", "_"))
            if mapped is None:
                raise ValueError(
                    f"unknown accion {self.accion!r}; expected one of {sorted(ACTIONS)}"
                )
            self.level = mapped
        if not 1 <= self.level <= 5:
            raise ValueError("provide a level from 1 through 5, or a known accion")
        return self
    intent: str | None = None
    rationale: str | None = None
    # Defaults to the monitor so the in-process path, which builds this directly, can
    # never talk itself past MONITOR_CEILING by omission. The HTTP handler raises it
    # to the on-call, because that endpoint is only reachable from outside.
    source: DispatchSource = "monitor"


# Read aloud by the voice agent, so it must be a sentence and it must be true.
DONE_MESSAGES = {
    3: "Hecho. La conversación queda marcada para revisión.",
    4: "Hecho. El agente está pausado y sus registros guardados.",
    5: "Hecho. El acceso a internet está cortado y los agentes apagados.",
}


class DispatchResponse(BaseModel):
    accepted: bool
    # Whether the state the caller asked for is now in effect. An action that was
    # already carried out is a success for whoever asked: reporting it as "accepted:
    # false" made the agent tell the on-call it had failed when it had not.
    done: bool = False
    message: str = ""
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
    # The monitor never comes through HTTP — it calls the service in process. So an
    # authenticated request on this endpoint is a human decision, and is what lifts an
    # incident past MONITOR_CEILING. A caller that wants monitor semantics says so.
    if "source" not in request.model_fields_set:
        request.source = "oncall_phone"
    accepted = await service.dispatch(incident_id, request)
    was_accepted = accepted is not None
    state = service.get_state(incident_id)
    # The ladder bundles steps, and the caller may ask for one that a previous
    # request already carried out. That is done, not refused.
    done = state.accepted_level >= request.level
    response.status_code = status.HTTP_202_ACCEPTED if done else status.HTTP_200_OK
    return DispatchResponse(
        accepted=was_accepted,
        done=done,
        message=(
            DONE_MESSAGES.get(request.level, "Hecho.")
            if done
            else "No se ha podido aplicar. Queda anotado para el equipo."
        ),
        state=state,
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

# The one chain that pulls the plug, and the run numbers that use it.
L5_SCENARIO = "lateral_db"
_run_count = 0


def _next_scenario() -> str:
    """Draw the next chain.

    Every second run — run 2, 4, 6, and so on — is the L5 chain, so the demo reaches
    the full ladder and calls the on-call on a fixed cadence rather than whenever a
    shuffle happens to land there. Odd runs cycle through the other three.
    """
    global _run_count, _previous_scenario
    _run_count += 1
    if _run_count % 2 == 0:
        _previous_scenario = L5_SCENARIO
        return L5_SCENARIO
    if not _scenario_bag:
        others = [key for key in CHAINS if key != L5_SCENARIO]
        random.shuffle(others)
        _scenario_bag.extend(others)
    scenario = _scenario_bag.pop(0)
    _previous_scenario = scenario
    return scenario


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
    scenario = body.scenario if body.scenario is not None else _next_scenario()
    if scenario not in CHAINS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario}")

    run_id = f"trigger-{uuid.uuid4().hex[:8]}"
    events = build_chain(run_id, scenario)

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
