from pydantic import BaseModel


class StartingGridEntry(BaseModel):
    position: int
    driver_code: str
    team_id: str
    quali_time: str | None = None


class StartingGrid(BaseModel):
    circuit: str
    entries: list[StartingGridEntry]
    updated_at: float = 0.0
