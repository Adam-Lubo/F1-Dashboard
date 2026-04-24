from enum import Enum
from pydantic import BaseModel


class TireCompound(str, Enum):
    SOFT = "S"
    MEDIUM = "M"
    HARD = "H"
    INTERMEDIATE = "I"
    WET = "W"


class TimingEntry(BaseModel):
    position: int
    driver_code: str
    team_id: str
    last_lap: str | None = None
    gap: str | None = None
    interval: str | None = None
    tire: TireCompound | None = None
    tire_age: int | None = None
    is_fastest_overall: bool
    is_personal_best: bool
    is_in_battle: bool
    is_retired: bool
    dnf: bool
    # Watchlist is computed client-side; not part of server payload.


class TimingTower(BaseModel):
    entries: list[TimingEntry]
    fastest_lap_driver: str | None = None
    fastest_lap_time: str | None = None
    updated_at: float = 0.0
