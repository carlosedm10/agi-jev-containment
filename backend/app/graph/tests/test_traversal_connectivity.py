"""Every move the agent makes is an edge, whatever its causal references say."""

from itertools import pairwise

from app.classification.models import Level
from app.graph.manager import ActionGraph


def event(sequence: int, target: str, caused_by: list[str] | None = None):
    return {
        "id": f"run-1:e{sequence}",
        "sequence": sequence,
        "kind": "file_read",
        "tool": "read_file",
        "target": target,
        "content": f"Read {target}",
        "caused_by": caused_by or [],
    }


def walk(graph: ActionGraph, events: list[dict]) -> list[str]:
    return [
        graph.append("run-1", level=Level.NONE, threshold=1.0, event=payload).id
        for payload in events
    ]


def assert_every_move_is_an_edge(graph: ActionGraph, visited: list[str]) -> None:
    lookup = {node.id: node for node in graph.nodes}
    for previous, current in pairwise(visited):
        if previous == current:
            continue
        neighbours = {node.id for node in lookup[previous].neighbors}
        assert current in neighbours, f"moved {previous} -> {current} with no edge"


def test_a_backward_causal_reference_still_connects_to_where_the_run_came_from():
    """The case that regressed: caused_by pointing at an older node.

    The causal edge is fine to add, but it must not replace the edge to the node the
    agent was actually standing on, or the graph shows a move across empty space.
    """
    graph = ActionGraph()
    visited = walk(
        graph,
        [
            event(1, "/a"),
            event(2, "/b", ["run-1:e1"]),
            event(3, "/c", ["run-1:e2"]),
            # The agent is on /c but the step is attributed back to /a.
            event(4, "/d", ["run-1:e1"]),
        ],
    )
    assert_every_move_is_an_edge(graph, visited)
    # The causal reference is still recorded as its own edge.
    first, last = visited[0], visited[-1]
    assert first in {node.id for node in graph.get_node(last).neighbors}


def test_a_new_node_is_created_attached_and_never_orphaned():
    graph = ActionGraph()
    visited = walk(graph, [event(n, f"/step-{n}") for n in range(1, 8)])
    assert_every_move_is_an_edge(graph, visited)
    for node in graph.nodes:
        if node.id == "root":
            continue
        assert node.neighbors, f"{node.id} was created with no connection"


def test_revisiting_an_action_returns_to_its_node_and_keeps_the_walk_connected():
    graph = ActionGraph()
    visited = walk(
        graph,
        [event(1, "/a"), event(2, "/b"), event(3, "/a"), event(4, "/c")],
    )
    assert_every_move_is_an_edge(graph, visited)
    assert visited[0] == visited[2], "a repeated action must return to its own node"
    # Branch: /a now leads to both /b and /c.
    branch = graph.get_node(visited[0])
    assert {node.id for node in branch.neighbors} >= {visited[1], visited[3]}
