# Action Graph

A dynamic graph for tracing events.

* Dynamic: Starts empty and supports adding nodes at runtime.
* Node: Each node has exactly one parent (except the root), zero or more children, a threshold, and an optional associated tool (default: `None`).
* Singleton: A single shared instance manages the entire graph.
* Persistence: Supports efficient `save()` and `load()` operations.
* Safety: Thread-safe operations to prevent concurrent access issues.
* Constraint: threshold must be a float between 0.0 and 1.0 (inclusive).

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
