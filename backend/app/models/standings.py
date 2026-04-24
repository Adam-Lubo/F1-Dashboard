from pydantic import BaseModel


class DriverStanding(BaseModel):
    position: int
    driver_code: str
    team_id: str
    points: float
    wins: int


class ConstructorStanding(BaseModel):
    position: int
    team_id: str
    team_name: str
    points: float
    wins: int
