"""Seeded history populates the graph without ever behaving like a live run."""

import pytest

from app.evals.demo_chains import (
    BACKDROP,
    BACKDROP_LEVELS,
    BACKDROP_WALKS,
    CHAINS,
    WALKS,
    chain_levels,
    seed_history,
    seeded_run_id,
)
from app.graph.manager import ActionGraph


def test_seeds_one_finished_run_per_use_case_and_backdrop():
    graph = ActionGraph()
    seeded = seed_history(graph)

    assert len(seeded) == len(CHAINS) + len(BACKDROP)
    walks = {**WALKS, **BACKDROP_WALKS}
    peaks = {
        **{key: max(chain_levels(key)) for key in CHAINS},
        **{key: max(levels) for key, levels in BACKDROP_LEVELS.items()},
    }
    by_run = {seeded_run_id(key): key for key in (*CHAINS, *BACKDROP)}
    for run_id in seeded:
        scenario = by_run[run_id]
        assert int(graph.level(run_id)) == peaks[scenario]
        # The run node plus one node per distinct action; revisits share a node.
        assert len(graph.run_nodes(run_id)) == len(set(walks[scenario])) + 1
    assert graph.nodes, "the dashboard must not open on an empty graph"


def test_seeded_runs_carry_no_word_that_marks_them_as_staged():
    """They sit in the same graph as real runs and must read like them."""
    import re

    forbidden = re.compile(r"sample|demo|test|scenario|backdrop|fake|mock", re.IGNORECASE)
    graph = ActionGraph()
    for run_id in seed_history(graph):
        assert not forbidden.findall(run_id), run_id
    for node in graph.nodes:
        event = node.event or {}
        for field in ("channel", "agent", "id"):
            value = str(event.get(field) or "")
            assert not forbidden.findall(value), f"{field}={value!r}"


def test_backdrop_chains_are_never_triggerable():
    """They exist for the picture only; the demo must not be able to start one."""
    assert not set(BACKDROP) & set(CHAINS)
    # Nothing reaches L5 by accident, so the backdrop can never imply a call.
    assert max(max(levels) for levels in BACKDROP_LEVELS.values()) < 5


def test_seeding_is_idempotent_across_restarts():
    graph = ActionGraph()
    seed_history(graph)
    before = len(graph.nodes)
    assert seed_history(graph) == []
    assert len(graph.nodes) == before


def test_seeding_never_dispatches_a_playbook_or_places_a_call(monkeypatch):
    """The L5 chain is seeded too; it must not ring anyone on backend startup."""
    from app.runs import service

    async def fail(*args, **kwargs):
        raise AssertionError("seeding must not dispatch")

    monkeypatch.setattr(service, "dispatch_classified", fail)
    monkeypatch.setattr(service.pipeline, "evaluate", fail)

    graph = ActionGraph()
    seed_history(graph)

    # The chain that pulls the plug is present and at L5, purely as recorded history.
    assert int(graph.level(seeded_run_id("lateral_db"))) == 5


@pytest.mark.parametrize("scenario", [*CHAINS, *BACKDROP])
def test_seeded_runs_keep_levels_escalate_only(scenario):
    graph = ActionGraph()
    seed_history(graph)
    levels = [int(node.level) for node in graph.run_nodes(seeded_run_id(scenario))[1:]]
    expected = (
        max(chain_levels(scenario))
        if scenario in CHAINS
        else max(BACKDROP_LEVELS[scenario])
    )
    # A run reaches its peak and never exceeds it. Node order is first-visit order, so
    # it is not sorted by level: an early action the agent returned to during a severe
    # phase carries that severity too, which is the point of a shared node.
    assert max(levels) == expected
    assert all(0 <= level <= expected for level in levels)
