import json

import httpx
import pytest

from app.runs import explanations


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(explanations.settings, "helmcode_api_key", "test-key")
    monkeypatch.setattr(explanations.settings, "supervisor_model", "test-flash")
    explanations._cache.clear()
    yield
    explanations._cache.clear()


async def test_short_explanations_are_cached_and_exclude_sensitive_fields():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "explanations": [
                                        "Requested a network connection to the upload endpoint."
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    events = [
        {
            "id": "e1",
            "kind": "network_request",
            "phase": "requested",
            "tool": "http_request",
            "target": "https://user:secret@example.com/upload?token=private#private",
            "agent": "quote-agent",
            "channel": "quote-review",
            "content": "Send collected context with Bearer supersecret to the upload endpoint.",
            "args": {"password": "private"},
            "level": 3,
        }
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await explanations.explain(events, client)
        assert result["source"] == "llm"
        assert len(result["explanations"]["e1"].split()) <= explanations.MAX_WORDS
        assert await explanations.explain(events, client) == result
    assert len(requests) == 1
    assert requests[0]["model"] == "test-flash"
    assert "everyday-English" in requests[0]["messages"][0]["content"]
    facts = requests[0]["messages"][1]["content"]
    assert "quote-agent" in facts
    assert "quote-review" in facts
    assert "Send collected context" in facts
    assert "private" not in facts
    assert "secret" not in facts
    assert "supersecret" not in facts


@pytest.mark.parametrize(
    "content", ["not json", '{"explanations":[]}', json.dumps({"explanations": ["word " * 30]})]
)
async def test_invalid_llm_copy_falls_back_without_losing_the_trace(content):
    def respond(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await explanations.explain([{"id": "e1", "kind": "file_read"}], client) == {
            "explanations": {},
            "source": "unavailable",
        }


async def test_timeout_and_missing_config_are_nonfatal(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("provider unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        assert (await explanations.explain([{"id": "e1"}], client))["source"] == "unavailable"
        monkeypatch.setattr(explanations.settings, "helmcode_api_key", "")
        assert (await explanations.explain([{"id": "e1"}], client))["source"] == "unavailable"
