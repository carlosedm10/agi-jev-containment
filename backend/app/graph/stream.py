from __future__ import annotations

import asyncio
from typing import Any

from app.graph import graph
from app.graph.manager import GraphListener, GraphUpdate

MAX_QUEUE = 64


class Subscription:
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
                self.overflow.set()

        try:
            self._loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            pass

    async def receive(self) -> GraphUpdate | None:
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
    subscription = Subscription(asyncio.get_running_loop())
    snapshot = graph.subscribe(subscription.listener)
    return snapshot, subscription


def unsubscribe(subscription: Subscription) -> None:
    graph.unsubscribe(subscription.listener)
