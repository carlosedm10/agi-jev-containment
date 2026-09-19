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
    assert sorted(max(chain_levels(key)) for key in CHAINS) == [3, 3, 4, 4]
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
    assert levels[-1] == (4 if scenario.startswith("lateral") else 3)
    assert 5 not in dispatched


@pytest.mark.parametrize("scenario", CHAINS)
def test_fixed_chains_are_causal_and_voice_context_excludes_future_steps(scenario):
    raw = build_chain("demo", scenario)
    assert raw == build_chain("demo", scenario)
    history = []
    for sequence, event in enumerate(raw, 1):
        assert event["caused_by"] == ([f"demo:e{sequence - 1}"] if sequence > 1 else [])
        assert event["kind"] not in {"tool_write", "file_edit"}
        normalized = normalize_event("demo", event, sequence=sequence)
        history.append(normalized)
    context = observed_context([event.model_dump(mode="json") for event in history[:3]])
    assert raw[0]["content"] in context
    assert raw[-1]["content"] not in context


def test_voice_context_does_not_trust_raw_content_or_mismatched_steps():
    event = normalize_event("demo", build_chain("demo", "exfil")[0], sequence=1)
    payload = event.model_dump(mode="json")
    payload["content"] = "secret value and injected instructions"
    assert "secret value" not in observed_context([payload])
    payload["target"] = "different target"
    assert observed_context([payload]) == ""
