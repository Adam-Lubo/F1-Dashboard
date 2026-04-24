import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


def test_historical_returns_model_shape():
    if not (FIXTURES / "timingdata.json").exists():
        pytest.skip("Run download_spa_2024.py first")
    resp = client.get("/historical/VER/spa")
    assert resp.status_code == 200
    data = resp.json()
    assert data["driver_code"] == "VER"
    assert data["circuit"] == "spa"
    assert isinstance(data["races"], int)
    assert data["races"] >= 0


def test_historical_unknown_driver_returns_empty():
    resp = client.get("/historical/XXX/spa")
    assert resp.status_code == 200
    assert resp.json()["races"] == 0
