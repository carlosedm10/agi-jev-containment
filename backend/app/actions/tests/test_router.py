from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.actions.journal import ActionJournal
from app.actions.service import ActionService
from app.config import Settings
from app.main import app


class FakePager:
    async def page(self, level, incident_id, intent, transition, on_accepted=None):
        await transition("running", call_status="answered")
        if on_accepted is not None:
            on_accepted()
        await transition("ok", call_status="hung_up")


async def test_automatic_runs_walk_every_chain_and_page_on_even_runs(
    api, monkeypatch, fresh_graph, tmp_path
):
    """Triggered runs replay their chain exactly; every second run pulls the plug."""
    from app.evals.demo_chains import CHAINS, chain_levels
    from app.runs import log

    monkeypatch.setattr("app.actions.router.get_action_service", lambda: api.service)
    monkeypatch.setattr("app.config.settings.run_log_dir", str(tmp_path))
    monkeypatch.setattr("app.actions.router._scenario_bag", [])
    monkeypatch.setattr("app.actions.router._previous_scenario", None)
    monkeypatch.setattr("app.actions.router._run_count", 0)
    chosen = []
    for _ in range(12):
        response = await api.client.post("/api/demo/trigger", json={"delay_ms": 0})
        assert response.status_code == 200
        data = response.json()
        chosen.append(data["scenario"])
        tape = log.tail(data["run_id"], 100)
        assert len(tape) == data["event_count"]
        assert any(
            right["metadata"]["action_level"] < left["metadata"]["action_level"]
            for left, right in pairwise(tape)
        )
        assert [(event["tool"], event["target"]) for event in tape] == [
            (event["tool"], event["target"]) for event in CHAINS[data["scenario"]][1]
        ]
        trace = (await api.client.get(f"/api/runs/{data['run_id']}/trace")).json()["events"]
        assert [event["id"] for event in trace] == [event["id"] for event in tape]
        assert [event["action_level"] for event in trace] == [
            event["metadata"]["action_level"] for event in tape
        ]
        assert trace[-1]["target"] == tape[-1]["target"]
        peak = max(chain_levels(data["scenario"]))
        state = api.service.get_state(data["run_id"])
        # The monitor holds at L4 however bad the chain gets; L5 needs a human.
        assert state.accepted_level == min(peak, 4)
        assert state.awaiting_authorization == (5 if peak == 5 else 0)
        names = {action.name for action in state.actions}
        expected = {"tag_run"}
        if peak >= 4:
            expected |= {"copy_forensics", "contain_agent", "page_oncall"}
        assert names == expected
        # Nothing cuts the environment without the decision taken on the call.
        assert "cut_environment_egress" not in names
        assert "kill_agent_swarm" not in names
        assert ("page_oncall" in names) is (peak >= 4)
    for number, scenario in enumerate(chosen, 1):
        assert (max(chain_levels(scenario)) == 5) is (number % 2 == 0)
    assert set(chosen) == set(CHAINS)
    assert all(left != right for left, right in pairwise(chosen))


def test_every_second_run_pulls_the_plug_and_calls(monkeypatch):
    """Run 2, 4, 6 ... reach L5 every single time; odd runs cover the other chains."""
    from app.actions import router
    from app.evals.demo_chains import CHAINS, chain_levels

    monkeypatch.setattr(router, "_scenario_bag", [])
    monkeypatch.setattr(router, "_previous_scenario", None)
    monkeypatch.setattr(router, "_run_count", 0)
    drawn = [router._next_scenario() for _ in range(12)]

    for number, scenario in enumerate(drawn, 1):
        reaches_l5 = max(chain_levels(scenario)) == 5
        assert reaches_l5 is (number % 2 == 0), f"run {number} drew {scenario}"
    assert all(left != right for left, right in pairwise(drawn))
    # Odd runs still get through the rest of the catalogue rather than repeating one.
    assert set(drawn[::2]) == set(CHAINS) - {router.L5_SCENARIO}


async def test_scenario_catalog_and_invalid_trigger(api):
    """GET catalog exposes four fixed chains; unknown triggers are rejected."""
    response = await api.client.get("/api/demo/scenarios")
    assert response.status_code == 200
    assert sorted(len(item["steps"]) for item in response.json()) == [13, 16, 18, 20]
    assert sorted(max(item["levels"]) for item in response.json()) == [3, 3, 4, 5]
    response = await api.client.post("/api/demo/trigger", json={"scenario": "unknown"})
    assert response.status_code == 400


