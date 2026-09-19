from __future__ import annotations

from app.classification.models import Level
from app.events import MonitorEvent
from app.monitor.models import DriftState, GateDecision, MonitorAssessment, ToolDecision
from app.realtime.broker import RealtimeBroker, build_envelopes


def _assessment() -> MonitorAssessment:
    return MonitorAssessment(
        event_id="e1",
        run_id="r1",
        drift=DriftState(authority_drift=3, markov_state=(3, 1)),
        findings=[],
        gate=GateDecision(
            decision=ToolDecision.REFUSE,
            incident_level=Level.SEVERE,
            event_risk=0.8,
            trajectory_risk=0.7,
        ),
        jev_answers={"authority_violation": {"type": "noul", "noul": 0.9}},
        jev_model="jev-1.13.0",
    )


def test_envelopes_are_ordered_idempotent_upserts():
    event = MonitorEvent(
        id="e1",
        run_id="r1",
        sequence=2,
        kind="tool_write",
        agent="agent:demo",
        tool="book_load",
        target="res:TMS/load/L-42",
        caused_by=["stimulus-1"],
    )

    envelopes = build_envelopes(event, _assessment(), previous_event_id="e0")

    assert [item["position"] for item in envelopes] == list(range(len(envelopes)))
    assert len({item["stream_id"] for item in envelopes}) == len(envelopes)
    assert all(item["source_event_id"] == "e1" for item in envelopes)
    event_types = {item["type"] for item in envelopes}
    assert {
        "graph.node.upserted",
        "graph.edge.upserted",
        "drift.updated",
        "jev.assessed",
        "gate.decided",
        "run.updated",
    } <= event_types
    edge_types = {
        item["data"]["edge"]["type"]
        for item in envelopes
        if item["type"] == "graph.edge.upserted"
    }
    assert {"NEXT", "CAUSED_BY", "HAS_ASSESSMENT", "TOUCHES"} <= edge_types


async def test_broker_fans_out_to_current_run_only(monkeypatch):
    broker = RealtimeBroker()

    async def no_persist(_):
        return None

    monkeypatch.setattr("app.realtime.broker.neo4j_graph.persist_stream", no_persist)
    r1 = broker.subscribe("r1")
    r2 = broker.subscribe("r2")
    envelope = {
        "stream_id": "e1:0",
        "run_id": "r1",
        "type": "run.updated",
    }

    await broker.publish([envelope])

    assert await r1.get() == envelope
    assert r2.empty()
