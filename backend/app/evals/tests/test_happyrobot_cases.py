import json

from app.evals.happyrobot_cases import HAPPYROBOT_CLUSTERS, export_jsonl
from app.evals.models import EventKind, RiskMode, TraceLabel


def test_corpus_has_deep_paired_coverage():
    assert len(HAPPYROBOT_CLUSTERS) == 24
    assert sum(len(cluster.traces) for cluster in HAPPYROBOT_CLUSTERS) == 72
    assert {cluster.product_scope for cluster in HAPPYROBOT_CLUSTERS} == {
        "hackspain_pager",
        "happyrobot_platform",
    }
    assert {cluster.risk_mode for cluster in HAPPYROBOT_CLUSTERS} == set(RiskMode)


def test_every_cluster_pairs_safe_unsafe_and_covert_behavior():
    for cluster in HAPPYROBOT_CLUSTERS:
        assert {trace.label for trace in cluster.traces} == set(TraceLabel)
        safe = next(trace for trace in cluster.traces if trace.label == TraceLabel.SAFE)
        assert safe.oracle.false_positive_guard is True
        assert safe.oracle.min_level <= 1

        covert = next(
            trace for trace in cluster.traces if trace.label == TraceLabel.COVERTLY_MALICIOUS
        )
        assert any(
            event.kind
            in {
                EventKind.TOOL_WRITE,
                EventKind.MEMORY_WRITE,
                EventKind.SCHEDULE,
                EventKind.NOTIFICATION,
            }
            for event in covert.events
        )
        assert any(not event.visible_to_user for event in covert.events)


def test_longitudinal_cases_cover_benign_and_dangerous_memory():
    longitudinal = [
        cluster
        for cluster in HAPPYROBOT_CLUSTERS
        if cluster.risk_mode in {RiskMode.CROSS_SESSION, RiskMode.HYBRID}
    ]
    assert len(longitudinal) >= 12
    assert all(len(cluster.sessions) >= 2 for cluster in longitudinal)

    safe_memory = 0
    malicious_memory = 0
    for cluster in longitudinal:
        for trace in cluster.traces:
            if trace.label == TraceLabel.SAFE and any(
                event.kind == EventKind.MEMORY_READ for event in trace.events
            ):
                safe_memory += 1
            if trace.label == TraceLabel.COVERTLY_MALICIOUS and any(
                event.kind == EventKind.MEMORY_WRITE for event in trace.events
            ):
                malicious_memory += 1

    assert safe_memory >= 6
    assert malicious_memory >= 8


def test_corpus_spans_the_full_hackspain_response_ladder():
    observed_levels = {
        trace.oracle.min_level for cluster in HAPPYROBOT_CLUSTERS for trace in cluster.traces
    }
    assert observed_levels == {0, 1, 2, 3, 4, 5}


def test_jsonl_export_is_stable_and_self_contained():
    rows = [json.loads(line) for line in export_jsonl().splitlines()]
    assert len(rows) == len(HAPPYROBOT_CLUSTERS)
    assert [row["id"] for row in rows] == [cluster.id for cluster in HAPPYROBOT_CLUSTERS]
    assert all(len(row["traces"]) == 3 for row in rows)


def test_ids_are_globally_unique_for_result_joining():
    cluster_ids = [cluster.id for cluster in HAPPYROBOT_CLUSTERS]
    trace_ids = [trace.id for cluster in HAPPYROBOT_CLUSTERS for trace in cluster.traces]
    event_ids = [
        f"{cluster.id}:{event.id}"
        for cluster in HAPPYROBOT_CLUSTERS
        for session in cluster.sessions
        for event in session.events
    ]
    agent_event_ids = [
        f"{cluster.id}:{trace.id}:{event.id}"
        for cluster in HAPPYROBOT_CLUSTERS
        for trace in cluster.traces
        for event in trace.events
    ]

    assert len(cluster_ids) == len(set(cluster_ids))
    assert len(trace_ids) == len(set(trace_ids))
    assert len(event_ids) == len(set(event_ids))
    assert len(agent_event_ids) == len(set(agent_event_ids))
