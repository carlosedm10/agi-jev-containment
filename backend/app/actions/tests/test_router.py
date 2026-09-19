from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.actions.journal import ActionJournal
from app.actions.service import ActionService
from app.config import Settings
from app.main import app


class FakePager:
    async def page(self, level, incident_id, intent, action_taken, transition):
        await transition("running", call_status="answered")
        await transition("ok", call_status="hung_up")


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


async def test_dispatch_returns_unavailable_when_server_token_is_not_configured(
    api, monkeypatch
):
    monkeypatch.setattr("app.actions.router.settings.action_dispatch_token", "")

    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "anything"},
        json={"level": 1},
    )

    assert response.status_code == 503


@pytest.mark.parametrize("level", [0, 6, 1.5, True])
async def test_dispatch_rejects_invalid_level(api, level):
    response = await api.client.post(
        "/api/demo/incidents/incident-1/dispatch",
        headers={"X-Dispatch-Token": "dispatch-secret"},
        json={"level": level},
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
        assert response.status_code == 200
        assert response.json()["accepted"] is False
        assert response.json()["state"]["accepted_level"] == 3


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
    responses = app.openapi()["paths"][
        "/api/demo/incidents/{incident_id}/dispatch"
    ]["post"]["responses"]

    assert "200" in responses


def test_happyrobot_poll_defaults_are_strictly_positive():
    configured = Settings(_env_file=None)

    assert configured.happyrobot_poll_interval == 1.5
    assert configured.happyrobot_poll_timeout == 240


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
