import json
import threading

import pytest

from app.classification.models import Level
from app.graph import ActionGraph, Node, graph


@pytest.fixture
def g() -> ActionGraph:
    return ActionGraph()


class TestAddNode:
    def test_empty_graph_starts_with_no_root(self, g: ActionGraph):
        assert g.root is None
        assert g.nodes == []

    def test_first_node_becomes_root(self, g: ActionGraph):
        root = g.add_node("root", threshold=0.5)
        assert g.root is root
        assert root.parent is None
        assert root.children == []
        assert root.threshold == 0.5
        assert root.tool is None

    def test_second_root_rejected(self, g: ActionGraph):
        g.add_node("root")
        with pytest.raises(ValueError, match="root already exists"):
            g.add_node("another-root")

    def test_root_cannot_have_parent_in_empty_graph(self, g: ActionGraph):
        with pytest.raises(ValueError, match="first node must be the root"):
            g.add_node("orphan", parent=Node(id="ghost"))

    def test_child_links_to_parent(self, g: ActionGraph):
        root = g.add_node("root")
        tool = object()
        child = g.add_node("child", parent=root, threshold=1.0, tool=tool)
        assert child.parent is root
        assert root.children == [child]
        assert child.tool is tool

    def test_duplicate_id_rejected(self, g: ActionGraph):
        g.add_node("root")
        with pytest.raises(ValueError, match="already exists"):
            g.add_node("root")

    def test_unknown_parent_rejected(self, g: ActionGraph):
        g.add_node("root")
        with pytest.raises(ValueError, match="not in the graph"):
            g.add_node("child", parent=Node(id="ghost"))

    @pytest.mark.parametrize("threshold", [0.0, 1.0, 0.42])
    def test_threshold_bounds_inclusive(self, g: ActionGraph, threshold: float):
        node = g.add_node("n", threshold=threshold)
        assert node.threshold == threshold

    @pytest.mark.parametrize("threshold", [-0.1, 1.1, 100, "0.5", None, True])
    def test_threshold_out_of_range_or_wrong_type(self, g: ActionGraph, threshold):
        with pytest.raises((TypeError, ValueError), match="threshold"):
            g.add_node("n", threshold=threshold)

    def test_empty_id_rejected(self, g: ActionGraph):
        with pytest.raises(ValueError, match="non-empty string"):
            g.add_node("")

    def test_get_node(self, g: ActionGraph):
        node = g.add_node("root")
        assert g.get_node("root") is node
        assert g.get_node("missing") is None