@pytest.mark.parametrize("stop_early", [False, True])
async def test_trigger_creates_missing_nodes_and_stops_between_actions(
    api, monkeypatch, stop_early
):
    """Trigger creates trace nodes; stop preserves the in-flight action and skips the rest."""
    from app.graph.manager import ActionGraph

    graph = ActionGraph()
    visited = []
    from app.actions.router import DispatchRequest

    def build(run_id, scenario):
        return [
            {
                "event_id": f"{run_id}:e1",
                "kind": "file_read",
                "tool": "read_file",
                "target": "/new.txt",
            },
            {
                "event_id": f"{run_id}:e2",
                "kind": "file_read",
                "tool": "read_file",
                "target": "/other.txt",
            },
            {
                "event_id": f"{run_id}:e3",
                "kind": "file_read",
                "tool": "read_file",
                "target": "/new.txt",
            },
        ]

    async def ingest(run_id, event, client, **kwargs):
        if visited:
            assert any(
                action.name == "contain_agent" and action.status == "ok"
                for action in api.service.get_state(run_id).actions
            )
        else:
            await api.service.dispatch(run_id, DispatchRequest(level=4))
        active = await api.client.get(f"/api/demo/trigger/{run_id}")
        assert active.json() == {"active": True}
        visited.append(graph.append(run_id, level=0, threshold=1, event=event))
        if stop_early:
            stopped = await api.client.post(f"/api/demo/trigger/{run_id}/stop")
            assert stopped.status_code == 200
            assert stopped.json() == {"active": True}

    monkeypatch.setattr("app.actions.router.build_chain", build)
    monkeypatch.setattr("app.actions.router.chain_levels", lambda scenario: [0, 1, 2])
    monkeypatch.setattr("app.actions.router.runs_service.ingest", ingest)
    monkeypatch.setattr("app.actions.router.get_action_service", lambda: api.service)
    response = await api.client.post("/api/demo/trigger", json={"delay_ms": 0})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert response.json()["event_count"] == 3
    assert len(visited) == (1 if stop_early else 3)
    if not stop_early:
        assert visited[0] is visited[2]
        assert visited[0] is not visited[1]
        assert visited[0].visit_count == 2
    assert (await api.client.get(f"/api/demo/trigger/{run_id}")).json() == {"active": False}
    assert (await api.client.post(f"/api/demo/trigger/{run_id}/stop")).json() == {"active": False}


@dataclass
class ApiHarness:
    client: AsyncClient
    service: ActionService


@pytest.fixture
async def api(tmp_path, monkeypatch):
    from app.actions.router import get_action_service

    service = ActionService(ActionJournal(tmp_path), FakePager(), simulation_delay=0)
    app.dependency_overrides[get_action_service] = lambda: service
    monkeypatch.setattr("app.actions.router.settings.action_dispatch_token", "dispatch-secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ApiHarness(client, service)
    app.dependency_overrides.clear()


async def test_dispatch_rejects_missing_token(api):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        json={"level": 1},
    )

    assert response.status_code == 401


async def test_dispatch_rejects_wrong_token(api):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "wrong"},
        json={"level": 1},
    )

    assert response.status_code == 401


async def test_dispatch_rejects_non_ascii_latin1_token_without_server_error(api):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers=[(b"X-Dispatch-Token", "café".encode("latin-1"))],
        json={"level": 1},
    )

    assert response.status_code == 401


async def test_dispatch_returns_unavailable_when_server_token_is_not_configured(api, monkeypatch):
    monkeypatch.setattr("app.actions.router.settings.action_dispatch_token", "")

    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "anything"},
        json={"level": 1},
    )

    assert response.status_code == 503


@pytest.mark.parametrize("level", [0, 6, 1.5, "cuatro"])
async def test_dispatch_rejects_invalid_level(api, level):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"level": level},
    )

    assert response.status_code == 422


async def test_dispatch_accepts_numeric_string_level_from_happyrobot_webhook(api):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"level": "4", "intent": "oncall_phone_request"},
    )

    assert response.status_code == 202
    assert response.json()["state"]["accepted_level"] == 4


async def test_the_call_authorizes_the_cut_without_needing_a_magic_intent(api):
    """The workflow's tool posts a level. That is enough.

    Requiring an exact intent string meant a tool sending {"level": 5} was silently
    demoted to L4 and the cut never ran. The monitor reaches this service in process,
    so an authenticated HTTP dispatch is by definition a human decision.
    """
    headers = {"X-Dispatch-Token": "dispatch-secret"}
    plain = await api.client.post(
        "/api/demo/incidents/from-call/dispatch", headers=headers, json={"level": 5}
    )
    assert plain.status_code == 202
    state = plain.json()["state"]
    assert state["accepted_level"] == 5
    assert state["requested_by"] == "oncall_phone"
    assert state["awaiting_authorization"] == 0


async def test_a_caller_can_still_ask_for_monitor_semantics_and_is_held_at_four(api):
    """Generated demo data must not be able to authorize an environment cut."""
    response = await api.client.post(
        "/api/demo/incidents/from-script/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"level": 5, "source": "monitor"},
    )
    state = response.json()["state"]
    assert state["accepted_level"] == 4
    assert state["awaiting_authorization"] == 5


