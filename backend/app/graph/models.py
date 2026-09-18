from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    id: str
    parent: Node | None = None
    children: list[Node] = field(default_factory=list)
    threshold: float = 0.0  # Range: [0.0, 1.0]
    tool: Any | None = None
