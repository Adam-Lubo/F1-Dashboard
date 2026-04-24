from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


FAKE_MEETINGS = [{
    "round": 6,
    "season": 2026,
    "Country": "United States",
    "Location": "Miami",
    "circuit_short_name": "miami",
    "sessions": [
        {"Name": "Practice 1",  "StartDate": _future(-48)},
        {"Name": "Practice 2",  "StartDate": _future(-44)},
        {"Name": "Practice 3",  "StartDate": _future(-24)},
        {"Name": "Qualifying",  "StartDate": _future(-20)},
        {"Name": "Race",        "StartDate": _future(2)},
    ],
}]


def test_schedule_returns_weekend_shape():
    with patch("app.services.schedule_service.load_season", return_value=FAKE_MEETINGS):
        resp = client.get("/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["circuit"] == "miami"
    assert len(data["sessions"]) == 5
    next_sessions = [s for s in data["sessions"] if s["is_next"]]
    assert len(next_sessions) == 1
    assert next_sessions[0]["name"] == "RACE"


def test_predictions_returns_stub():
    resp = client.get("/predictions")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert len(data["entries"]) >= 5
    assert "win_probability" in data["entries"][0]
