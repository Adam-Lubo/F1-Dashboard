from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_circuits_returns_miami():
    resp = client.get("/circuits/miami")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "miami"
    assert data["total_laps"] > 0


def test_circuits_404_on_unknown():
    resp = client.get("/circuits/nowhere")
    assert resp.status_code == 404
