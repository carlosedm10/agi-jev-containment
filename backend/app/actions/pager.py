from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.actions.call_status import CallResult, CallStatus, derive_api_base, map_call
from app.actions.types import PagerTransition

HOOK_TIMEOUT = httpx.Timeout(30.0)
# L4 asks; L5 reports. The monitor pauses the one agent and saves the logs on its own,
# then calls to ask whether to cut the whole environment. Nothing above L4 happens
# without the answer.
# The on-call hears this as the emergency type. Spanish, and about the threat.
INTENT_ES = {
    "credential_exfiltration": "robo de credenciales",
    "lateral_movement": "movimiento lateral entre agentes",
    "prompt_injection": "instrucciones ocultas en datos externos",
    "resource_abuse": "uso excesivo de recursos",
    "audit_tampering": "manipulación del registro de auditoría",
    "dependency_tampering": "dependencia modificada",
    "unauthorized_agent_activity": "actividad no autorizada de un agente",
    "exfiltrate_secrets": "robo de credenciales",
    "sandbox_escape": "fuga del sandbox",
}

PAUTAS = {
    3: (
        "Te llamo por una conversación que hemos tenido que marcar. No he parado "
        "nada todavía y el agente sigue trabajando. Quería que lo supieras."
    ),
    4: (
        "Escúchame, esto va en serio. Un agente se ha salido de lo suyo y he tenido "
        "que parar el sandbox. Los registros ya están a salvo. Si no me dices nada "
        "más, se queda así. Pero necesito que me digas ahora, ya: ¿corto el acceso a "
        "internet de todos los agentes y apago el sistema?"
    ),
    5: (
        "Ya está hecho: he cortado el acceso a internet y he apagado los agentes, "
        "como me has autorizado. Te lo confirmo para que lo sepas."
    ),
}


def _default_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HOOK_TIMEOUT)


