"""Tests for the graph streaming protocol: manager pub/sub, SSE hub, endpoint."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.graph import ActionGraph, stream
from app.graph.manager import GraphUpdate
from app.main import app  # noqa: F401 - mounts the graph router


def _ids(update: GraphUpdate) -> set[str]:
    return {node["id"] for node in update.upsert_nodes}


class Collector:
    def __init__(self) -> None:
        self.updates: list[GraphUpdate] = []

    def __call__(self, update: GraphUpdate) -> None:
        self.updates.append(update)


@pytest.fixture
def g() -> ActionGraph:
    """Fresh graph instance (not the singleton) for manager-level tests."""
    return ActionGraph()


# --------------------------------------------------------------------------- #


class TestManagerSubscription:
    async def test_subscribe_on_empty_graph(self, g: ActionGraph):
        snapshot = g.subscribe(Collector())
        assert snapshot == {"revision": 0, "root": None, "nodes": []}

    async def test_snapshot_captures_existing_graph(self, g: ActionGraph):
        root = g.add_node("root", tool=object())
        node = g.add_node(
            "run:r1:1", connect=root, run_id="r1", event={"event": "file_read"}
        )
        collector = Collector()
        snapshot = g.subscribe(collector)

        assert snapshot["revision"] == 2
        assert snapshot["root"] == "root"
        by_id = {n["id"]: n for n in snapshot["nodes"]}
        assert by_id["root"]["neighbors"] == ["run:r1:1"]
        assert by_id["run:r1:1"]["neighbors"] == ["root"]
        assert by_id["run:r1:1"]["run_id"] == "r1"
        assert by_id["run:r1:1"]["event"] == {"event": "file_read"}
        # The live tool object is never serialized.
        assert "tool" not in by_id["root"]

    async def test_updates_are_ordered_and_gapless(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        root = g.add_node("root")                          # 1
        left = g.add_node("left", connect=root)            # 2
        right = g.add_node("right", connect=root)          # 3
        g.connect(left, right)                             # 4
        g.update("left", intent="recon")                    # 5

        revisions = [u.revision for u in collector.updates]
        assert revisions == [1, 2, 3, 4, 5]
        assert all(
            collector.updates[i].revision == collector.updates[i - 1].revision + 1
            for i in range(1, len(revisions))
        )
        assert g.revision == 5

    async def test_add_node_upserts_connect_target_too(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        root = g.add_node("root")
        g.add_node("child", connect=root)

        first, second = collector.updates
        assert _ids(first) == {"root"}
        assert _ids(second) == {"child", "root"}
        assert second.upsert_nodes[1]["neighbors"] == ["child"]

    async def test_connect_upserts_both_endpoints(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        root = g.add_node("root")
        a = g.add_node("a", connect=root)
        b = g.add_node("b", connect=root)
        collector.updates.clear()

        g.connect(a, b)
        (update,) = collector.updates
        assert _ids(update) == {"a", "b"}
        by_id = {n["id"]: n for n in update.upsert_nodes}
        assert by_id["a"]["neighbors"] == ["root", "b"]
        assert by_id["b"]["neighbors"] == ["root", "a"]

    async def test_update_upserts_the_node(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        g.add_node("root")
        collector.updates.clear()

        g.update("root", threshold=0.9, intent="exfil")
        (update,) = collector.updates
        assert _ids(update) == {"root"}
        assert update.upsert_nodes[0]["threshold"] == 0.9
        assert update.upsert_nodes[0]["intent"] == "exfil"

    async def test_failed_mutation_emits_nothing(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        g.add_node("root")
        collector.updates.clear()

        with pytest.raises(ValueError, match="already exists"):
            g.add_node("root")
        with pytest.raises(ValueError, match="does not exist"):
            g.update("ghost", intent="x")
        assert collector.updates == []
        assert g.revision == 1

    async def test_append_is_one_composite_update(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        collector.updates.clear()

        # First append on a virgin graph creates root + run node + key node.
        g.append("r1", level=2, threshold=0.8, intent="recon")
        (update,) = collector.updates
        assert _ids(update) == {"root", "run:r1", "r1:1"}

        collector.updates.clear()
        g.append("r2", level=1, threshold=0.5)
        (update,) = collector.updates
        # root is re-upserted too: it gained run:r2 as a neighbor.
        assert _ids(update) == {"root", "run:r2", "r2:1"}

    async def test_clear_reports_removed_ids(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        root = g.add_node("root")
        g.add_node("child", connect=root)
        collector.updates.clear()

        g.clear()
        (update,) = collector.updates
        assert update.root is None
        assert update.upsert_nodes == []
        assert set(update.removed_node_ids) == {"root", "child"}

    async def test_load_reports_removed_and_upserted(self, g: ActionGraph, tmp_path):
        root = g.add_node("root")
        stale = g.add_node("stale", connect=root)
        path = tmp_path / "snapshot.json"
        g.save(path)
        # A node created after the snapshot must be reported as removed.
        g.add_node("ghost", connect=root)
        collector = Collector()
        g.subscribe(collector)

        g.load(path)
        (update,) = collector.updates
        assert set(update.removed_node_ids) == {"ghost"}
        assert _ids(update) == {"root", "stale"}
        assert update.root == "root"
        assert stale.id in {n["id"] for n in update.upsert_nodes}

    async def test_unsubscribe_stops_delivery(self, g: ActionGraph):
        collector = Collector()
        g.subscribe(collector)
        g.unsubscribe(collector)
        g.add_node("root")
        assert collector.updates == []

    async def test_broken_listener_does_not_break_mutations(self, g: ActionGraph):
        def boom(update: GraphUpdate) -> None:
            raise RuntimeError("sink exploded")

        g.subscribe(boom)
        node = g.add_node("root")
        assert node.id == "root"
        assert g.revision == 1


# --------------------------------------------------------------------------- #


class TestSubscriptionHub:
    async def test_receive_delivers_updates_in_order(self):
        subscription = stream.Subscription(asyncio.get_running_loop())
        for i in range(3):
            subscription._on_update(
                GraphUpdate(revision=i + 1, root=None, upsert_nodes=[], removed_node_ids=[])
            )
        revisions = []
        for _ in range(3):
            update = await subscription.receive()
            assert update is not None
            revisions.append(update.revision)
        assert revisions == [1, 2, 3]

    async def test_slow_client_is_dropped_on_overflow(self):
        subscription = stream.Subscription(asyncio.get_running_loop())
        for i in range(stream.MAX_QUEUE + 1):
            subscription._on_update(
                GraphUpdate(revision=i + 1, root=None, upsert_nodes=[], removed_node_ids=[])
            )
        await asyncio.sleep(0)  # let the call_soon_threadsafe callbacks run
        assert subscription.overflow.is_set()
        assert await subscription.receive() is None


# --------------------------------------------------------------------------- #


async def _read_event(lines) -> tuple[str, dict[str, Any]]:
    """Consume SSE lines until one full event is parsed; return (event, data)."""
    event = ""
    data = ""
    async for line in lines:
        line = line.rstrip("\n")
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data = line.removeprefix("data: ")
        elif line == "" and event:
            return event, json.loads(data)
    raise AssertionError("stream ended before a full event arrived")


class TestStreamEndpoint:
    """Endpoint tests run against the singleton the router streams from, so
    revisions are asserted relative to the snapshot, never absolute."""

    async def test_snapshot_then_live_updates(self, client, fresh_graph: ActionGraph):
        fresh_graph.add_node("root", threshold=0.4)
        async with client.stream("GET", "/api/graph/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            lines = response.aiter_lines()
            event, data = await _read_event(lines)
            assert event == "snapshot"
            assert data["revision"] == fresh_graph.revision
            assert data["root"] == "root"
            assert data["nodes"][0]["id"] == "root"
            base = data["revision"]

            # A mutation after connecting arrives as an ordered update.
            fresh_graph.append("r1", level=2, threshold=0.8, intent="recon")
            event, data = await _read_event(lines)
            assert event == "update"
            assert data["revision"] == base + 1
            assert {"root", "run:r1", "r1:1"} <= {n["id"] for n in data["upsert_nodes"]}
            assert data["root"] == "root"

    async def test_empty_graph_snapshot(self, client, fresh_graph: ActionGraph):
        async with client.stream("GET", "/api/graph/stream") as response:
            event, data = await _read_event(response.aiter_lines())
            assert event == "snapshot"
            assert data == {"revision": fresh_graph.revision, "root": None, "nodes": []}

    async def test_multiple_clients_each_get_updates(self, client, fresh_graph: ActionGraph):
        async with client.stream("GET", "/api/graph/stream") as first, client.stream(
            "GET", "/api/graph/stream"
        ) as second:
            await _read_event(first.aiter_lines())
            await _read_event(second.aiter_lines())
            base = fresh_graph.revision

            fresh_graph.add_node("root")
            for response in (first, second):
                event, data = await _read_event(response.aiter_lines())
                assert event == "update"
                assert data["revision"] == base + 1
                assert [n["id"] for n in data["upsert_nodes"]] == ["root"]

    async def test_disconnect_unsubscribes(self, client, fresh_graph: ActionGraph):
        async with client.stream("GET", "/api/graph/stream") as response:
            await _read_event(response.aiter_lines())
            assert len(fresh_graph._listeners) == 1
        assert fresh_graph._listeners == []
