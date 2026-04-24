import time
from fastapi import APIRouter
from ..main import cache, state_machine
from ..models.session import SessionInfo, SessionType
from ..services import schedule_service

_NAME_TO_TYPE = {
    "FP1": SessionType.PRACTICE, "FP2": SessionType.PRACTICE, "FP3": SessionType.PRACTICE,
    "QUALI": SessionType.QUALIFYING,
    "SPRINT QUALI": SessionType.SPRINT_QUALI,
    "SPRINT": SessionType.SPRINT,
    "RACE": SessionType.RACE,
}

router = APIRouter()


@router.get("/state", response_model=SessionInfo)
def get_state():
    state = state_machine.tick()

    result = schedule_service.current_weekend(cache)
    if result is not None:
        weekend, next_ts = result
        if next_ts is not None:
            state_machine.set_next_session_at(next_ts)
        active = next((s for s in weekend.sessions if s.is_next and not s.is_complete), None)
        nxt = next((s for s in weekend.sessions if not s.is_complete), None)
        session = active or nxt
        session_type = _NAME_TO_TYPE.get(session.name) if session else None
        session_name = f"{weekend.circuit.upper()} {session.name}" if session else "F1 Dashboard"
        round_ = weekend.round
        season = weekend.season
        countdown = int(next_ts - time.time()) if next_ts else None
        if countdown is not None and countdown < 0:
            countdown = None
    else:
        session_type = None
        session_name = "F1 Dashboard"
        round_ = 0
        season = 2026
        countdown = None

    timing = cache.get("timing") or {}
    entries = timing.get("entries", [])
    current_lap: int | None = None
    leader_gap: str | None = None
    if entries:
        second = next((e for e in entries if e.get("position") == 2), None)
        leader_gap = second.get("gap") if second else None
        current_lap = timing.get("current_lap")

    return SessionInfo(
        state=state,
        session_type=session_type,
        session_name=session_name,
        round=round_,
        season=season,
        current_lap=current_lap,
        total_laps=None,
        leader_gap=leader_gap,
        countdown_seconds=countdown,
        session_elapsed_seconds=None,
    )