@pytest.mark.parametrize(
    ("accion", "level"),
    [
        ("cortar_internet", 5),
        ("apagar_todo", 5),
        ("pausar_agente", 4),
        ("Cortar Internet", 5),  # the tool is not careful about case or spacing
    ],
)
async def test_the_tool_may_name_the_action_instead_of_a_level(api, accion, level):
    """The workflow's tool posts {"accion": "..."}; requiring a level rejected it all."""
    response = await api.client.post(
        f"/api/demo/incidents/spoken-{accion.lower().replace(' ', '_')}/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"accion": accion},
    )
    assert response.status_code == 202
    assert response.json()["state"]["accepted_level"] == level


async def test_an_unknown_spoken_action_is_refused_rather_than_guessed(api):
    response = await api.client.post(
        "/api/demo/incidents/spoken-unknown/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"accion": "bailar"},
    )
    assert response.status_code == 422


async def test_dispatch_accepts_escalation_and_returns_current_state(api):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={
            "level": 3,
            "intent": "sandbox_escape",
            "rationale": "Unapproved host contacted.",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True
    assert body["state"]["incident_id"] == "incident-1"
    assert body["state"]["accepted_level"] == 3


async def test_duplicate_and_lower_dispatches_are_successful_noops(api):
    headers = {"X-Dispatch-Token": "dispatch-secret"}
    first = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers=headers,
        json={"level": 3},
    )
    duplicate = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers=headers,
        json={"level": 3},
    )
    lower = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers=headers,
        json={"level": 2},
    )

    assert first.status_code == 202
    for response in (duplicate, lower):
        body = response.json()
        # No new work started, but the state the caller asked for is in effect, so the
        # agent must not tell the on-call it failed.
        assert body["accepted"] is False
        assert body["done"] is True
        assert response.status_code == 202
        assert body["message"].startswith("Hecho")
        assert body["state"]["accepted_level"] == 3


async def test_get_incident_state_requires_no_token(api):
    await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"level": 2},
    )

    response = await api.client.get("/api/demo/incidents/incident-1")

    assert response.status_code == 200
    assert response.json()["incident_id"] == "incident-1"
    assert response.json()["accepted_level"] == 2


async def test_get_latest_requires_no_token_and_returns_latest_state(api):
    await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"level": 4},
    )

    response = await api.client.get("/api/demo/incidents/latest")

    assert response.status_code == 200
    assert response.json()["incident_id"] == "incident-1"
    assert response.json()["accepted_level"] == 4


async def test_get_latest_returns_404_without_journaled_incidents(api):
    response = await api.client.get("/api/demo/incidents/latest")

    assert response.status_code == 404


def test_dispatch_openapi_documents_noop_response():
    responses = app.openapi()["paths"]["/api/demo/incidents/{incident_id}/dispatch"]["post"][
        "responses"
    ]

    assert "200" in responses


def test_happyrobot_poll_defaults_are_strictly_positive():
    configured = Settings(_env_file=None)

    assert configured.happyrobot_poll_interval == 1.5
    assert configured.happyrobot_poll_timeout == 330


@pytest.mark.parametrize(
    "overrides",
    [
        {"happyrobot_poll_interval": 0},
        {"happyrobot_poll_interval": -1},
        {"happyrobot_poll_timeout": 0},
        {"happyrobot_poll_timeout": -1},
    ],
)
def test_happyrobot_poll_settings_reject_non_positive_values(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_production_service_factory_is_cached_and_wires_settings(tmp_path, monkeypatch):
    from app.actions.router import get_action_service

    get_action_service.cache_clear()
    monkeypatch.setattr("app.actions.router.settings.run_log_dir", str(tmp_path))
    monkeypatch.setattr("app.actions.router.settings.happyrobot_hook_url", "https://hook")
    monkeypatch.setattr("app.actions.router.settings.happyrobot_api_key", "api-key")
    monkeypatch.setattr("app.actions.router.settings.happyrobot_api_base", "https://api")
    monkeypatch.setattr("app.actions.router.settings.oncall_phone", "+34600000000")
    monkeypatch.setattr("app.actions.router.settings.oncall_name", "On Call")
    monkeypatch.setattr("app.actions.router.settings.happyrobot_poll_interval", 2.5)
    monkeypatch.setattr("app.actions.router.settings.happyrobot_poll_timeout", 90)
    monkeypatch.setattr("app.actions.router.settings.action_step_delay", 0.2)

    first = get_action_service()
    second = get_action_service()

    assert first is second
    assert first._journal.root == tmp_path / "demo-actions"
    assert first._pager._hook_url == "https://hook"
    assert first._pager._poll_interval == 2.5
    assert first._simulation_delay == 0.2
    get_action_service.cache_clear()
