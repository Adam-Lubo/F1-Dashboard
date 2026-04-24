import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_grid_empty_on_miss():
    cache.delete("grid")
    resp = client.get("/grid")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_grid_returns_cached():
    cache.set("grid", {
        "circuit": "miami",
        "entries": [
            {"position": 1, "driver_code": "VER", "team_id": "redbull", "quali_time": "1:27.121"},
            {"position": 2, "driver_code": "NOR", "team_id": "mclaren", "quali_time": "1:27.344"},
        ],
        "updated_at": time.time(),
    }, ttl_seconds=3600)
    resp = client.get("/grid")
    data = resp.json()
    assert data["circuit"] == "miami"
    assert len(data["entries"]) == 2
    assert data["entries"][0]["driver_code"] == "VER"
