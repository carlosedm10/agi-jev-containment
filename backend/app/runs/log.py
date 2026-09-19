from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import settings

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _path(run_id: str) -> Path:
    return Path(settings.run_log_dir) / f"{_UNSAFE.sub('_', run_id)}.jsonl"


def append(run_id: str, event: dict[str, Any]) -> None:
    path = _path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def count(run_id: str) -> int:
    path = _path(run_id)
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def tail(run_id: str, n: int) -> list[dict[str, Any]]:
    path = _path(run_id)
    if not path.exists() or n <= 0:
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-n:] if line.strip()]


def list_runs() -> list[str]:
    root = Path(settings.run_log_dir)
    if not root.exists():
        return []
    return sorted(path.stem for path in root.glob("*.jsonl"))
