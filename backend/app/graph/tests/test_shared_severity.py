from app.classification.models import Level
from app.graph.manager import ActionGraph


def test_shared_action_keeps_run_severity_and_context_isolated_after_reload(tmp_path):
    graph = ActionGraph()
    action = {"kind": "file_read", "tool": "read_file", "target": "/report.txt"}
    old = graph.append("old", level=5, threshold=0.99, event={**action, "id": "old:e1"})
    current = graph.append("new", level=0, threshold=0.8, event={**action, "id": "new:e1"})
    assert current is old
    assert graph.level("old") == Level.CATASTROPHIC
    assert graph.level("new") == Level.NONE
    assert graph.key_nodes("new") == []
    assert graph.key_nodes("old")[0].event["id"] == "old:e1"
    graph.append("new", level=3, threshold=0.9, event={**action, "id": "new:e2"})
    path = tmp_path / "graph.json"
    graph.save(path)
    restored = ActionGraph()
    restored.load(path)
    assert restored.level("new") == Level.SEVERE
    assert restored.actionable_level("new") == Level.SEVERE
    assert restored.level("old") == Level.CATASTROPHIC
    assert restored.key_nodes("new")[0].event["id"] == "new:e2"
