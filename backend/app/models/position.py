from pydantic import BaseModel


class DriverPosition(BaseModel):
    driver_code: str
    team_id: str
    x: float
    y: float


class TrackPositions(BaseModel):
    drivers: list[DriverPosition]
    updated_at: float = 0.0
