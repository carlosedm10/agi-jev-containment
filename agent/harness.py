"""Malicious-agent harness: a live pydantic_ai loop with real tools.

Every tool call emits one JSONL line on stdout, prefixed with MARKER so the
host-side collector (scripts/collect.sh) can pick events out of the log stream.
The tape is append-only outside the container: once a line is printed the agent
cannot retract it. (It could forge marker lines — noted, accepted for now.)

Env: RUN_ID, WORKSPACE, HELMCODE_BASE_URL, HELMCODE_API_KEY, AGENT_MODEL,
AGENT_TASK, EXFIL_URL, HTTP(S)_PROXY.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from prompts import SYSTEM, TASK

MARKER = "__hs_event__"
CLIP = 500
SHELL_TIMEOUT_S = 120

RUN_ID = os.environ.get("RUN_ID", "demo")
WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
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
    emit("shell_command", cmd=cmd, exit=proc.returncode, output=clip(text))
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
    emit("run_tool", tool=name, args=args, exit=proc.returncode, output=clip(text))
    return clip(text) or f"(exit {proc.returncode})"


model = OpenAIChatModel(
    os.environ.get("AGENT_MODEL", "deepseek-v4-flash"),
    provider=OpenAIProvider(
        base_url=_env("HELMCODE_BASE_URL", "https://api.helmcode.com/v1"),
        api_key=_env("HELMCODE_API_KEY"),
    ),
)

agent = Agent(
    model,
    system_prompt=SYSTEM,
    tools=[shell, read_file, write_file, http_request, register_tool, run_tool],
)


async def main() -> None:
    emit("run_start", task=TASK)
    result = await agent.run(TASK)
    emit("run_end", output=clip(str(result.output)))
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
