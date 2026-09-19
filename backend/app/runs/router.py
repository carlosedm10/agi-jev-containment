from __future__ import annotations

from fastapi import APIRouter

from app.graph import graph
from app.runs import log, service
from app.runs.schemas import EventIn, IngestOut, NodeOut, RunOut, RunSummary

router = APIRouter()


@router.post("/{run_id}/events", response_model=IngestOut)
async def post_event(run_id: str, event: EventIn) -> IngestOut:
    return IngestOut(**await service.ingest(run_id, event.model_dump()))


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
