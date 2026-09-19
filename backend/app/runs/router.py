from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Query

from app.graph import graph
from app.graph.neo4j import neo4j_graph
from app.runs import log, service
from app.runs.explanations import explain
from app.runs.schemas import EventIn, GraphOut, IngestOut, NodeOut, RunOut, RunSummary

router = APIRouter()


@router.get("/logs/recent")
def recent_logs(limit: int = Query(default=500, ge=1, le=2000)) -> list[dict]:
    """Independent all-run tape feed; repeated visits remain separate log entries."""
    levels = {}
    for node in graph.nodes:
        for run_id, state in list(node.run_states.items()):
            event = state.get("event") or {}
            levels[(run_id, event.get("id"))] = state["level"]
    return [
        {**event, "level": levels.get((event["run_id"], event["id"]))}
        for event in log.recent_events(limit)
    ]


@router.post("/{run_id}/events", response_model=IngestOut)
async def post_event(run_id: str, event: EventIn) -> IngestOut:
    return IngestOut(**await service.ingest(run_id, event.model_dump()))


@router.post("/{run_id}/preflight", response_model=IngestOut)
async def preflight_event(run_id: str, event: EventIn) -> IngestOut:
    return IngestOut(**await service.preflight(run_id, event.model_dump()))


@router.get("/{run_id}/timeline")
async def get_timeline(run_id: str) -> list[dict]:
    return await neo4j_graph.timeline(run_id)


@router.get("/{run_id}/trace")
async def get_trace(run_id: str) -> dict:
    """Ordered event occurrences, never collapsed by action signature."""
    tape = log.tail(run_id, log.count(run_id))
    warning = None
    try:
        persisted = await neo4j_graph.timeline(run_id)
    except Exception:  # noqa: BLE001 - the tape remains usable during a graph outage
        persisted = []
        warning = "Stored assessments unavailable; showing recorded events."
    events = {
        row["event"]["id"]: row["event"]
        for row in persisted
        if row.get("event", {}).get("id") and not row["event"].get("placeholder")
    }
    events.update({event["id"]: event for event in tape if event.get("id")})
    levels = {
        node.event["id"]: int(node.level)
        for node in graph.run_nodes(run_id)
        if node.event and node.event.get("id")
    }
    for row in persisted:
        assessment = row.get("assessment") or {}
        gate = json.loads(assessment.get("gate_json") or "{}")
        if gate.get("incident_level") is not None:
            levels[row["event"]["id"]] = gate["incident_level"]
    ordered = sorted(
        events.values(),
        key=lambda event: (
            event.get("sequence") or 0,
            event.get("timestamp") or "",
            event["id"],
        ),
    )
    return {
        "run_id": run_id,
        "warning": warning,
        "events": [
            {
                **{
                    key: event.get(key)
                    for key in (
                        "id",
                        "sequence",
                        "timestamp",
                        "kind",
                        "phase",
                        "tool",
                        "target",
                        "agent",
                        "channel",
                        "content",
                    )
                },
                "level": levels.get(event["id"]),
            }
            for event in ordered
        ],
    }


@router.get("/{run_id}/graph", response_model=GraphOut)
async def get_graph(run_id: str) -> GraphOut:
    return GraphOut(**await neo4j_graph.graph(run_id))


@router.post("/{run_id}/trace/explanations")
async def trace_explanations(run_id: str) -> dict:
    trace = await get_trace(run_id)
    async with httpx.AsyncClient() as client:
        return await explain(trace["events"], client)


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str) -> RunOut:
    return RunOut(
        run_id=run_id,
        level=int(graph.level(run_id)),
        key_nodes=[
            NodeOut(
                id=node.id,
                level=int(node.level),
                threshold=node.threshold,
                intent=node.intent,
                action_id=node.action_id,
            )
            for node in graph.key_nodes(run_id)
        ],
    )


@router.get("/", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    return [
        RunSummary(
            run_id=run_id,
            level=int(graph.level(run_id)),
            nodes=len(graph.key_nodes(run_id)),
        )
        for run_id in log.list_runs()
    ]
