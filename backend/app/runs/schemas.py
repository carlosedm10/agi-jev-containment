from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EventIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str


class NodeOut(BaseModel):
    id: str
    level: int
    threshold: float
    intent: str | None = None
    action_id: str | None = None


class IngestOut(BaseModel):
    level: int
    confidence: float
    intent: str | None = None
    escalated: bool
    degraded: bool
    node_id: str | None = None


class RunOut(BaseModel):
    run_id: str
    level: int
    key_nodes: list[NodeOut]


class RunSummary(BaseModel):
    run_id: str
    level: int
    nodes: int
