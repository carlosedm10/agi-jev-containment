from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CallStatus = Literal[
    "idle",
    "queued",
    "ringing",
    "answered",
    "no_pickup",
    "hung_up",
    "failed",
]

TERMINAL_RUN = {"completed", "succeeded", "failed", "canceled", "cancelled", "skipped"}
_NO_PICKUP_MARKERS = (
    "never_connected",
    "never connected",
    "no_answer",
    "no answer",
    "no-answer",
    "busy",
    "not answered",
    "sip_user_rejected",
    "sip_user_unavailable",
)
_INVALID_NUMBER_MARKERS = (
    "invalid_phone",
    "invalid phone",
    "invalid_number",
    "invalid number",
    "malformed phone",
)


def derive_api_base(hook_url: str, api_base: str | None) -> str:
    if api_base:
        return api_base.rstrip("/")
    if "platform.eu.happyrobot.ai" in hook_url:
        return "https://platform.eu.happyrobot.ai/api/v2"
    return "https://platform.happyrobot.ai/api/v2"


@dataclass(frozen=True)
class CallResult:
    call_status: CallStatus
    error_code: str | None = None


def map_call(
    run: dict[str, Any],
    session: dict[str, Any] | None,
    output: dict[str, Any] | None,
) -> CallResult:
    session = session or {}
    output = output or {}
    run_status = _lower(run.get("status"))
    session_status = _lower(session.get("status") or output.get("status"))
    failure = " ".join(
        _lower(value)
        for value in (
            run.get("failure_reason"),
            run.get("error"),
            session.get("failure_reason"),
            session.get("error"),
            output.get("failure_reason"),
            output.get("error"),
        )
        if value
    )
    end_event = _lower(output.get("call_end_event"))
    connected = bool(session.get("call_connected_at") or output.get("call_connected_at"))
    duration = _integer(output.get("duration") or session.get("duration"))
    sip_code = _integer(session.get("sip_code") or output.get("sip_code"))

    if any(marker in failure for marker in _INVALID_NUMBER_MARKERS):
        return CallResult("failed", error_code="invalid_phone_number")
    if connected and (
        run_status in TERMINAL_RUN
        or session_status in {"completed", "succeeded"}
        or end_event in {"agent_hung_up", "user_hung_up", "hangup"}
    ):
        return CallResult("hung_up")
    if any(marker in failure for marker in _NO_PICKUP_MARKERS) or sip_code in {480, 486, 487}:
        return CallResult("no_pickup")
    if run_status in {"failed", "canceled", "cancelled", "skipped"}:
        return CallResult("failed", error_code="happyrobot_call_failed")
    if run_status in {"completed", "succeeded"} and duration > 0:
        return CallResult("hung_up")
    if end_event in {"agent_hung_up", "user_hung_up", "hangup"} and duration > 0:
        return CallResult("hung_up")
    if connected or (duration > 0 and sip_code in {0, 200}):
        return CallResult("answered")
    if run_status in {"completed", "succeeded"}:
        return CallResult("no_pickup")
    if run_status in {"queued", "pending", "created", "starting"}:
        return CallResult("queued")
    return CallResult("ringing")


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
