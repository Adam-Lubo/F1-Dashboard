from pydantic import BaseModel


class WeatherData(BaseModel):
    air_temp: float
    track_temp: float | None = None
    humidity: float
    wind_speed: float
    rain_chance: float
    description: str
    is_live: bool = False
    updated_at: float = 0.0
