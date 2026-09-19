from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.actions.call_status import CallResult, map_call
from app.actions.journal import ActionJournal
from app.actions.models import ActionTransition
from app.actions.pager import HappyRobotPager, derive_api_base


@pytest.mark.parametrize(
    ("run", "session", "output", "expected"),
    [
        ({"status": "queued"}, None, None, CallResult("queued")),
        ({"status": "running"}, {"status": "ringing"}, None, CallResult("ringing")),
        (
            {"status": "running"},
            {"status": "active", "call_connected_at": "2026-09-19T12:00:00Z"},
            None,
            CallResult("answered"),
        ),
        (
            {"status": "completed"},
            {"status": "completed", "call_connected_at": "2026-09-19T12:00:00Z"},
            None,
            CallResult("hung_up"),
        ),
        (
            {"status": "completed"},
            {"status": "completed", "failure_reason": "no_answer"},
            None,
            CallResult("no_pickup"),
        ),
        (
            {"status": "failed"},
            {"status": "failed", "failure_reason": "invalid_phone_number"},
            None,
            CallResult("failed", error_code="invalid_phone_number"),
        ),
        (
            {"status": "failed"},
            {"status": "failed", "sip_code": 403, "failure_reason": "provider rejected call"},
            None,
            CallResult("failed", error_code="happyrobot_call_failed"),
        ),
    ],
)
def test_maps_happyrobot_call_state(run, session, output, expected):
    assert map_call(run, session, output) == expected


def test_output_can_supply_terminal_call_evidence():
    assert map_call(
        {"status": "completed"},
        None,
        {"call_end_event": "agent_hung_up", "duration": 12},
    ) == CallResult("hung_up")


def test_derives_eu_api_base_from_hook():
    assert (
        derive_api_base("https://platform.eu.happyrobot.ai/hooks/abc", None)
        == "https://platform.eu.happyrobot.ai/api/v2"
    )


class HappyRobotStub:
    def __init__(
        self,
        attempts: list[list[tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]]],
        *,
        first_hook_status: int = 200,
    ) -> None:
        self.attempts = attempts
        self.first_hook_status = first_hook_status
        self.hook_calls = 0
        self.poll_indexes: dict[str, int] = {}
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            self.hook_calls += 1
            self.payloads.append(json.loads(request.content))
            if self.hook_calls == 1 and self.first_hook_status != 200:
                return httpx.Response(self.first_hook_status, json={"error": "temporary"})
            attempt = self.hook_calls - (1 if self.first_hook_status != 200 else 0)
            return httpx.Response(200, json={"data": {"run_id": f"run-{attempt}"}})

        run_id = request.url.path.split("/runs/", 1)[1].split("/", 1)[0]
        attempt_index = int(run_id.split("-")[-1]) - 1
        poll_index = self.poll_indexes.get(run_id, 0)
        run, session, output = self.attempts[attempt_index][poll_index]
        path = request.url.path
        if path.endswith(f"/runs/{run_id}"):
            return httpx.Response(200, json=run)
        if path.endswith("/sessions"):
            self.poll_indexes[run_id] = poll_index + 1
            return httpx.Response(200, json={"data": [] if session is None else [session]})
        if path.endswith("/nodes"):
            nodes = [] if output is None else [{"name": "llamada", "output_id": "out-1"}]
            return httpx.Response(200, json={"data": nodes})
        if path.endswith("/outputs/out-1"):
            return httpx.Response(200, json={"data": output})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")


async def run_pager(
    stub: Callable[[httpx.Request], httpx.Response],
) -> tuple[list[tuple[str, str | None, str | None]], HappyRobotPager]:
    transitions: list[tuple[str, str | None, str | None]] = []

    async def transition(
        status: str,
        detail: str | None = None,
        error_code: str | None = None,
        *,
        call_status: str | None = None,
    ) -> None:
        transitions.append((status, call_status, error_code))

    client = httpx.AsyncClient(transport=httpx.MockTransport(stub))
    pager = HappyRobotPager(
        hook_url="https://platform.happyrobot.ai/hooks/page",
        api_key="secret",
        api_base="https://platform.happyrobot.ai/api/v2",
        phone="+34600000000",
        name="Guli",
        poll_interval=0,
        poll_timeout=1,
        client=client,
    )
    try:
        await pager.page(
            4,
            "incident-1",
            "sandbox_escape",
            "Contained all live runs",
            transition,
        )
    finally:
        await client.aclose()
    return transitions, pager


async def test_posts_telefono_and_reports_answered_then_hung_up():
    stub = HappyRobotStub(
        [[
            (
                {"status": "running"},
                {"status": "active", "call_connected_at": "now"},
                None,
            ),
            (
                {"status": "completed"},
                {"status": "completed", "call_connected_at": "now"},
                None,
            ),
        ]]
    )

    transitions, _ = await run_pager(stub)

    assert stub.payloads == [
        {
            "tipo_emergencia": "sandbox_escape (level 4, run incident-1)",
            "pautas": "Contained all live runs.",
            "nivel_gravedad": "crítico",
            "nombre_contacto": "Guli",
            "telefono": "+34600000000",
        }
    ]
    assert transitions == [
        ("running", "queued", None),
        ("running", "answered", None),
        ("ok", "hung_up", None),
    ]


async def test_retries_webhook_once_after_5xx():
    stub = HappyRobotStub(
        [[({"status": "completed"}, {"failure_reason": "invalid number"}, None)]],
        first_hook_status=503,
    )

    transitions, _ = await run_pager(stub)

    assert stub.hook_calls == 2
    assert transitions[-1] == ("failed", "failed", "invalid_phone_number")


async def test_retries_completed_no_pickup_once_then_fails():
    no_pickup = (
        {"status": "completed"},
        {"status": "completed", "failure_reason": "no_answer"},
        None,
    )
    stub = HappyRobotStub([[no_pickup], [no_pickup]])

    transitions, _ = await run_pager(stub)

    assert stub.hook_calls == 2
    assert transitions[-1] == ("failed", "no_pickup", "no_pickup")


async def test_journal_replay_keeps_final_call_status_separate(tmp_path):
    journal = ActionJournal(tmp_path)
    journal.append(
        ActionTransition(
            incident_id="incident",
            level=4,
            action_id="incident:page:l4",
            name="page_oncall",
            ladder_level=None,
            mode="real",
            status="ok",
            call_status="hung_up",
        )
    )

    state = journal.state("incident")

    assert state.pager_status == "ok"
    assert state.call_status == "hung_up"
