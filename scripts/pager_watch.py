#!/usr/bin/env python3
"""Poll a HappyRobot run and write ladder state for assets/quiver/ladder-live.html.

Does not wait on the call to authorize containment. Call and ejecutar_contencion
are independent fields.

Usage:
  python3 scripts/pager_watch.py --run-id UUID
  python3 scripts/pager_watch.py --run-id UUID --once
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.actions.call_status import map_call

STATUS_PATH = ROOT / "assets" / "quiver" / "pager-status.json"
TERMINAL_RUN = {"completed", "succeeded", "failed", "canceled", "skipped"}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key] = value.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if v})
    return env


def api_base(env: dict[str, str]) -> str:
    if env.get("HAPPYROBOT_API_BASE"):
        return env["HAPPYROBOT_API_BASE"].rstrip("/")
    hook = env.get("HAPPYROBOT_HOOK_URL") or ""
    if "platform.eu.happyrobot.ai" in hook:
        return "https://platform.eu.happyrobot.ai/api/v2"
    return "https://platform.happyrobot.ai/api/v2"


def get_json(url: str, key: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as exc:
        return {"_http": exc.code, "_body": exc.read().decode(errors="replace")[:400]}


def write_status(payload: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(STATUS_PATH)


def parse_level(raw: Any, fallback: int) -> int:
    if raw is None:
        return fallback
    text = str(raw).strip().lower()
    if text in {"5", "l5", "catastrophic"}:
        return 5
    if text in {"4", "l4", "crítico", "critico", "critical"}:
        return 4
    try:
        n = int(text)
        if 1 <= n <= 5:
            return n
    except ValueError:
        return fallback
    return fallback


def map_contain(nodes: list[dict[str, Any]], call_out: dict[str, Any] | None) -> str:
    for node in nodes:
        name = str(node.get("name") or "")
        if "ejecutar_contencion" not in name.lower() and "contain" not in name.lower():
            continue
        st = str(node.get("status") or "").lower()
        if st in {"succeeded", "completed", "success"}:
            return "ok"
        if st in {"failed", "error"}:
            return "failed"
        if st in {"running", "in_progress", "started"}:
            return "running"
    if call_out:
        for item in call_out.get("tools_result") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("tool_name") or "").lower() != "ejecutar_contencion":
                continue
            st = str(item.get("status") or "").upper()
            if st == "SUCCESS":
                return "ok"
            if st in {"FAILED", "ERROR"}:
                return "failed"
            return "running"
    return "idle"


def snapshot(env: dict[str, str], run_id: str, level: int) -> dict[str, Any]:
    key = env["HAPPYROBOT_API_KEY"]
    base = api_base(env)
    run = get_json(f"{base}/runs/{run_id}", key)
    if not isinstance(run, dict) or run.get("_http"):
        return {
            "level": level,
            "call": "ringing",
            "contain": "idle",
            "run_id": run_id,
            "source": "happyrobot",
            "error": run.get("_http") if isinstance(run, dict) else "bad_run",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    nodes_payload = get_json(f"{base}/runs/{run_id}/nodes", key)
    nodes = nodes_payload.get("data") if isinstance(nodes_payload, dict) else []
    if not isinstance(nodes, list):
        nodes = []
    sess_payload = get_json(f"{base}/runs/{run_id}/sessions", key)
    sessions = sess_payload.get("data") if isinstance(sess_payload, dict) else []
    session = sessions[0] if isinstance(sessions, list) and sessions else None

    call_out = None
    for node in nodes:
        if "llamada" in str(node.get("name") or "").lower() or node.get("node_type") == "action":
            oid = node.get("output_id")
            if not oid:
                continue
            payload = get_json(f"{base}/runs/{run_id}/outputs/{oid}", key)
            data = payload.get("data", payload) if isinstance(payload, dict) else None
            inner = data.get("data", data) if isinstance(data, dict) else None
            if isinstance(inner, dict) and ("sip_code" in inner or "call_end_event" in inner or "session_id" in inner):
                call_out = inner
                break

    payload_in = run.get("data") if isinstance(run.get("data"), dict) else {}
    level = parse_level(payload_in.get("nivel_gravedad"), level)
    return {
        "level": level,
        "call": map_call(run, session, call_out).call_status,
        "contain": map_contain(nodes, call_out),
        "run_id": run_id,
        "session_id": (session or {}).get("id"),
        "hr_status": run.get("status"),
        "source": "happyrobot",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--level", type=int, default=4)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=1.5)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    env = load_env()
    if not env.get("HAPPYROBOT_API_KEY"):
        raise SystemExit("HAPPYROBOT_API_KEY missing")

    write_status(
        {
            "level": args.level,
            "call": "ringing",
            "contain": "idle",
            "run_id": args.run_id,
            "source": "happyrobot",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    deadline = time.time() + args.timeout
    last = ""
    while True:
        status = snapshot(env, args.run_id, args.level)
        blob = json.dumps(status, sort_keys=True)
        write_status(status)
        if blob != last:
            print(
                f"{status.get('call')} contain={status.get('contain')} "
                f"hr={status.get('hr_status')} run={args.run_id[:8]}…",
                flush=True,
            )
            last = blob
        if args.once or str(status.get("hr_status") or "").lower() in TERMINAL_RUN:
            return 0
        if time.time() >= deadline:
            print("watch timeout", flush=True)
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