class TestPersistence:
    def test_save_load_roundtrip(self, g: ActionGraph, tmp_path):
        root = g.add_node("root", threshold=0.1)
        left = g.add_node("left", parent=root, threshold=0.5)
        g.add_node("right", parent=root, threshold=0.9)
        g.add_node("leaf", parent=left, threshold=0.0)

        path = tmp_path / "graph.json"
        g.save(path)
        assert json.loads(path.read_text())["nodes"][0] == {
            "id": "root",
            "parent": None,
            "threshold": 0.1,
        }

        restored = ActionGraph()
        restored.load(path)
        assert [n.id for n in restored.nodes] == ["root", "left", "right", "leaf"]
        assert {n.id: n.threshold for n in restored.nodes} == {
            "root": 0.1,
            "left": 0.5,
            "right": 0.9,
            "leaf": 0.0,
        }
        assert restored.root is restored.get_node("root")
        assert [c.id for c in restored.get_node("root").children] == ["left", "right"]
        assert restored.get_node("leaf").parent is restored.get_node("left")

    def test_save_empty_graph(self, g: ActionGraph, tmp_path):
        path = tmp_path / "empty.json"
        g.save(path)
        assert json.loads(path.read_text()) == {"nodes": []}

        restored = ActionGraph()
        restored.load(path)
        assert restored.root is None
        assert restored.nodes == []

    def test_save_leaves_no_temp_files(self, g: ActionGraph, tmp_path):
        path = tmp_path / "graph.json"
        g.add_node("root")
        g.save(path)
        assert list(tmp_path.iterdir()) == [path]

    def test_tool_is_not_persisted(self, g: ActionGraph, tmp_path):
        g.add_node("root", tool=object())
        path = tmp_path / "graph.json"
        g.save(path)

        restored = ActionGraph()
        restored.load(path)
        assert restored.get_node("root").tool is None

    def test_load_replaces_existing_graph(self, g: ActionGraph, tmp_path):
        g.add_node("old-root")
        other = ActionGraph()
        other.add_node("new-root")

        path = tmp_path / "graph.json"
        other.save(path)
        g.load(path)

        assert [n.id for n in g.nodes] == ["new-root"]
        assert g.root.id == "new-root"

    def test_load_rejects_snapshot_with_unknown_parent(self, g: ActionGraph, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"nodes": [{"id": "a", "parent": "ghost", "threshold": 0.0}]}))
        with pytest.raises(ValueError, match="unknown parent"):
            g.load(path)

    def test_failed_load_preserves_current_graph(self, g: ActionGraph, tmp_path):
        g.add_node("keeper")
        path = tmp_path / "bad.json"
        path.write_text(
            json.dumps(
                {
                    "nodes": [
                        {"id": "a", "parent": None, "threshold": 0.0},
                        {"id": "b", "parent": "ghost", "threshold": 0.0},
                    ]
                }
            )
        )
        with pytest.raises(ValueError):
            g.load(path)
        assert [n.id for n in g.nodes] == ["keeper"]
        assert g.root.id == "keeper"

    def test_load_rejects_snapshot_with_two_roots(self, g: ActionGraph, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(
            json.dumps(
                {
                    "nodes": [
                        {"id": "a", "parent": None, "threshold": 0.0},
                        {"id": "b", "parent": None, "threshold": 0.0},
                    ]
                }
            )
        )
        with pytest.raises(ValueError, match="more than one root"):
            g.load(path)


class TestThreadSafety:
    def test_concurrent_adds(self, g: ActionGraph):
        root = g.add_node("root")
        errors: list[Exception] = []

        def add(i: int) -> None:
            try:
                g.add_node(f"node-{i}", parent=root)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=add, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(g.nodes) == 101
        assert len(root.children) == 100


class TestSingleton:
    def test_module_level_instance_is_shared(self):
        assert isinstance(graph, ActionGraph)
        assert ActionGraph() is not graph


class TestRunSubtrees:
    def test_ensure_run_creates_root_and_run_node(self, g: ActionGraph):
        run_node = g.ensure_run("r1")
        assert g.root.id == "root"
        assert run_node.id == "run:r1"
        assert run_node.parent is g.root
        assert run_node.run_id == "r1"
        assert run_node.level == Level.NONE

    def test_ensure_run_is_idempotent(self, g: ActionGraph):
        first = g.ensure_run("r1")
        second = g.ensure_run("r1")
        assert first is second
        assert len(g.nodes) == 2

    def test_runs_share_the_single_root(self, g: ActionGraph):
        a = g.ensure_run("a")
        b = g.ensure_run("b")
        assert g.root.children == [a, b]
        assert a.parent is g.root and b.parent is g.root

    def test_ensure_run_rejects_empty_id(self, g: ActionGraph):
        with pytest.raises(ValueError, match="non-empty"):
            g.ensure_run("")

    def test_append_chains_under_the_run_node(self, g: ActionGraph):
        run_node = g.ensure_run("r")
        n1 = g.append("r", level=Level.MILD, threshold=0.9, intent="recon")
        n2 = g.append("r", level=Level.SEVERE, threshold=0.8, intent="exfiltrate_secrets")
        assert [n1.id, n2.id] == ["r:1", "r:2"]
        assert n1.parent is run_node
        assert n2.parent is n1
        assert run_node.children == [n1]
        assert n1.run_id == "r" and n2.run_id == "r"

    def test_append_creates_the_run_lazily(self, g: ActionGraph):
        node = g.append("r", level=Level.MILD, threshold=0.9)
        assert g.root.id == "root"
        assert node.parent is g.get_node("run:r")

    def test_append_validates_threshold(self, g: ActionGraph):
        with pytest.raises(ValueError, match="threshold"):
            g.append("r", level=Level.MILD, threshold=1.5)

    def test_append_rejects_non_level(self, g: ActionGraph):
        with pytest.raises(ValueError):
            g.append("r", level=99, threshold=0.9)

    def test_run_nodes_in_order_and_isolated_per_run(self, g: ActionGraph):
        g.ensure_run("a")
        g.ensure_run("b")
        a1 = g.append("a", level=Level.MILD, threshold=0.9)
        g.append("b", level=Level.MODERATE, threshold=0.9)
        a2 = g.append("a", level=Level.SEVERE, threshold=0.9)
        assert [n.id for n in g.run_nodes("a")] == ["run:a", "a:1", "a:2"]
        assert [n.id for n in g.run_nodes("b")] == ["run:b", "b:1"]
        assert g.run_nodes("a") == [g.get_node("run:a"), a1, a2]
        assert g.run_nodes("missing") == []

    def test_key_nodes_exclude_sub_mild_levels(self, g: ActionGraph):
        g.ensure_run("r")
        n1 = g.append("r", level=Level.MILD, threshold=0.9)
        g.append("r", level=Level.NONE, threshold=0.9)
        n3 = g.append("r", level=Level.SEVERE, threshold=0.9)
        assert g.key_nodes("r") == [n1, n3]

    def test_level_is_max_over_the_run(self, g: ActionGraph):
        g.ensure_run("r")
        assert g.level("r") == Level.NONE
        g.append("r", level=Level.MILD, threshold=0.9)
        g.append("r", level=Level.SEVERE, threshold=0.9)
        g.append("r", level=Level.MODERATE, threshold=0.9)
        assert g.level("r") == Level.SEVERE
        assert g.level("missing") == Level.NONE

    def test_actionable_level_holds_then_releases(self, g: ActionGraph):
        g.ensure_run("r")
        g.append("r", level=Level.SEVERE, threshold=0.5)
        assert g.level("r") == Level.SEVERE
        assert g.actionable_level("r") == Level.NONE
        g.append("r", level=Level.SEVERE, threshold=0.9)
        assert g.actionable_level("r") == Level.SEVERE

    def test_actionable_level_gate_is_inclusive(self, g: ActionGraph):
        g.ensure_run("r")
        g.append("r", level=Level.MODERATE, threshold=0.7)
        assert g.actionable_level("r") == Level.MODERATE
        g.append("r", level=Level.SEVERE, threshold=0.69)
        assert g.actionable_level("r") == Level.MODERATE

    def test_clear_resets_the_instance_in_place(self, g: ActionGraph):
        g.ensure_run("r")
        g.append("r", level=Level.MILD, threshold=0.9)
        g.clear()
        assert g.root is None
        assert g.nodes == []
        assert g.get_node("run:r") is None


class TestUpdate:
    def test_update_sets_documented_fields(self, g: ActionGraph):
        node = g.append("r", level=Level.MILD, threshold=0.9)
        updated = g.update(node.id, level=Level.SEVERE, intent="lateral_movement", action_id="a1")
        assert updated.level == Level.SEVERE
        assert updated.intent == "lateral_movement"
        assert updated.action_id == "a1"

    def test_update_rejects_bad_threshold(self, g: ActionGraph):
        node = g.add_node("n")
        with pytest.raises(ValueError, match="threshold"):
            g.update(node.id, threshold=-1)

    def test_update_unknown_node_raises(self, g: ActionGraph):
        with pytest.raises(ValueError, match="does not exist"):
            g.update("ghost", level=Level.MILD)

    def test_update_unknown_field_raises(self, g: ActionGraph):
        node = g.add_node("n")
        with pytest.raises(ValueError, match="unknown node fields"):
            g.update(node.id, parent=None)


class TestRunPersistence:
    def test_save_load_roundtrip_preserves_run_fields(self, g: ActionGraph, tmp_path):
        g.ensure_run("r")
        n1 = g.append("r", level=Level.MILD, threshold=0.9, intent="recon", event={"event": "file_read"})
        g.append("r", level=Level.SEVERE, threshold=0.8, action_id="a1")

        path = tmp_path / "graph.json"
        g.save(path)
        restored = ActionGraph()
        restored.load(path)

        r1 = restored.get_node("r:1")
        r2 = restored.get_node("r:2")
        assert r1.run_id == "r" and r2.run_id == "r"
        assert r1.level == Level.MILD and r2.level == Level.SEVERE
        assert r1.intent == "recon"
        assert r1.event == {"event": "file_read"}
        assert r2.action_id == "a1"
        assert r1.created_at == n1.created_at
        assert r2.parent is r1
        assert restored.level("r") == Level.SEVERE
        assert [n.id for n in restored.key_nodes("r")] == ["r:1", "r:2"]

    def test_save_load_roundtrip_preserves_created_at_on_update(self, g: ActionGraph, tmp_path):
        node = g.append("r", level=Level.MILD, threshold=0.9)
        g.update(node.id, level=Level.SEVERE, intent="recon")
        path = tmp_path / "graph.json"
        g.save(path)
        restored = ActionGraph()
        restored.load(path)
        updated = restored.get_node(node.id)
        assert updated.level == Level.SEVERE
        assert updated.intent == "recon"
        assert updated.created_at == node.created_at

    def test_load_accepts_legacy_snapshot_without_new_fields(self, g: ActionGraph, tmp_path):
        path = tmp_path / "legacy.json"
        path.write_text(
            json.dumps({"nodes": [{"id": "root", "parent": None, "threshold": 0.5}]})
        )
        g.load(path)
        assert g.get_node("root").level == Level.NONE
        assert g.get_node("root").run_id is None

    def test_load_rejects_snapshot_with_nodes_but_no_root(self, g: ActionGraph, tmp_path):
        path = tmp_path / "orphan.json"
        path.write_text(
            json.dumps({"nodes": [{"id": "a", "parent": "missing-root", "threshold": 0.0}]})
        )
        with pytest.raises(ValueError):
            g.load(path)

    def test_load_rejects_parent_cycle_as_rootless(self, g: ActionGraph, tmp_path):
        path = tmp_path / "cycle.json"
        path.write_text(
            json.dumps({"nodes": [
                {"id": "a", "parent": "b", "threshold": 0.0},
                {"id": "b", "parent": "a", "threshold": 0.0},
            ]})
        )
        with pytest.raises(ValueError, match="no root"):
            g.load(path)
