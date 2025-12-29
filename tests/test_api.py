from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_models():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 3
    
    model_ids = [model["id"] for model in data["data"]]
    assert "gpt" in model_ids
    assert "gemini" in model_ids
    assert "grok" in model_ids

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "tab_stats" in data

def test_session_id_validation():
    """Test that session_id validation works."""
    response = client.post("/v1/chat/completions", json={
        "model": "gpt",
        "messages": [{"role": "user", "content": "test"}],
        "session_id": "abcd1234"
    })
    # Should fail at browser level but not validation
    assert response.status_code in [200, 500]  # 500 due to browser not available in test

    # Invalid session_id (too short)
    response = client.post("/v1/chat/completions", json={
        "model": "gpt",
        "messages": [{"role": "user", "content": "test"}],
        "session_id": "abc"
    })
    assert response.status_code == 422  # Validation error
    
    # Invalid session_id (non-hex)
    response = client.post("/v1/chat/completions", json={
        "model": "gpt",
        "messages": [{"role": "user", "content": "test"}],
        "session_id": "not-valid-hex!"
    })
    assert response.status_code == 422  # Validation error