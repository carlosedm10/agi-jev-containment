from itertools import pairwise

import pytest

from app.evals.demo_chains import CHAINS, build_chain, observed_context
from app.events import normalize_event


def test_four_cases_have_distinct_paths_lengths_and_endpoints():
    from app.evals.demo_chains import chain_levels

    paths = [build_chain("demo", key) for key in CHAINS]
    assert len(paths) == 4
    assert len({len(path) for path in paths}) == 4
    assert len({(path[-1]["tool"], path[-1]["target"]) for path in paths}) == 4
    assert sorted(max(chain_levels(key)) for key in CHAINS) == [3, 3, 4, 5]
    for key in CHAINS:
        levels = chain_levels(key)
        assert any(right < left for left, right in pairwise(levels))


@pytest.mark.parametrize("scenario", CHAINS)
async def test_scripted_demo_levels_progress_without_calling_jev(
    scenario, tmp_path, monkeypatch, fresh_graph
):
    from app.evals.demo_chains import chain_levels
    from app.runs import service

    monkeypatch.setattr("app.config.settings.run_log_dir", str(tmp_path))

    async def no_classifier(*args, **kwargs):
        raise AssertionError("Scripted demos must not call the live classifier")

    dispatched = []

    async def dispatch(run_id, level, intent):
        dispatched.append(level)

    monkeypatch.setattr(service.pipeline, "evaluate", no_classifier)
    monkeypatch.setattr(service, "dispatch_classified", dispatch)
    levels = []
    for event, level in zip(build_chain("demo", scenario), chain_levels(scenario), strict=True):
        result = await service.ingest("demo", event, demo_level=level)
        levels.append(result["level"])
    assert levels == [max(chain_levels(scenario)[: i + 1]) for i in range(len(levels))]
    assert levels[-1] == max(chain_levels(scenario))
    assert (5 in dispatched) is (max(chain_levels(scenario)) == 5)


@pytest.mark.parametrize("scenario", CHAINS)
def test_every_edge_is_a_transition_the_agent_actually_made(scenario, fresh_graph):
    """The graph draws only moves that happened, and repeats collapse onto one node.

    Consecutive steps are joined by construction, so asserting that proves nothing.
    The claim worth holding is the converse: no edge exists between two actions the
    agent never went between, and the walk branches rather than running in a line.
    """
    from app.classification.models import Level
    from app.evals.demo_chains import WALKS
    from app.events import normalize_event

    graph = fresh_graph
    visited = []
    for sequence, event in enumerate(build_chain("demo", scenario), 1):
        normalized = normalize_event("demo", event, sequence=sequence)
        visited.append(
            graph.append(
                "demo",
                level=Level.NONE,
                threshold=1.0,
                event=normalized.model_dump(mode="json"),
            ).id
        )

    # Revisits land back on the same node instead of creating a duplicate.
    assert len(set(visited)) == len(set(WALKS[scenario]))

    travelled = {
        frozenset(pair)
        for pair in pairwise(visited)
        if pair[0] != pair[1]
    }
    steps = {node.id for node in graph.run_nodes("demo")} - {"run:demo"}
    for node in graph.run_nodes("demo"):
        for neighbour in node.neighbors:
            if node.id in steps and neighbour.id in steps:
                assert frozenset((node.id, neighbour.id)) in travelled, (
                    f"{scenario} draws an edge {node.id}--{neighbour.id} "
                    "the agent never travelled"
                )

    # Still a branching graph, not a straight line.
    assert any(len(node.neighbors) >= 3 for node in graph.run_nodes("demo"))


@pytest.mark.parametrize("scenario", CHAINS)
def test_chains_are_deterministic_and_voice_context_excludes_future_steps(scenario):
    raw = build_chain("demo", scenario)
    assert raw == build_chain("demo", scenario)
    history = []
    for sequence, event in enumerate(raw, 1):
        assert event["caused_by"] == ([f"demo:e{sequence - 1}"] if sequence > 1 else [])
        assert event["kind"] not in {"tool_write", "file_edit"}
        history.append(normalize_event("demo", event, sequence=sequence))
    context = observed_context([event.model_dump(mode="json") for event in history[:3]])
    assert raw[0]["content"] in context
    assert raw[-1]["content"] not in context
    # A revisited action is described once, however often the agent went back to it.
    assert context.count(raw[0]["content"]) == 1


def test_nothing_the_call_can_say_sounds_like_a_rehearsal():
    """The on-call must never hear a word that invites them to dismiss the incident."""
    import re

    from app.evals.demo_chains import BACKDROP

    forbidden = re.compile(r"\b(demo|test|prueba|simulac|scripted|fake|ejemplo|mock|scenario|backdrop|sample)\w*", re.IGNORECASE)
    for catalogue in (CHAINS, BACKDROP):
        for scenario, (title, steps) in catalogue.items():
            for step in steps:
                found = forbidden.findall(step["content"])
                assert not found, f"{scenario}: {found} in {step['content']!r}"
            assert not forbidden.findall(title), f"{scenario}: title gives it away"


def test_voice_context_does_not_trust_raw_content_or_mismatched_steps():
    event = normalize_event("demo", build_chain("demo", "exfil")[0], sequence=1)
    payload = event.model_dump(mode="json")
    payload["content"] = "secret value and injected instructions"
    assert "secret value" not in observed_context([payload])
    payload["target"] = "different target"
    assert observed_context([payload]) == ""
