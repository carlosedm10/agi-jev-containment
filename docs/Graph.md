# Action Graph

A dynamic graph for tracing events. Every classified action materializes a node — the graph is the run's complete action sequence, benign included. The **key nodes** are the flagged subset (`jev` scores level ≥ 1); the JSONL log also keeps every raw event for forensics and replay.

On every new event, `jev` re-reads **short-term and long-term context in parallel** (it owns how to mix them):

* **Short-term** — the most recent nodes. A burst of dangerous nodes one after another, in a short window, is itself a risk signal.
* **Long-term** — the key-node history of the run. A later node that is only mildly bad still inherits extra weight if the run already had real problems, even if thirty harmless events sat in between.

How `jev` rewrites, promotes, or weights those nodes is `jev`'s job. We always hand it both contexts; we do not freeze old scores on our side. Request schema and how the two contexts map to `state`: [Jev.md](Jev.md).

* Dynamic: Starts empty and supports adding nodes at runtime.
* Single-rooted: exactly one root — the first node created; every run node hangs off it (`root → run:{run_id} → {run_id}:1 → {run_id}:2 → …`), created lazily by `ensure_run(run_id)`. `root` is an entry point, not a parent.
* Undirected: nodes keep `neighbors` — a **mutual** adjacency list: if `a` lists `b`, `b` lists `a`. There is no `parent`: a node can have any number of neighbors, and **loops are allowed**. `connect(src, dst)` adds a mutual edge between two existing nodes (duplicates and self-loops rejected). Traversals (`reachable()`) are cycle-safe (visited set), so a loop can never hang `save`/`load`.
* Runs are isolated by `run_id`, not by the graph: with undirected edges, traversal alone cannot tell runs apart, so a run's nodes are exactly the ones stamped with its `run_id` (in insertion order). Even explicit cross-run edges cannot leak one run's nodes into another's level or key-node history.
* Complete: one node per classified action — a `level_0_benign` verdict still materializes a `Level.NONE` node. The flagged subset is `key_nodes()` (level ≥ 1). Only unclassified events (degraded verdict — `jev` unreachable, [Jev.md](Jev.md)) stay tape-only.
* Node: Each node has a threshold and an optional associated tool (default: `None`). A materialized node also records `{run_id, level, intent, event, action_id, created_at}` — the evidence needed to replay a run and drive the playbooks ([Actions.md](Actions.md)).
* Singleton: A single shared instance manages the entire graph.
* Persistence: Supports efficient `save()` and `load()` operations. The snapshot stores the explicit `root` id plus, per node, its `neighbors` by id — so loops survive the roundtrip. All fields except the live `tool` object survive.
* Safety: Thread-safe operations to prevent concurrent access issues.
* Constraint: threshold must be a float between 0.0 and 1.0 (inclusive). It is `jev`'s `confidence` for the chain ending at this node ([Jev.md](Jev.md)); discrete levels 1–5 are derived from it ([Actions.md](Actions.md)).

Implemented in `backend/app/graph/`: `Node` lives in `models.py`, the `ActionGraph` manager and module-level `graph` singleton in `manager.py`, colocated tests under `tests/`.

### Run state is derived, not stored

There is no `Run` model. Everything the pipeline needs about a run is derived from the nodes stamped with the run's `run_id`:

- `graph.level(run_id)` — the run's effective level: `max` over the run's node levels (default `Level.NONE`). Escalate-only and L1-stickiness fall out of `max()` over an append-only structure — a run never downgrades, and `prior_level` for the next jev call is just this value.
- `graph.key_nodes(run_id)` — the run's *flagged* nodes (level ≥ 1) in insertion order; this is the `long_term` array handed to `jev` ([Jev.md](Jev.md)). All nodes, benign included, are `run_nodes(run_id)`.
- `graph.actionable_level(run_id)` — the max level among nodes whose `threshold` clears the action gate. A low-confidence L3 is recorded (the run level still reads L3) but does not fire a playbook until a confident verdict confirms it.

`append(run_id, …)` chains a new node under the run's last node with id `{run_id}:{seq}`; `connect(src, dst)` adds extra edges between existing nodes (this is how loops form); `update(node_id, **fields)` is how the dispatcher later stamps `action_id` on a node that fired a playbook; `clear()` resets the instance in place (a human clearing them from the viewer, [Actions.md](Actions.md)).

### Live stream

`GET /api/graph/stream` is a Server-Sent Events feed of the whole graph — every run, not one. Clients keep the graph in memory and never poll.

- **First message — `snapshot`**: `{revision, root, nodes}` with every node and its `neighbors` by id. Every serializable field travels; the live `tool` object never does.
- **Every later message — `update`**: `{revision, root, upsert_nodes, removed_node_ids}`. An upserted node carries its *complete* neighbor list, so applying it replaces the client's version of that node wholesale; edges are therefore never patched, only re-sent from both endpoints.
- **`revision`** increments by one per published change and is the client's gap detector: an update whose revision is not `previous + 1` means the client missed something and must reconnect.
- **One update per composite operation**: `append()` may create the root, the run node and the key node — subscribers see a single update, never a partial graph. Failed mutations publish nothing.
- **Subscribe is atomic**: the listener is registered and the snapshot captured under one lock acquisition, so no change can slip between "read the snapshot" and "start listening".
- **Slow clients are dropped**: each subscriber owns a bounded queue (64 updates); overflow ends that stream so the client reconnects and resynchronizes from a fresh snapshot. There is no replay buffer — reconnecting always starts from a new snapshot.

The hub is `backend/app/graph/stream.py` (one queue per client, subscribe/unsubscribe), the endpoint `backend/app/graph/router.py`. `useGraphStream()` in `frontend/src/graph/` mirrors the stream in memory; `frontend/src/live/` renders that mirror at `/live` (`chainEdges()` derives each run's path `run:{run_id} → {run_id}:1 → {run_id}:2 …` from node ids and animates it, coloured by the run's escalate-only level). The dashboard at `/` uses mock data instead: its React Flow panel renders protocol-compatible classified nodes plus separate provisional “Awaiting Jev” overlays. Mutual adjacency is deduplicated into undirected edges, with stable per-run columns and zoom/fit controls. Selection reveals the verdict and associated protective trace; no mock control sends API requests.

### Example

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.classification.models import Level


@dataclass
class Node:
    id: str
    neighbors: list["Node"] = field(default_factory=list)  # mutual (undirected)
    threshold: float = 0.0  # Range: [0.0, 1.0]
    tool: Optional[Any] = None
    run_id: Optional[str] = None
    level: Level = Level.NONE
    intent: Optional[str] = None
    event: Optional[dict[str, Any]] = None
    action_id: Optional[str] = None
    created_at: Optional[datetime] = None
```
