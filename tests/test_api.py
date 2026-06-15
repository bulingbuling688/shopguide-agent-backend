from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rag_search_keyword_and_vector():
    response = client.post("/rag/search", json={"query": "3000 元左右拍照好的手机", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["matches"]
    assert any("手机" in item["product"]["category"] for item in body["matches"])


def test_recommend_returns_trace_and_reasons():
    response = client.post("/recommend", json={"query": "我想买轻薄办公笔记本，预算 6000", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"]
    assert body["trace"][0]["node"] == "parse_intent"
    assert body["needs_clarification"] is False


def test_recommend_clarification():
    response = client.post("/recommend", json={"query": "推荐下", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_clarification"] is True
    assert body["clarification_question"]


def test_chat_persists_session_version():
    first = client.post("/chat", json={"session_id": "pytest-session", "message": "通勤降噪耳机"})
    second = client.post("/chat", json={"session_id": "pytest-session", "message": "预算 1000 以内"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["version"] > first.json()["version"]


def test_chat_stream_sse():
    with client.stream("POST", "/chat/stream", json={"session_id": "stream-session", "message": "适合宠物家庭的清洁产品"}) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())
        assert "event: token" in text
        assert "event: done" in text
