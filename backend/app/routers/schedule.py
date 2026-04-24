from fastapi import APIRouter, HTTPException
from ..main import cache, state_machine
from ..models.schedule import WeekendSchedule
from ..services import schedule_service

router = APIRouter()


@router.get("/schedule", response_model=WeekendSchedule)
def get_schedule():
    result = schedule_service.current_weekend(cache)
    if result is None:
        raise HTTPException(status_code=503, detail="Schedule unavailable")
    weekend, next_ts = result
    if next_ts is not None:
        state_machine.set_next_session_at(next_ts)
    return weekend
