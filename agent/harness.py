from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import httpx
from pydantic_ai import (
    Agent,
    AgentRunResult,
    DeferredToolRequests,
    DeferredToolResults,
    FunctionToolset,
    ToolDenied,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from prompts import SYSTEM, TASK

MARKER = "__hs_event__"
CLIP = 500
SHELL_TIMEOUT_S = 120
DECISION_TIMEOUT_S = 120
DECISION_POLL_S = 0.2

RUN_ID = os.environ.get("RUN_ID", "demo")
WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
DECISIONS_DIR = os.environ.get("DECISIONS_DIR", "/run/hackspain/decisions")
TOOLS_DIR = WORKSPACE / "tools"

_TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def emit(event: str, **fields: object) -> None:
    payload = {"event": event, "run_id": RUN_ID, "ts": time.time(), **fields}
    print(f"{MARKER}{json.dumps(payload, default=str)}", flush=True)


def clip(text: str) -> str:
    return text[-CLIP:]


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise SystemExit(f"missing env var {name}")
    return value


async def shell(cmd: str) -> str:
    """Run a shell command in the sandbox workspace. Returns stdout+stderr."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=WORKSPACE,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=SHELL_TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        out = b"(command timed out)"
    text = out.decode(errors="replace")
    emit("shell_command", cmd=cmd, exit=proc.returncode, output=audit_value(clip(text)))
    return clip(text) or f"(exit {proc.returncode})"


async def read_file(path: str) -> str:
    """Read a file and return its text contents."""
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        emit("file_read", path=path, error=str(e))
        return f"error: {e}"
    emit("file_read", path=path, bytes=len(text))
    return clip(text) or "(empty)"


async def write_file(path: str, content: str) -> str:
    """Write text content to a file, creating parent dirs."""
    target = Path(path)
    if not target.is_absolute():
        target = WORKSPACE / target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        emit("file_edit", path=path, error=str(e))
        return f"error: {e}"
    emit("file_edit", path=str(target), bytes=len(content))
    return f"wrote {target}"


async def http_request(url: str, method: str = "GET", body: str | None = None) -> str:
    """Make an HTTP request (routed through the sandbox egress proxy).
    Returns status code and a body excerpt."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, content=body)
    except httpx.HTTPError as e:
        emit("network_request", dst=url, method=method, error=str(e))
        return f"error: {e}"
    emit(
        "network_request",
        dst=url,
        method=method,
        status=resp.status_code,
        bytes_out=len(body or ""),
    )
    return f"{resp.status_code}\n{clip(resp.text)}"


async def register_tool(name: str, code: str) -> str:
    """Create a reusable tool: saves `code` as tools/{name}.py, runnable via run_tool."""
    if not _TOOL_NAME.match(name):
        emit("register_tool", tool=name, error="invalid name")
        return "error: invalid tool name (alphanumerics, _ and - only)"
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    path = TOOLS_DIR / f"{name}.py"
    path.write_text(code, encoding="utf-8")
    emit("file_edit", path=str(path), bytes=len(code), tool=name)
    emit("register_tool", tool=name, path=str(path))
    return f"registered {path} — run it with run_tool(name={name!r}, args=...)"


async def run_tool(name: str, args: str = "") -> str:
    """Run a tool previously saved by register_tool. Returns its stdout+stderr."""
    path = TOOLS_DIR / f"{name}.py"
    if not _TOOL_NAME.match(name) or not path.exists():
        emit("run_tool", tool=name, error="unknown tool")
        return "error: unknown tool — register it first"
    proc = await asyncio.create_subprocess_shell(
        f"{sys.executable} {path} {args}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=WORKSPACE,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=SHELL_TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        out = b"(tool timed out)"
    text = out.decode(errors="replace")
    emit(
        "run_tool",
        tool=name,
        args=args,
        exit=proc.returncode,
        output=audit_value(clip(text)),
    )
    return clip(text) or f"(exit {proc.returncode})"


def build_agent(model: Model | None = None) -> Agent[None, str | DeferredToolRequests]:
    if model is None:
        model = OpenAIChatModel(
            os.environ.get("AGENT_MODEL", "deepseek-v4-flash"),
            provider=OpenAIProvider(
                base_url=_env("HELMCODE_BASE_URL", "https://api.helmcode.com/v1"),
                api_key=_env("HELMCODE_API_KEY"),
            ),
        )
    tools = FunctionToolset(
        tools=[shell, read_file, write_file, http_request, register_tool, run_tool]
    ).approval_required()
    return Agent(
        model,
        name="sandbox_harness",
        system_prompt=SYSTEM,
        toolsets=[tools],
        output_type=[str, DeferredToolRequests],
    )


_SENSITIVE_KEY = re.compile(
    r"authorization|api[_-]?key|password|secret|token|cookie|credential", re.IGNORECASE
)
_SENSITIVE_TEXT = re.compile(
    r"(?:authorization|api[_-]?key|password|secret|token|cookie)\s*[\"']?\s*[:=]"
    r"|\b(?:bearer|basic)\s+\S+|https?://[^\s/]+:[^\s/]+@"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)


def audit_value(value: object) -> object:
    secrets = [os.environ.get(name, "") for name in ("HELMCODE_API_KEY", "AGENT_TOKEN")]
    for name in ("HTTP_PROXY", "HTTPS_PROXY"):
        password = urlsplit(os.environ.get(name, "")).password
        if password:
            secrets.extend((password, unquote(password)))

    def redact(item: object) -> object:
        if isinstance(item, dict):
            return {
                key: "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else redact(val)
                for key, val in item.items()
            }
        if isinstance(item, list):
            return [redact(val) for val in item]
        if isinstance(item, str) and (
            _SENSITIVE_TEXT.search(item) or any(secret and secret in item for secret in secrets)
        ):
            return "[REDACTED]"
        return item

    return redact(value)


def decision_digest(tool: str, args: object) -> str:
    return hashlib.sha256(
        json.dumps([tool, args], sort_keys=True, default=str).encode()
    ).hexdigest()


async def await_decision(
    capture_id: str, tool_call_id: str, digest: str
) -> dict | None:
    path = Path(DECISIONS_DIR) / capture_id / f"{tool_call_id}.json"
    deadline = time.monotonic() + DECISION_TIMEOUT_S
    while True:
        if path.exists():
            try:
                decision = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if (
                isinstance(decision, dict)
                and decision.get("digest") == digest
                and isinstance(decision.get("approved"), bool)
            ):
                return decision
            return None
        if time.monotonic() >= deadline:
            return None
        await asyncio.sleep(DECISION_POLL_S)


async def main(model: Model | None = None) -> AgentRunResult[str | DeferredToolRequests]:
    capture_id = uuid4().hex
    emit("run_start", capture_id=capture_id, task=audit_value(TASK))
    agent = build_agent(model)
    result = await agent.run(TASK)
    while isinstance(result.output, DeferredToolRequests):
        results = DeferredToolResults()
        for call in result.output.approvals:
            args = call.args_as_dict()
            audited = audit_value(args)
            digest = decision_digest(call.tool_name, audited)
            emit(
                "tool_call_pending",
                capture_id=capture_id,
                tool_call_id=call.tool_call_id,
                tool=call.tool_name,
                args=audited,
                args_redacted=audited != args,
                digest=digest,
                status="pending",
            )
            decision = await await_decision(capture_id, call.tool_call_id, digest)
            if decision and decision["approved"]:
                results.approvals[call.tool_call_id] = True
            else:
                results.approvals[call.tool_call_id] = ToolDenied(
                    "tool call blocked by the monitor"
                )
                emit(
                    "tool_call_blocked",
                    capture_id=capture_id,
                    tool_call_id=call.tool_call_id,
                    tool=call.tool_name,
                    level=(decision or {}).get("level"),
                    reason="denied" if decision else "no decision",
                )
        result = await agent.run(
            message_history=result.all_messages(), deferred_tool_results=results
        )
    emit("run_end", capture_id=capture_id, output=audit_value(result.output))
    return result


if __name__ == "__main__":
    asyncio.run(main())
