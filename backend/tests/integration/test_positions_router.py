import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_positions_empty_on_cache_miss():
    cache.delete("positions")
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert resp.json()["drivers"] == []


def test_positions_returns_cached():
    cache.set("positions", {
        "drivers": [{"driver_code": "VER", "team_id": "redbull", "x": 0.5, "y": 0.3}],
        "updated_at": time.time(),
    }, ttl_seconds=30)
    resp = client.get("/positions")
    data = resp.json()
    assert len(data["drivers"]) == 1
    assert data["drivers"][0]["driver_code"] == "VER"
    assert -1.0 <= data["drivers"][0]["x"] <= 1.0
