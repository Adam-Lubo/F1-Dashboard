import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..main import cache
from ..models.weather import WeatherData
from ..services import weather_client

router = APIRouter()
_CIRCUITS_PATH = Path(__file__).parent.parent.parent / "data" / "circuits.json"


def _circuit_coords(circuit_id: str) -> tuple[float, float]:
    circuits = json.loads(_CIRCUITS_PATH.read_text())
    if circuit_id not in circuits:
        raise HTTPException(status_code=404, detail=f"Unknown circuit: {circuit_id}")
    c = circuits[circuit_id]
    return c["lat"], c["lon"]


@router.get("/weather/{circuit_id}", response_model=WeatherData)
def get_weather(circuit_id: str):
    cache_key = f"weather/{circuit_id}"
    cached = cache.get(cache_key)
    if cached:
        return WeatherData(**cached)
    lat, lon = _circuit_coords(circuit_id)
    try:
        data = weather_client.fetch(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")
    cache.set(cache_key, data.model_dump(), ttl_seconds=600)
    return data
