import time
import respx
import httpx
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)

OPEN_METEO_MOCK = {
    "current": {
        "temperature_2m": 27.4,
        "relative_humidity_2m": 65,
        "wind_speed_10m": 12.0,
        "precipitation_probability": 15,
    }
}


def test_weather_returns_cached_data():
    cache.set("weather/miami", {
        "air_temp": 27.0, "track_temp": None, "humidity": 65.0,
        "wind_speed": 12.0, "rain_chance": 15.0,
        "description": "Partly cloudy", "is_live": False, "updated_at": time.time(),
    }, ttl_seconds=60)
    resp = client.get("/weather/miami")
    assert resp.status_code == 200
    data = resp.json()
    assert data["air_temp"] == 27.0
    assert "rain_chance" in data


@respx.mock
def test_weather_fetches_from_open_meteo_on_cache_miss():
    cache.delete("weather/miami")
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=OPEN_METEO_MOCK)
    )
    resp = client.get("/weather/miami")
    assert resp.status_code == 200
    assert resp.json()["air_temp"] == 27.4
