import pytest

from app.classification import Level, classifier, classify
from app.config import settings
from app.graph.models import Node


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "typesafe_api_key", "test-key")


def fake_response(choice: str):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "answers": {
                    "criticality": {
                        "type": "choice",
                        "choice": choice,
                        "probabilities": {},
                        "confidence": 0.9,
                    }
                }
            }

    return Resp()


def test_classify_returns_single_level(monkeypatch):
    captured = {}

    def post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, headers=headers)
        return fake_response("level_3_severe")

    monkeypatch.setattr(classifier.httpx, "post", post)
    nodes = [
        Node(id="e1", tool={"event": "file_read", "path": "/app/.env"}),
        Node(id="e2", tool={"event": "network_request", "dst": "https://evil.example"}),
    ]

    assert classify(nodes) is Level.SEVERE
    body = captured["body"]
    assert body["model"] == "jev-latest"
    assert body["questions"]["criticality"]["type"] == "choice"
    assert body["state"]["short_term"] == [
        {"id": "e1", "threshold": 0.0, "tool": {"event": "file_read", "path": "/app/.env"}},
        {
            "id": "e2",
            "threshold": 0.0,
            "tool": {"event": "network_request", "dst": "https://evil.example"},
        },
    ]
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_classify_passes_optional_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        classifier.httpx,
        "post",
        lambda url, json=None, **kw: captured.update(body=json) or fake_response("level_1_mild"),
    )
    classify(
        [Node(id="n")],
        run_id="run-1",
        prior_level=Level.MILD,
        long_term=[Node(id="old", threshold=0.8)],
    )
    state = captured["body"]["state"]
    assert state["run_id"] == "run-1"
    assert state["prior_level"] == 1
    assert state["long_term"] == [{"id": "old", "threshold": 0.8}]


def test_unknown_choice_raises(monkeypatch):
    monkeypatch.setattr(
        classifier.httpx, "post", lambda *a, **kw: fake_response("level_9_nope")
    )
    with pytest.raises(ValueError, match="unknown jev choice"):
        classify([Node(id="n")])


def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "typesafe_api_key", "")
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        classify([Node(id="n")])
