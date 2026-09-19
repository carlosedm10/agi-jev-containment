from __future__ import annotations

from typing import Any

import httpx

from app.actions.models import DispatchAccepted
from app.classification import pipeline
from app.graph import graph
from app.runs import log

client_factory = httpx.AsyncClient


async def ingest(
    run_id: str, event: dict[str, Any], client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    log.append(run_id, event)
    owned = client is None
    if client is None:
        client = client_factory()
    try:
        before_level = graph.level(run_id)
        before_nodes = len(graph.run_nodes(run_id))
        verdict = await pipeline.evaluate(client, run_id, event)
    finally:
        if owned:
            await client.aclose()
    nodes = graph.run_nodes(run_id)
    node_id = nodes[-1].id if len(nodes) > before_nodes else None
    if node_id is not None and not verdict.degraded and int(verdict.level) >= 1:
        accepted = await dispatch_classified(
            run_id, int(verdict.level), verdict.intent
        )
        if accepted is not None:
            graph.update(node_id, action_id=accepted.planned_actions[0].action_id)
    return {
        "level": int(verdict.level),
        "confidence": verdict.confidence,
        "intent": verdict.intent,
        "escalated": int(verdict.level) > int(before_level),
        "degraded": verdict.degraded,
        "node_id": node_id,
    }


async def dispatch_classified(
    run_id: str, level: int, intent: str | None
) -> DispatchAccepted | None:
    from app.actions.router import DispatchRequest, get_action_service

    return await get_action_service().dispatch(
        run_id,
        DispatchRequest(level=level, intent=intent),
    )
