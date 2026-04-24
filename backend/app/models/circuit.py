from pydantic import BaseModel


class CircuitInfo(BaseModel):
    id: str
    name: str
    country: str
    lat: float
    lon: float
    length_km: float
    total_laps: int
    lap_record: str
    lap_record_driver: str
    lap_record_year: int
    timezone: str
