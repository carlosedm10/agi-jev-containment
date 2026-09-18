"""Action Graph — a dynamic, thread-safe tree of Nodes for tracing events.

The graph starts empty. The first node added becomes the root; every node
added afterwards must name an existing node as its parent, so the graph is
always a single tree. Persistence is a JSON snapshot of the graph structure;
``Node.tool`` is a live runtime object and is not serialized — reattach
tools after ``load()``.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.graph.models import Node


class ActionGraph:
    """Singleton-managed tree of Nodes. Use the module-level ``graph`` instance."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, Node] = {}
        self._root_id: str | None = None

    @property
    def root(self) -> Node | None:
        with self._lock:
            return self._nodes.get(self._root_id) if self._root_id else None

    @property
    def nodes(self) -> list[Node]:
        with self._lock:
            return list(self._nodes.values())

    def get_node(self, node_id: str) -> Node | None:
        with self._lock:
            return self._nodes.get(node_id)

    def add_node(
        self,
        node_id: str,
        parent: Node | None = None,
        threshold: float = 0.0,
        tool: Any | None = None,
    ) -> Node:
        """Add a node and attach it to its parent. Returns the new node."""
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"node id must be a non-empty string, got {node_id!r}")
        value = _validate_threshold(threshold)

        with self._lock:
            if node_id in self._nodes:
                raise ValueError(f"node id already exists: {node_id!r}")
            if self._root_id is None:
                if parent is not None:
                    raise ValueError(
                        "graph is empty: the first node must be the root (parent=None)"
                    )
            elif parent is None:
                raise ValueError(f"root already exists ({self._root_id!r}): parent is required")
            elif parent.id not in self._nodes:
                raise ValueError(f"parent {parent.id!r} is not in the graph")

            node = Node(id=node_id, parent=parent, threshold=value, tool=tool)
            self._nodes[node_id] = node
            if parent is not None:
                parent.children.append(node)
            else:
                self._root_id = node_id
            return node

    def save(self, path: str | Path) -> None:
        """Write the graph structure to a JSON file (atomically)."""
        with self._lock:
            payload = {
                "nodes": [
                    {
                        "id": node.id,
                        "parent": node.parent.id if node.parent else None,
                        "threshold": node.threshold,
                    }
                    for node in self._nodes.values()
                ]
            }

        target = Path(path)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, target)
        except BaseException:
            os.unlink(tmp)
            raise

    def load(self, path: str | Path) -> None:
        """Replace the current graph with the snapshot stored at ``path``."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = data["nodes"]

        with self._lock:
            created: dict[str, Node] = {}
            for row in rows:
                node = Node(id=row["id"], threshold=_validate_threshold(row["threshold"]))
                created[node.id] = node

            roots = 0
            root_id: str | None = None
            for row in rows:
                node = created[row["id"]]
                parent_id = row["parent"]
                if parent_id is not None:
                    parent = created.get(parent_id)
                    if parent is None:
                        raise ValueError(f"snapshot references unknown parent {parent_id!r}")
                    node.parent = parent
                    parent.children.append(node)
                else:
                    roots += 1
                    if roots > 1:
                        raise ValueError("snapshot contains more than one root")
                    root_id = row["id"]

            self._nodes = created
            self._root_id = root_id


def _validate_threshold(threshold: float) -> float:
    """Constraint: threshold must be a float between 0.0 and 1.0 (inclusive)."""
    if isinstance(threshold, bool) or not isinstance(threshold, int | float):
        raise TypeError(f"threshold must be a float in [0.0, 1.0], got {threshold!r}")
    value = float(threshold)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"threshold must be in [0.0, 1.0], got {value}")
    return value


graph = ActionGraph()
