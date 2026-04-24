import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_timing_returns_empty_when_no_cache():
    cache.delete("timing")
    resp = client.get("/timing")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_timing_returns_cached_data():
    cache.set("timing", {
        "entries": [{
            "position": 1, "driver_code": "VER", "team_id": "redbull",
            "last_lap": "1:46.123", "gap": "Leader", "interval": None,
            "tire": None, "tire_age": None,
            "is_fastest_overall": False, "is_personal_best": False,
            "is_in_battle": False, "is_retired": False, "dnf": False,
        }],
        "fastest_lap_driver": None,
        "fastest_lap_time": None,
        "updated_at": time.time(),
    }, ttl_seconds=30)
    resp = client.get("/timing")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["driver_code"] == "VER"
    assert data["entries"][0]["gap"] == "Leader"
