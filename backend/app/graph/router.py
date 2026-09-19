from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.graph import stream

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.get("/stream")
async def graph_stream() -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        snapshot, subscription = stream.subscribe()
        try:
            yield _sse("snapshot", snapshot)
            while True:
                update = await subscription.receive()
                if update is None:
                    break
                yield _sse(
                    "update",
                    {
                        "revision": update.revision,
                        "root": update.root,
                        "upsert_nodes": update.upsert_nodes,
                        "removed_node_ids": update.removed_node_ids,
                    },
                )
        finally:
            stream.unsubscribe(subscription)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
