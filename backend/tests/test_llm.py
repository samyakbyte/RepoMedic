"""LLM service tests with a mocked Ollama HTTP responder (unit tests only)."""

import json
from pathlib import Path

import httpx
import pytest

from app.core.llm import OllamaClient, OllamaError
from app.schemas.patch import RepairProposal

VALID_CHAT = {
    "model": "qwen2.5-coder:1.5b",
    "created_at": "2026-10-25T12:00:00Z",
    "message": {"role": "assistant", "content": json.dumps({
        "root_cause": "missing division by 100",
        "target_file": "src/calc.py",
        "old_snippet": "return price - price * percent",
        "new_snippet": "return price - price * percent / 100",
        "explanation": "percent must be divided by 100",
        "expected_outcome": "apply_discount(200, 10) == 180",
    })},
    "done": True,
    "prompt_eval_count": 40,
    "eval_count": 54,
    "eval_duration": 1_000_000_000,
    "total_duration": 1_200_000_000,
    "load_duration": 200_000_000,
}

INVALID_JSON_CHAT = {
    "model": "qwen2.5-coder:1.5b",
    "message": {"role": "assistant", "content": "this is not json"},
    "done": True,
    "prompt_eval_count": 10,
    "eval_count": 5,
    "eval_duration": 500_000_000,
    "total_duration": 600_000_000,
}


def _transport(handler):
    return httpx.MockTransport(handler)


def _client_with(handler):
    client = OllamaClient(timeout_s=5)
    client._transport = _transport(handler)
    # generate_repair creates its own httpx.Client; patch httpx.Client in tests via monkeypatch instead.
    return client


def test_generate_repair_valid_json(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/chat":
            return httpx.Response(200, json=VALID_CHAT)
        return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:1.5b"}]})

    import app.core.llm as llm_mod

    orig = httpx.Client

    class Patched(orig):
        def __init__(self, *a, **k):
            k["transport"] = _transport(handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "Client", Patched)
    monkeypatch.setattr(llm_mod.httpx, "Client", Patched)

    client = OllamaClient(timeout_s=5)
    result = client.generate_repair("some failing test context")
    assert isinstance(result.proposal, RepairProposal)
    assert result.proposal.root_cause == "missing division by 100"
    assert result.proposal.new_snippet == "return price - price * percent / 100"
    assert result.tokens_per_second == 54 / (1_000_000_000 / 1e9), result.tokens_per_second
    assert result.eval_count == 54
    assert result.eval_duration_ns == 1_000_000_000


def test_generate_repair_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json=INVALID_JSON_CHAT)
        return httpx.Response(200, json=VALID_CHAT)

    import app.core.llm as llm_mod

    class Patched(httpx.Client):
        def __init__(self, *a, **k):
            k["transport"] = _transport(handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "Client", Patched)
    monkeypatch.setattr(llm_mod.httpx, "Client", Patched)

    client = OllamaClient(timeout_s=5)
    result = client.generate_repair("context")
    assert calls["n"] == 2
    assert result.proposal.root_cause == "missing division by 100"


def test_generate_repair_invalid_output_after_retries(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=INVALID_JSON_CHAT)

    import app.core.llm as llm_mod

    class Patched(httpx.Client):
        def __init__(self, *a, **k):
            k["transport"] = _transport(handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "Client", Patched)
    monkeypatch.setattr(llm_mod.httpx, "Client", Patched)

    client = OllamaClient(timeout_s=5)
    with pytest.raises(OllamaError) as exc:
        client.generate_repair("context")
    assert exc.value.code == "LLM_INVALID_OUTPUT"


def test_model_not_pulled(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/chat":
            return httpx.Response(404, json={"error": "model not found"})
        return httpx.Response(200, json={"models": []})

    import app.core.llm as llm_mod

    class Patched(httpx.Client):
        def __init__(self, *a, **k):
            k["transport"] = _transport(handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "Client", Patched)
    monkeypatch.setattr(llm_mod.httpx, "Client", Patched)

    client = OllamaClient(timeout_s=5, model="qwen2.5-coder:7b")
    with pytest.raises(OllamaError) as exc:
        client.generate_repair("context")
    assert exc.value.code == "MODEL_NOT_PULLED"


def test_ollama_down(monkeypatch):
    import app.core.llm as llm_mod

    class Patched(httpx.Client):
        def __init__(self, *a, **k):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "Client", Patched)
    monkeypatch.setattr(llm_mod.httpx, "Client", Patched)

    client = OllamaClient(timeout_s=5)
    with pytest.raises(OllamaError) as exc:
        client.generate_repair("context")
    assert exc.value.code == "OLLAMA_DOWN"


def test_health_when_down(monkeypatch):
    import app.core.llm as llm_mod

    class Patched(httpx.Client):
        def __init__(self, *a, **k):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "Client", Patched)
    monkeypatch.setattr(llm_mod.httpx, "Client", Patched)

    client = OllamaClient()
    status = client.health()
    assert status["ollama_reachable"] is False
    assert status["model_available"] is False
    assert "Ollama" in status["hint"]
