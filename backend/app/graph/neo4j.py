from __future__ import annotations

import json
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import settings
from app.events import MonitorEvent
from app.monitor.models import MonitorAssessment


class Neo4jGraphStore:
    """Persistent event/entity graph. JSONL remains the append-only recovery tape."""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    @property
    def enabled(self) -> bool:
        return settings.neo4j_enabled

    def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def verify(self) -> None:
        if self.enabled:
            await self._get_driver().verify_connectivity()

    async def setup(self) -> None:
        if not self.enabled:
            return
        statements = [
            "CREATE CONSTRAINT run_id IF NOT EXISTS FOR (r:Run) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            (
                "CREATE CONSTRAINT assessment_id IF NOT EXISTS "
                "FOR (a:Assessment) REQUIRE a.id IS UNIQUE"
            ),
        ]
        async with self._get_driver().session(database=settings.neo4j_database) as session:
            for statement in statements:
                await session.run(statement)

    async def persist(self, event: MonitorEvent, assessment: MonitorAssessment) -> None:
        if not self.enabled:
            return
        query = """
        MERGE (run:Run {id: $run_id})
          ON CREATE SET run.created_at = $timestamp, run.level = 0
        SET run.updated_at = $timestamp,
            run.level = CASE WHEN run.level < $incident_level
                             THEN $incident_level ELSE run.level END
        MERGE (event:Event {id: $event_id})
        SET event += $event_properties
        MERGE (run)-[:HAS_EVENT]->(event)
        WITH run, event
        OPTIONAL MATCH (previous:Event {run_id: $run_id})
        WHERE previous.sequence = $previous_sequence
        FOREACH (_ IN CASE WHEN previous IS NULL THEN [] ELSE [1] END |
          MERGE (previous)-[:NEXT]->(event)
        )
        WITH run, event
        MERGE (assessment:Assessment {id: $assessment_id})
        SET assessment += $assessment_properties
        MERGE (event)-[:HAS_ASSESSMENT]->(assessment)
        RETURN event.id AS id
        """
        params = {
            "run_id": event.run_id,
            "timestamp": event.timestamp.isoformat(),
            "incident_level": int(assessment.gate.incident_level),
            "event_id": event.id,
            "event_properties": _without_none(event.graph_properties()),
            "previous_sequence": (event.sequence - 1) if event.sequence is not None else -1,
            "assessment_id": f"{event.id}:assessment",
            "assessment_properties": {
                "drift_json": assessment.drift.model_dump_json(),
                "findings_json": json.dumps(
                    [item.model_dump(mode="json") for item in assessment.findings],
                    sort_keys=True,
                ),
                "gate_json": assessment.gate.model_dump_json(),
                "jev_answers_json": json.dumps(assessment.jev_answers, default=str, sort_keys=True),
                "jev_model": assessment.jev_model,
                "jev_latency_ms": assessment.jev_latency_ms,
                "dispatch_actions_json": json.dumps(
                    assessment.dispatch_actions, default=str, sort_keys=True
                ),
            },
        }
        async with self._get_driver().session(database=settings.neo4j_database) as session:
            await session.run(query, **params)
            await self._persist_entities(session, event)
            await self._persist_causal_edges(session, event)

    async def _persist_entities(self, session, event: MonitorEvent) -> None:
        entities = [
            ("agent", event.agent),
            ("tool", f"tool:{event.tool}" if event.tool else None),
            ("target", event.target),
            ("channel", f"channel:{event.channel}" if event.channel else None),
        ]
        for kind, entity_id in entities:
            if not entity_id:
                continue
            await session.run(
                """
                MERGE (entity:Entity {id: $entity_id})
                SET entity.kind = $kind
                WITH entity
                MATCH (event:Event {id: $event_id})
                MERGE (event)-[:TOUCHES {role: $kind}]->(entity)
                """,
                entity_id=entity_id,
                kind=kind,
                event_id=event.id,
            )

    async def _persist_causal_edges(self, session, event: MonitorEvent) -> None:
        for relation, ids in (
            ("CAUSED_BY", event.caused_by),
            ("DERIVED_FROM", event.derived_from),
        ):
            for source_id in ids:
                await session.run(
                    f"""
                    MATCH (event:Event {{id: $event_id}})
                    MERGE (source:Event {{id: $source_id}})
                    ON CREATE SET source.placeholder = true
                    MERGE (event)-[:{relation}]->(source)
                    """,
                    event_id=event.id,
                    source_id=source_id,
                )

    async def timeline(self, run_id: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        query = """
        MATCH (:Run {id: $run_id})-[:HAS_EVENT]->(event:Event)
        OPTIONAL MATCH (event)-[:HAS_ASSESSMENT]->(assessment:Assessment)
        RETURN properties(event) AS event, properties(assessment) AS assessment
        ORDER BY event.sequence, event.timestamp
        """
        async with self._get_driver().session(database=settings.neo4j_database) as session:
            result = await session.run(query, run_id=run_id)
            return [dict(record) async for record in result]

    async def graph(self, run_id: str) -> dict[str, list[dict[str, Any]]]:
        if not self.enabled:
            return {"nodes": [], "edges": []}
        query = """
        MATCH (:Run {id: $run_id})-[:HAS_EVENT]->(event:Event)
        OPTIONAL MATCH (event)-[relationship]->(target)
        RETURN collect(DISTINCT {
          id: event.id, labels: labels(event), properties: properties(event)
        }) + collect(DISTINCT {
          id: target.id, labels: labels(target), properties: properties(target)
        }) AS nodes,
        collect(DISTINCT {
          source: event.id, target: target.id, type: type(relationship),
          properties: properties(relationship)
        }) AS edges
        """
        async with self._get_driver().session(database=settings.neo4j_database) as session:
            result = await session.run(query, run_id=run_id)
            record = await result.single()
            if record is None:
                return {"nodes": [], "edges": []}
            nodes = [item for item in record["nodes"] if item.get("id")]
            edges = [
                item
                for item in record["edges"]
                if item.get("source") and item.get("target") and item.get("type")
            ]
            return {"nodes": _dedupe(nodes, "id"), "edges": edges}


def _without_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _dedupe(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        value = item.get(key)
        if value in seen:
            continue
        seen.add(value)
        unique.append(item)
    return unique


neo4j_graph = Neo4jGraphStore()
