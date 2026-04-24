from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app, state_machine

client = TestClient(app)


def test_state_returns_idle_by_default():
    state_machine.__init__()  # reset to IDLE
    with patch("app.services.schedule_service.current_weekend", return_value=None):
        resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "IDLE"
    assert data["season"] == 2026
    assert "countdown_seconds" in data


def test_state_reflects_machine_state():
    with patch("app.services.schedule_service.current_weekend", return_value=None):
        state_machine.on_timing_data()
        resp = client.get("/state")
        assert resp.json()["state"] == "LIVE"
    state_machine.__init__()  # reset
