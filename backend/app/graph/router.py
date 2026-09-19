from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.graph import stream

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # never buffer the stream in a reverse proxy
}


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.get("/stream")
async def graph_stream() -> StreamingResponse:
    """Server-Sent Events feed of the whole graph.

    The first message is a full ``snapshot`` ({revision, root, nodes}); every
    later message is an ``update`` ({revision, root, upsert_nodes,
    removed_node_ids}). Updates are ordered, gapless and grouped per composite
    graph operation. A slow client is disconnected so it resynchronizes with a
    fresh snapshot; a disconnected client is unsubscribed.
    """

    async def event_stream() -> AsyncIterator[str]:
        snapshot, subscription = stream.subscribe()
        try:
            yield _sse("snapshot", snapshot)
            while True:
                update = await subscription.receive()
                if update is None:  # overflow: client must reconnect
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
