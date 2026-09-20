#!/usr/bin/env python3
"""POST /api/demo/trigger on the local origin. Public links use CD_URL."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    api = os.environ.get("CD_API_URL", "http://127.0.0.1:8000").rstrip("/")
    public = os.environ.get("CD_URL", "https://jervis.palistapp.com").rstrip("/")
    body: dict[str, object] = {"delay_ms": int(os.environ.get("DELAY_MS") or "1800")}
    scenario = os.environ.get("SCENARIO") or ""
    if scenario:
        body["scenario"] = scenario
    request = urllib.request.Request(
        f"{api}/api/demo/trigger",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(exc.read().decode() + "\n")
        return min(exc.code, 255)
    except urllib.error.URLError as exc:
        sys.stderr.write(f"{exc.reason}\n")
        return 1
    print(json.dumps(data))
    run_id = data.get("run_id") or ""
    print(f"dashboard: {public}/?run={run_id}")
    print(f"trace: {public}/trace?run={run_id}")
    print(f"ladder: {public}/ladder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
