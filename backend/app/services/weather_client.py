import httpx
from ..models.weather import WeatherData
import time

_BASE = "https://api.open-meteo.com/v1/forecast"

_CONDITION_MAP = {
    (0, 20): "Clear",
    (20, 50): "Partly cloudy",
    (50, 80): "Cloudy",
    (80, 100): "Rain likely",
}


def _describe(rain_pct: float) -> str:
    for (lo, hi), label in _CONDITION_MAP.items():
        if lo <= rain_pct < hi:
            return label
    return "Rain"


def fetch(lat: float, lon: float) -> WeatherData:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability",
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(_BASE, params=params)
        resp.raise_for_status()
    current = resp.json()["current"]
    rain_chance = float(current.get("precipitation_probability", 0) or 0)
    return WeatherData(
        air_temp=float(current["temperature_2m"]),
        humidity=float(current["relative_humidity_2m"]),
        wind_speed=float(current["wind_speed_10m"]),
        rain_chance=rain_chance,
        description=_describe(rain_chance),
        is_live=False,
        updated_at=time.time(),
    )
