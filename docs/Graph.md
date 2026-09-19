# Action Graph

A dynamic graph for tracing events. The full JSONL log keeps every event; this graph only keeps **key nodes** — anything `jev` scores at level ≥ 1. Harmless chatter stays in the log so the viewer is not a wall of noise.

On every new event, `jev` re-reads **short-term and long-term context in parallel** (it owns how to mix them):

* **Short-term** — the most recent nodes. A burst of dangerous nodes one after another, in a short window, is itself a risk signal.
* **Long-term** — the key-node history of the run. A later node that is only mildly bad still inherits extra weight if the run already had real problems, even if thirty harmless events sat in between.

How `jev` rewrites, promotes, or weights those nodes is `jev`'s job. We always hand it both contexts; we do not freeze old scores on our side. Request schema and how the two contexts map to `state`: [Jev.md](Jev.md).

* Dynamic: Starts empty and supports adding nodes at runtime.
* Single-rooted: exactly one root — the first node created; every run hangs off it (`root → run:{run_id} → {run_id}:1 → {run_id}:2 → …`), created lazily by `ensure_run(run_id)`. `root` is an entry point, not a parent: nothing forbids other edges into or out of it.
* A graph, not a tree: nodes keep `neighbors` — the list of nodes they point to (directed adjacency list). There is no `parent`: a node may have any number of predecessors, and **cycles are allowed**. `connect(src, dst)` adds a directed edge between two existing nodes (duplicates and self-loops rejected), back-edges included. Every traversal is cycle-safe (visited set), so a cycle can never hang `run_nodes`, `append`, or `save`/`load`.
* Sparse: a node is materialized only when `jev` returns level ≥ 1. Below that (`level_0_benign`, [Jev.md](Jev.md)), the event exists only in JSONL.
* Node: Each node has a threshold and an optional associated tool (default: `None`). A materialized node also records `{run_id, level, intent, event, action_id, created_at}` — the evidence needed to replay a run and drive the playbooks ([Actions.md](Actions.md)).
* Singleton: A single shared instance manages the entire graph.
* Persistence: Supports efficient `save()` and `load()` operations. The snapshot stores the explicit `root` id plus, per node, its outgoing `neighbors` by id — so cycles survive the roundtrip. All fields except the live `tool` object survive.
* Safety: Thread-safe operations to prevent concurrent access issues.
* Constraint: threshold must be a float between 0.0 and 1.0 (inclusive). It is `jev`'s `confidence` for the chain ending at this node ([Jev.md](Jev.md)); discrete levels 1–5 are derived from it ([Actions.md](Actions.md)).

Implemented in `backend/app/graph/`: `Node` lives in `models.py`, the `ActionGraph` manager and module-level `graph` singleton in `manager.py`, colocated tests under `tests/`.

### Run state is derived, not stored

There is no `Run` model. Everything the pipeline needs about a run is derived from the append-only subgraph reachable from the run node:

- `graph.level(run_id)` — the run's effective level: `max` over the reachable subgraph's node levels (default `Level.NONE`). Escalate-only and L1-stickiness fall out of `max()` over an append-only structure — a run never downgrades, and `prior_level` for the next jev call is just this value.
- `graph.key_nodes(run_id)` — the reachable nodes in insertion order; this is the `long_term` array handed to `jev` ([Jev.md](Jev.md)).
- `graph.actionable_level(run_id)` — the max level among nodes whose `threshold` clears the action gate. A low-confidence L3 is recorded (the run level still reads L3) but does not fire a playbook until a confident verdict confirms it.

`append(run_id, …)` chains a new key node under the run's last node with id `{run_id}:{seq}`; `connect(src, dst)` adds extra edges between existing nodes (this is how cycles form); `update(node_id, **fields)` is how the dispatcher later stamps `action_id` on a node that fired a playbook; `clear()` resets the instance in place (a human clearing them from the viewer, [Actions.md](Actions.md)).

### Example

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.classification.models import Level


@dataclass
class Node:
    id: str
    neighbors: list["Node"] = field(default_factory=list)  # directed: outgoing edges
    threshold: float = 0.0  # Range: [0.0, 1.0]
    tool: Optional[Any] = None
    run_id: Optional[str] = None
    level: Level = Level.NONE
    intent: Optional[str] = None
    event: Optional[dict[str, Any]] = None
    action_id: Optional[str] = None
    created_at: Optional[datetime] = None
```
