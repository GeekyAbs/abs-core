import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app, rate_limit_exceeded
from app.rag.retriever import RetrievalUnavailable
from app.voice import (
    KNOWLEDGE_UNAVAILABLE,
    NOT_CONFIGURED,
    RATE_LIMITED,
    UNAVAILABLE,
)


class FakeGraph:
    def __init__(self, *, reply: str = "A measured reply.", error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.states: list[dict] = []

    def invoke(self, state):
        self.states.append(dict(state))
        if self.error is not None:
            raise self.error
        return {
            **state,
            "reply": self.reply,
            "retrieved": [
                {"source": "blog", "content": "a"},
                {"source": "portfolio", "content": "b"},
                {"source": "blog", "content": "c"},
            ],
        }


@pytest.fixture
def client(monkeypatch, seeded_db):
    monkeypatch.setattr(settings, "db_path", seeded_db)
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr("test-key"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_graph(monkeypatch):
    graph = FakeGraph()
    monkeypatch.setattr("app.main.graph", graph)
    return graph


def test_health_is_liveness_only(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_ok_with_key_and_corpus(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_is_503_without_api_key(client, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(""))

    response = client.get("/ready")

    assert response.status_code == 503
    assert any("OPENROUTER_API_KEY" in issue for issue in response.json()["issues"])


def test_ready_is_503_without_corpus(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "missing.db"))

    response = client.get("/ready")

    assert response.status_code == 503
    assert any("knowledge base" in issue.lower() for issue in response.json()["issues"])


def test_chat_returns_reply_and_unique_sorted_sources(client, fake_graph):
    response = client.post("/chat", json={"session_id": "s", "message": "who is abesh"})

    assert response.status_code == 200
    assert response.json() == {"reply": "A measured reply.", "sources": ["blog", "portfolio"]}
    assert fake_graph.states[0]["user_input"] == "who is abesh"


def test_chat_is_503_when_backend_is_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(""))

    response = client.post("/chat", json={"session_id": "s", "message": "who is abesh"})

    assert response.status_code == 503
    assert response.json()["detail"] == NOT_CONFIGURED


def test_chat_is_503_when_knowledge_base_is_unavailable(client, fake_graph):
    fake_graph.error = RetrievalUnavailable("index empty")

    response = client.post("/chat", json={"session_id": "s", "message": "who is abesh"})

    assert response.status_code == 503
    assert response.json()["detail"] == KNOWLEDGE_UNAVAILABLE


def test_chat_is_502_and_does_not_leak_internals_on_unexpected_error(client, fake_graph):
    fake_graph.error = RuntimeError("secret upstream detail")

    response = client.post("/chat", json={"session_id": "s", "message": "who is abesh"})

    assert response.status_code == 502
    assert response.json()["detail"] == UNAVAILABLE
    assert "secret upstream detail" not in response.text


def test_rate_limit_reply_is_styled():
    response = rate_limit_exceeded(None, None)

    assert response.status_code == 429
    assert RATE_LIMITED.encode() in response.body


def test_chat_rejects_blank_message(client, fake_graph):
    response = client.post("/chat", json={"session_id": "s", "message": "   "})

    assert response.status_code == 422
    assert fake_graph.states == []


def test_chat_rejects_oversized_message(client, fake_graph):
    response = client.post(
        "/chat",
        json={"session_id": "s", "message": "x" * (settings.max_message_chars + 1)},
    )

    assert response.status_code == 422


def test_chat_rejects_oversized_session_id(client, fake_graph):
    response = client.post("/chat", json={"session_id": "s" * 200, "message": "hi"})

    assert response.status_code == 422


def test_chat_sets_request_id_header(client, fake_graph):
    response = client.post("/chat", json={"session_id": "s", "message": "hi"})

    assert response.headers.get("x-request-id")


def test_cors_allows_the_configured_origin(client):
    response = client.options(
        "/chat",
        headers={"Origin": "https://abesh.site", "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://abesh.site"


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/chat",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
