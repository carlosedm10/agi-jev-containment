from __future__ import annotations

from typing import Any
import logging

import httpx

from app.classification import pipeline
from app.dispatch import dispatcher
from app.classification.models import Level
from app.events import EventPhase, normalize_event, redact_event
from app.graph import graph
from app.graph.neo4j import neo4j_graph
from app.monitor import monitor
from app.realtime import broker, build_envelopes
from app.runs import log

client_factory = httpx.AsyncClient
logger = logging.getLogger(__name__)


async def ingest(
    run_id: str, event: dict[str, Any], client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    normalized = redact_event(normalize_event(run_id, event))
    normalized, is_new = log.append_event(normalized)
    normalized_payload = normalized.model_dump(mode="json")
    if not is_new:
        return {
            "level": int(graph.level(run_id)),
            "confidence": 0.0,
            "intent": None,
            "escalated": False,
            "degraded": False,
            "node_id": None,
            "event_id": normalized.id,
            "decision": "allow",
            "event_risk": 0.0,
            "trajectory_risk": 0.0,
            "reasons": ["duplicate_event"],
            "graph_persisted": True,
            "dispatch_actions": [],
            "jev_latency_ms": None,
            "duplicate": True,
        }
    owned = client is None
    if client is None:
        client = client_factory()
    prepared = monitor.prepare(normalized)
    try:
        before_level = graph.level(run_id)
        before_nodes = len(graph.run_nodes(run_id))
        verdict = await pipeline.evaluate(
            client,
            run_id,
            normalized_payload,
            monitor_context=prepared.context,
        )
    finally:
        if owned:
            await client.aclose()
    nodes = graph.run_nodes(run_id)
    assessment = monitor.finalize(normalized, verdict, before_level, prepared)
    actions = dispatcher.handle(normalized, assessment)
    assessment.dispatch_actions = [action.model_dump(mode="json") for action in actions]
    node_id = nodes[-1].id if len(nodes) > before_nodes else None
    if node_id and assessment.gate.incident_level > graph.get_node(node_id).level:
        graph.update(node_id, level=assessment.gate.incident_level)

    graph_persisted = True
    try:
        await neo4j_graph.persist(normalized, assessment)
    except Exception:  # noqa: BLE001
        graph_persisted = False
        logger.exception("Neo4j persistence failed for event %s", normalized.id)

    effective_level = max(before_level, verdict.level, assessment.gate.incident_level)
    history = monitor.history(run_id)
    previous_event_id = history[-2].id if len(history) >= 2 else None
    await broker.publish(build_envelopes(normalized, assessment, previous_event_id))
    return {
        "level": int(effective_level),
        "confidence": verdict.confidence,
        "intent": verdict.intent,
        "escalated": effective_level > before_level,
        "degraded": verdict.degraded,
        "node_id": node_id,
        "event_id": normalized.id,
        "decision": assessment.gate.decision.value,
        "event_risk": assessment.gate.event_risk,
        "trajectory_risk": assessment.gate.trajectory_risk,
        "reasons": assessment.gate.reasons,
        "graph_persisted": graph_persisted,
        "dispatch_actions": assessment.dispatch_actions,
        "jev_latency_ms": verdict.latency_ms,
        "duplicate": False,
    }


async def preflight(
    run_id: str, event: dict[str, Any], client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    payload = dict(event)
    payload["phase"] = EventPhase.REQUESTED.value
    return await ingest(run_id, payload, client)
