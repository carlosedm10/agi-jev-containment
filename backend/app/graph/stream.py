"""SSE fan-out for the action graph.

Each subscriber owns a bounded asyncio queue. Graph mutations push one
:class:`~app.graph.manager.GraphUpdate` per composite operation; a subscriber
that cannot keep up (queue full) is marked closed so the stream ends and the
client resynchronizes with a fresh snapshot on reconnect.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.graph import graph
from app.graph.manager import GraphListener, GraphUpdate

# Bounded per-client queue: a client slower than 64 updates is dropped.
MAX_QUEUE = 64


class Subscription:
    """Per-client mailbox bridging graph mutations (any thread) to the SSE loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.queue: asyncio.Queue[GraphUpdate] = asyncio.Queue(maxsize=MAX_QUEUE)
        self.overflow = asyncio.Event()
        self.listener: GraphListener = self._on_update

    def _on_update(self, update: GraphUpdate) -> None:
        def deliver() -> None:
            try:
                self.queue.put_nowait(update)
            except asyncio.QueueFull:
                # Too slow: end the stream so the client reconnects and
                # resynchronizes from a fresh snapshot.
                self.overflow.set()

        try:
            self._loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            # The client's loop is already gone (disconnected mid-delivery).
            pass

    async def receive(self) -> GraphUpdate | None:
        """Next update, or None when the subscription was dropped (overflow)."""
        get_task = asyncio.create_task(self.queue.get())
        overflow_task = asyncio.create_task(self.overflow.wait())
        try:
            done, _ = await asyncio.wait(
                {get_task, overflow_task}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            get_task.cancel()
            overflow_task.cancel()
            raise
        overflow_task.cancel()
        if overflow_task in done and self.overflow.is_set():
            get_task.cancel()
            return None
        return get_task.result()


def subscribe() -> tuple[dict[str, Any], Subscription]:
    """Atomically register a subscriber and capture the initial snapshot."""
    subscription = Subscription(asyncio.get_running_loop())
    snapshot = graph.subscribe(subscription.listener)
    return snapshot, subscription


def unsubscribe(subscription: Subscription) -> None:
    graph.unsubscribe(subscription.listener)
