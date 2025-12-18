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
    assert "chatgpt-free" in model_ids
    assert "gemini-free" in model_ids
    assert "grok-free" in model_ids

def test_health_check():
    # Since we don't have a dedicated health endpoint, we can use docs or models
    response = client.get("/docs")
    assert response.status_code == 200
