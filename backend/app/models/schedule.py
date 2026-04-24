from pydantic import BaseModel
from .session import SessionType


class ScheduleSession(BaseModel):
    type: SessionType
    name: str
    day: str
    local_time: str
    utc_time: str
    is_next: bool = False
    is_complete: bool = False


class WeekendSchedule(BaseModel):
    circuit: str
    country: str
    round: int
    season: int
    sessions: list[ScheduleSession]
