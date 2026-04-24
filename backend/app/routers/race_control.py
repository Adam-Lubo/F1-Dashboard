from fastapi import APIRouter
from ..main import cache
from ..models.race_control import RaceControlLog

router = APIRouter()


@router.get("/race-control", response_model=RaceControlLog)
def get_race_control():
    data = cache.get("race_control")
    if data is None:
        return RaceControlLog(entries=[], updated_at=0.0)
    return RaceControlLog(**data)
