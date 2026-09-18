import json
import threading

import pytest

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
