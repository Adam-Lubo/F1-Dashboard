import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_race_control_empty_on_miss():
    cache.delete("race_control")
    resp = client.get("/race-control")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_race_control_returns_cached_entries():
    cache.set("race_control", {
        "entries": [
            {"utc": "2024-07-28T13:00:00", "lap": 1,  "category": "Flag",      "message": "GREEN LIGHT"},
            {"utc": "2024-07-28T13:10:00", "lap": 12, "category": "SafetyCar", "message": "SAFETY CAR DEPLOYED"},
        ],
        "updated_at": time.time(),
    }, ttl_seconds=60)
    resp = client.get("/race-control")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 2
    assert data["entries"][0]["category"] == "Flag"