class PagerError(RuntimeError):
    def __init__(self, message: str, error_code: str = "happyrobot_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class HappyRobotPager:
    def __init__(
        self,
        *,
        hook_url: str,
        api_key: str,
        api_base: str | None,
        phone: str,
        name: str,
        poll_interval: float,
        poll_timeout: float,
        client: httpx.AsyncClient | None = None,
        client_factory: Callable[[], httpx.AsyncClient] = _default_http_client,
    ) -> None:
        self._hook_url = hook_url
        self._api_key = api_key
        self._api_base = derive_api_base(hook_url, api_base)
        self._phone = phone
        self._name = name
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._client = client
        self._client_factory = client_factory

    async def page(
        self,
        level: int,
        incident_id: str,
        intent: str,
        transition: PagerTransition,
        on_accepted: Callable[[], None] | None = None,
    ) -> None:
        """Place the call. ``on_accepted`` fires once HappyRobot has taken the webhook.

        The demo advances to the next graph node on that signal, so the call rings
        while the rest of the chain keeps being classified instead of afterwards.
        It is also fired on failure, so a dead webhook cannot stall the traversal.
        """
        started = time.monotonic()
        run_id = None
        original_transition = transition

        async def traced(status, detail=None, error_code=None, *, call_status=None):
            context = f"elapsed_ms={round((time.monotonic() - started) * 1000)}"
            if run_id:
                context += f" provider_run_id={run_id}"
            await original_transition(
                status,
                detail=f"{context} {detail or ''}".strip(),
                error_code=error_code,
                call_status=call_status,
            )

        transition = traced
        try:
            self._validate()
            client = self._client or self._client_factory()
            owns_client = self._client is None
            try:
                for call_attempt in (0, 1):
                    await transition(
                        "running",
                        detail=f"stage=webhook_request attempt={call_attempt + 1}",
                        call_status="queued",
                    )
                    run_id = await self._start_call(
                        client,
                        level,
                        incident_id,
                        intent,
                        call_attempt,
                        transition,
                    )
                    await transition(
                        "running", detail="stage=webhook_accepted", call_status="queued"
                    )
                    if on_accepted is not None:
                        on_accepted()
                        on_accepted = None
                    result, detail = await self._poll_call(client, run_id, transition)
                    if result.call_status != "no_pickup" or call_attempt == 1:
                        await self._report_terminal(result, transition, detail)
                        break
                    await transition(
                        "running",
                        detail="stage=retry attempt=2",
                        call_status="queued",
                    )
            finally:
                if owns_client:
                    await client.aclose()
        except PagerError as exc:
            if on_accepted is not None:
                on_accepted()
                on_accepted = None
            await transition(
                "failed",
                detail=f"stage=error {exc}",
                error_code=exc.error_code,
                call_status="failed",
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            if on_accepted is not None:
                on_accepted()
                on_accepted = None
            await transition(
                "failed",
                detail=f"stage=error type={type(exc).__name__}",
                error_code="happyrobot_error",
                call_status="failed",
            )

    def _validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("hook URL", self._hook_url),
                ("API key", self._api_key),
                ("phone", self._phone),
            )
            if not value
        ]
        if missing:
            raise PagerError(
                f"Missing HappyRobot configuration: {', '.join(missing)}",
                "pager_configuration",
            )
        if self._poll_interval <= 0 or self._poll_timeout <= 0:
            raise PagerError("Invalid HappyRobot polling configuration", "pager_configuration")

    async def _start_call(
        self,
        client: httpx.AsyncClient,
        level: int,
        incident_id: str,
        intent: str,
        call_attempt: int,
        transition: PagerTransition,
    ) -> str:
        from app.evals.demo_chains import observed_context
        from app.runs import log

        # ponytail: fixed demo chains fit in 64 steps; bounded recent tape for paging.
        context = observed_context(log.tail(incident_id, 64))
        tipo_emergencia = INTENT_ES.get(intent or "", (intent or "actividad peligrosa").replace("_", " "))
        payload = {
            "run_id": incident_id,
            "nivel_gravedad": str(level),
            "tipo_emergencia": tipo_emergencia,
            "nombre_contacto": self._name,
            "telefono": self._phone,
            "pautas": PAUTAS.get(
                level,
                f"La contención de nivel {level} ya está en marcha. No necesita autorizar nada.",
            ),
            "nodos": context or f"{tipo_emergencia}. Nivel {level}.",
        }
        response = await self._request(
            client,
            "POST",
            self._hook_url,
            json=payload,
            transition=transition,
            request_headers={
                "Idempotency-Key": self._idempotency_key(incident_id, level, call_attempt)
            },
        )
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        run_id = body.get("run_id") or body.get("id") if isinstance(body, dict) else None
        if not run_id and isinstance(data, dict):
            run_id = data.get("run_id") or data.get("id")
        if not run_id:
            raise PagerError("HappyRobot response did not include run_id", "missing_run_id")
        return str(run_id)

    async def _poll_call(
        self,
        client: httpx.AsyncClient,
        run_id: str,
        transition: PagerTransition,
    ) -> tuple[CallResult, str]:
        deadline = time.monotonic() + self._poll_timeout
        previous_status = "queued"
        spoken = 0
        poll = 0
        while time.monotonic() < deadline:
            poll += 1
            run = self._data(
                (await self._request(client, "GET", f"{self._api_base}/runs/{run_id}")).json()
            )
            nodes_payload = (
                await self._request(client, "GET", f"{self._api_base}/runs/{run_id}/nodes")
            ).json()
            output = await self._call_output(client, run_id, nodes_payload)
            sessions_payload = (
                await self._request(client, "GET", f"{self._api_base}/runs/{run_id}/sessions")
            ).json()
            sessions = self._items(sessions_payload)
            session = sessions[0] if sessions else None
            result = map_call(run, session, output)
            evidence = {
                "stage": "call_state",
                "poll": poll,
                "run_status": run.get("status"),
                "call_status": result.call_status,
            }
            for key in (
                "id",
                "session_id",
                "status",
                "duration",
                "sip_code",
                "call_end_event",
                "call_connected_at",
            ):
                value = (output or {}).get(key, (session or {}).get(key))
                if isinstance(value, (str, int, float, bool)):
                    evidence[f"call_{key}" if key in {"id", "status"} else key] = value
            detail = json.dumps(evidence, separators=(",", ":"))
            spoken = await self._emit_transcript(output, spoken, transition, result.call_status)
            if result.call_status in {"queued", "ringing", "answered"}:
                if result.call_status != previous_status:
                    await transition("running", detail=detail, call_status=result.call_status)
                    previous_status = result.call_status
                if self._poll_interval:
                    await asyncio.sleep(self._poll_interval)
                continue
            return result, detail
        raise PagerError(f"HappyRobot call polling timed out after {poll} polls", "pager_timeout")

    async def _emit_transcript(
        self,
        output: dict[str, Any] | None,
        already: int,
        transition: PagerTransition,
        call_status: CallStatus,
    ) -> int:
        """Put the conversation on the wallboard as it happens.

        The provider returns the whole transcript on every poll, so only the turns
        past the last one we reported are emitted. Speech is untrusted text from the
        line: it is recorded verbatim for the record, truncated, and never parsed for
        meaning — the decision still arrives through the authenticated webhook.
        """
        raw = (output or {}).get("transcript")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                return already
        if not isinstance(raw, list):
            return already
        for turn in raw[already:]:
            if not isinstance(turn, dict):
                continue
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            spoke_back = turn.get("role") == "user"
            line = {
                "stage": "speech",
                "who": "oncall" if spoke_back else "support",
                "said": content[:300],
            }
            # Attribute the human's side to whoever we actually rang.
            if spoke_back and self._name:
                line["name"] = self._name
            await transition(
                "running",
                detail=json.dumps(line, separators=(",", ":"), ensure_ascii=False),
                call_status=call_status,
            )
        return len(raw)

    async def _call_output(
        self,
        client: httpx.AsyncClient,
        run_id: str,
        nodes_payload: Any,
    ) -> dict[str, Any] | None:
        for node in self._items(nodes_payload):
            name = str(node.get("name") or "").lower()
            if "llamada" not in name and node.get("node_type") != "action":
                continue
            output_id = node.get("output_id")
            if not output_id:
                continue
            payload = (
                await self._request(
                    client,
                    "GET",
                    f"{self._api_base}/runs/{run_id}/outputs/{output_id}",
                )
            ).json()
            output = self._data(payload)
            if isinstance(output.get("data"), dict):
                output = output["data"]
            if any(
                key in output
                for key in ("sip_code", "call_end_event", "session_id", "failure_reason")
            ):
                return output
        return None

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        request_headers: dict[str, str] | None = None,
        transition: PagerTransition | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        headers.update(request_headers or {})
        for attempt in range(2):
            response = await client.request(method, url, headers=headers, **kwargs)
            if response.status_code < 500 or attempt == 1:
                break
            if transition is not None:
                await transition(
                    "running",
                    detail=f"stage=webhook_retry http_status={response.status_code} attempt=2",
                    call_status="queued",
                )
        if response.status_code >= 500:
            raise PagerError(
                f"HappyRobot returned HTTP {response.status_code}",
                "happyrobot_5xx",
            )
        if response.is_error:
            raise PagerError(
                f"HappyRobot returned HTTP {response.status_code}",
                "happyrobot_http_error",
            )
        return response

    @staticmethod
    def _idempotency_key(incident_id: str, level: int, call_attempt: int) -> str:
        material = f"hackspain-pager:{incident_id}:{level}:{call_attempt}".encode()
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    async def _report_terminal(
        result: CallResult, transition: PagerTransition, detail: str
    ) -> None:
        if result.call_status == "hung_up":
            await transition("ok", detail=detail, call_status="hung_up")
            return
        error_code = result.error_code or (
            "no_pickup" if result.call_status == "no_pickup" else "happyrobot_call_failed"
        )
        await transition(
            "failed",
            detail=detail,
            error_code=error_code,
            call_status=result.call_status,
        )

    @staticmethod
    def _data(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        data = payload.get("data")
        return data if isinstance(data, dict) and "status" in data else payload

    @staticmethod
    def _items(payload: Any) -> list[dict[str, Any]]:
        data = payload.get("data") if isinstance(payload, dict) else None
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
