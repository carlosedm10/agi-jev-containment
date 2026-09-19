# Action Graph

A dynamic graph for tracing events. The full JSONL log keeps every event; this graph only keeps **key nodes** — anything `jev` scores at level ≥ 1. Harmless chatter stays in the log so the viewer is not a wall of noise.

On every new event, `jev` re-reads **short-term and long-term context in parallel** (it owns how to mix them):

* **Short-term** — the most recent nodes. A burst of dangerous nodes one after another, in a short window, is itself a risk signal.
* **Long-term** — the key-node history of the run. A later node that is only mildly bad still inherits extra weight if the run already had real problems, even if thirty harmless events sat in between.

How `jev` rewrites, promotes, or weights those nodes is `jev`'s job. We always hand it both contexts; we do not freeze old scores on our side. Request schema and how the two contexts map to `state`: [Jev.md](Jev.md).

* Dynamic: Starts empty and supports adding nodes at runtime.
* Sparse: a node is materialized only when `jev` returns level ≥ 1. Below that, the event exists only in JSONL.
* Node: Each node has exactly one parent (except the root), zero or more children, a threshold, and an optional associated tool (default: `None`).
* Singleton: A single shared instance manages the entire graph.
* Persistence: Supports efficient `save()` and `load()` operations.
* Safety: Thread-safe operations to prevent concurrent access issues.
* Constraint: threshold must be a float between 0.0 and 1.0 (inclusive). It is `jev`'s intent score for the chain ending at this node; discrete levels 1–5 are derived from it ([Actions.md](Actions.md)).

Implemented in `backend/app/graph/`: `Node` lives in `models.py`, the `ActionGraph` manager and module-level `graph` singleton in `manager.py`, colocated tests under `tests/`.

### Example

```python
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class Node:
    id: str
    parent: Optional["Node"] = None
    children: list["Node"] = field(default_factory=list)
    threshold: float = 0.0 # Range: [0.0, 1.0]
    tool: Optional[Any] = None
```
