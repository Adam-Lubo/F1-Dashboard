from enum import Enum
from pydantic import BaseModel


class RaceControlCategory(str, Enum):
    FLAG = "Flag"
    SAFETY_CAR = "SafetyCar"
    DRS = "Drs"
    CAR_EVENT = "CarEvent"
    OTHER = "Other"


class RaceControlMessage(BaseModel):
    utc: str
    lap: int | None = None
    category: RaceControlCategory
    message: str


class RaceControlLog(BaseModel):
    entries: list[RaceControlMessage]
    updated_at: float = 0.0
