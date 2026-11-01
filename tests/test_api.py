from __future__ import annotations

from fastapi.testclient import TestClient

from app.llm import MockLLMClient
from app.main import create_app


def make_client(tmp_path) -> TestClient:
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        llm_client=MockLLMClient(),
    )
    return TestClient(app)


def test_health(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "llm_mode": "mock"}


def test_chat_creates_conversation_and_saves_history(tmp_path) -> None:
    with make_client(tmp_path) as client:
        first = client.post("/api/chat", json={"message": "今天有点累"})
        assert first.status_code == 200
        body = first.json()
        assert body["provider"] == "mock"
        assert body["conversation_id"] > 0

        second = client.post(
            "/api/chat",
            json={
                "message": "主要是学习压力",
                "conversation_id": body["conversation_id"],
            },
        )
        assert second.status_code == 200

        history = client.get(f"/api/conversations/{body['conversation_id']}")
        assert history.status_code == 200
        roles = [item["role"] for item in history.json()["messages"]]
        assert roles == ["user", "assistant", "user", "assistant"]


def test_empty_message_is_rejected(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_crisis_signal_uses_safety_reply_without_calling_model(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post("/api/chat", json={"message": "我不想活了"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "safety"
    assert body["safety_triggered"] is True
    assert "110" in body["reply"]


def test_unknown_conversation_returns_404(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/chat",
            json={"message": "你好", "conversation_id": 9999},
        )

    assert response.status_code == 404
