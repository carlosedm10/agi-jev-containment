from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.classification.models import Level
from app.config import settings
from app.graph.models import Node

_UPDATABLE_FIELDS = frozenset({"level", "threshold", "intent", "event", "action_id"})


class ActionGraph:
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
        connect: Node | None = None,
        threshold: float = 0.0,
        tool: Any | None = None,
        **fields: Any,
    ) -> Node:
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"node id must be a non-empty string, got {node_id!r}")
        value = _validate_threshold(threshold)

        with self._lock:
            if node_id in self._nodes:
                raise ValueError(f"node id already exists: {node_id!r}")
            if self._root_id is None:
                if connect is not None:
                    raise ValueError(
                        "graph is empty: the first node must be the root (connect=None)"
                    )
            elif connect is None:
                raise ValueError(f"root already exists ({self._root_id!r}): connect is required")
            elif self._nodes.get(connect.id) is not connect:
                raise ValueError(f"connect target {connect.id!r} is not in the graph")

            node = Node(id=node_id, threshold=value, tool=tool, **fields)
            self._nodes[node_id] = node
            if connect is not None:
                connect.neighbors.append(node)
            else:
                self._root_id = node_id
            return node

    def connect(self, src: Node, dst: Node) -> None:
        """Add a directed edge src -> dst between two existing nodes (cycles allowed)."""
        with self._lock:
            if self._nodes.get(src.id) is not src:
                raise ValueError(f"source node {src.id!r} is not in the graph")
            if self._nodes.get(dst.id) is not dst:
                raise ValueError(f"destination node {dst.id!r} is not in the graph")
            if src is dst:
                raise ValueError("self-loops are not allowed")
            if dst in src.neighbors:
                raise ValueError(f"edge {src.id!r} -> {dst.id!r} already exists")
            src.neighbors.append(dst)

    def ensure_run(self, run_id: str) -> Node:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError(f"run id must be a non-empty string, got {run_id!r}")
        with self._lock:
            run_node = self._nodes.get(f"run:{run_id}")
            if run_node is not None:
                return run_node
            if self._root_id is None:
                self.add_node("root")
            root = self._nodes[self._root_id]
            return self.add_node(f"run:{run_id}", connect=root, run_id=run_id)

    def append(
        self,
        run_id: str,
        *,
        level: Level | int,
        threshold: float,
        intent: str | None = None,
        event: dict[str, Any] | None = None,
        action_id: str | None = None,
    ) -> Node:
        with self._lock:
            run_node = self.ensure_run(run_id)
            last = run_node
            seen = {run_node.id}
            while last.neighbors:
                nxt = last.neighbors[-1]
                if nxt.id in seen:  # cycle: stop, chain here
                    break
                seen.add(nxt.id)
                last = nxt
            seq = len(self._reachable(run_node)) + 1
            return self.add_node(
                f"{run_id}:{seq}",
                connect=last,
                threshold=threshold,
                run_id=run_id,
                level=Level(level),
                intent=intent,
                event=event,
                action_id=action_id,
                created_at=datetime.now(UTC),
            )

    def run_nodes(self, run_id: str) -> list[Node]:
        with self._lock:
            run_node = self._nodes.get(f"run:{run_id}")
            if run_node is None:
                return []
            return [run_node, *self._reachable(run_node)]

    def key_nodes(self, run_id: str) -> list[Node]:
        return [n for n in self.run_nodes(run_id) if n.level >= Level.MILD]

    def level(self, run_id: str) -> Level:
        return max((n.level for n in self.run_nodes(run_id)), default=Level.NONE)

    def actionable_level(self, run_id: str) -> Level:
        return max(
            (
                n.level
                for n in self.run_nodes(run_id)
                if n.threshold >= settings.action_gate
            ),
            default=Level.NONE,
        )

    def update(self, node_id: str, **fields: Any) -> Node:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown node fields: {sorted(unknown)!r}")
        if "threshold" in fields:
            fields["threshold"] = _validate_threshold(fields["threshold"])
        if "level" in fields:
            fields["level"] = Level(fields["level"])

        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise ValueError(f"node id does not exist: {node_id!r}")
            for name, value in fields.items():
                setattr(node, name, value)
            return node

    def clear(self) -> None:
        with self._lock:
            self._nodes = {}
            self._root_id = None

    def save(self, path: str | Path) -> None:
        with self._lock:
            payload = {
                "root": self._root_id,
                "nodes": [_node_row(node) for node in self._nodes.values()],
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
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        root_id = data.get("root")
        rows = data["nodes"]

        with self._lock:
            created: dict[str, Node] = {}
            for row in rows:
                node = Node(
                    id=row["id"],
                    threshold=_validate_threshold(row["threshold"]),
                    run_id=row.get("run_id"),
                    level=Level(row.get("level", 0)),
                    intent=row.get("intent"),
                    event=row.get("event"),
                    action_id=row.get("action_id"),
                    created_at=(
                        datetime.fromisoformat(row["created_at"]) if "created_at" in row else None
                    ),
                )
                created[node.id] = node

            for row in rows:
                node = created[row["id"]]
                seen: set[str] = set()
                for neighbor_id in row.get("neighbors", []):
                    if neighbor_id == node.id:
                        raise ValueError(f"snapshot contains a self-loop on {node.id!r}")
                    if neighbor_id in seen:
                        raise ValueError(
                            f"snapshot contains duplicate edge {node.id!r} -> {neighbor_id!r}"
                        )
                    seen.add(neighbor_id)
                    neighbor = created.get(neighbor_id)
                    if neighbor is None:
                        raise ValueError(f"snapshot references unknown neighbor {neighbor_id!r}")
                    node.neighbors.append(neighbor)

            if rows:
                if root_id is None:
                    raise ValueError("snapshot contains nodes but no root")
                if root_id not in created:
                    raise ValueError(f"snapshot root {root_id!r} is not among the nodes")
            else:
                root_id = None

            self._nodes = created
            self._root_id = root_id

    def _reachable(self, node: Node) -> list[Node]:
        """Cycle-safe DFS from node (excluded), in edge insertion order."""
        ordered: list[Node] = []
        visited: set[str] = {node.id}

        def visit(current: Node) -> None:
            for neighbor in current.neighbors:
                if neighbor.id in visited:
                    continue
                visited.add(neighbor.id)
                ordered.append(neighbor)
                visit(neighbor)

        visit(node)
        return ordered


def _node_row(node: Node) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": node.id,
        "neighbors": [n.id for n in node.neighbors],
        "threshold": node.threshold,
    }
    if node.run_id is not None:
        row["run_id"] = node.run_id
    if node.level != Level.NONE:
        row["level"] = int(node.level)
    if node.intent is not None:
        row["intent"] = node.intent
    if node.event is not None:
        row["event"] = node.event
    if node.action_id is not None:
        row["action_id"] = node.action_id
    if node.created_at is not None:
        row["created_at"] = node.created_at.isoformat()
    return row


def _validate_threshold(threshold: float) -> float:
    if isinstance(threshold, bool) or not isinstance(threshold, int | float):
        raise TypeError(f"threshold must be a float in [0.0, 1.0], got {threshold!r}")
    value = float(threshold)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"threshold must be in [0.0, 1.0], got {value}")
    return value


graph = ActionGraph()
