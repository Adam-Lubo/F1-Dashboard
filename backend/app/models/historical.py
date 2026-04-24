from pydantic import BaseModel


class HistoricalStats(BaseModel):
    driver_code: str
    circuit: str
    best_finish: int | None = None
    best_quali: int | None = None
    avg_race_pos: float | None = None
    avg_quali_pos: float | None = None
    wins: int = 0
    poles: int = 0
    races: int = 0
