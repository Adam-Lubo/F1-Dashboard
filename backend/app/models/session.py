from enum import Enum
from pydantic import BaseModel


class SessionState(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    RED_FLAG = "RED_FLAG"
    YELLOW_FLAG = "YELLOW_FLAG"
    SC = "SC"
    VSC = "VSC"
    ENDED = "ENDED"


class SessionType(str, Enum):
    PRACTICE = "PRACTICE"
    QUALIFYING = "QUALIFYING"
    SPRINT_QUALI = "SPRINT_QUALI"
    SPRINT = "SPRINT"
    RACE = "RACE"


class SessionInfo(BaseModel):
    state: SessionState
    session_type: SessionType | None = None
    session_name: str
    round: int
    season: int
    current_lap: int | None = None
    total_laps: int | None = None
    leader_gap: str | None = None
    countdown_seconds: int | None = None
    session_elapsed_seconds: int | None = None
