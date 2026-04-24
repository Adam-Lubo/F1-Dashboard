import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..main import cache, state_machine
from ..config import settings

router = APIRouter(prefix="/replay")


class ReplayStatus(BaseModel):
    active: bool
    session_key: str | None
    current_lap: int
    total_laps: int


def _get_manager():
    from ..main import replay_manager
    if replay_manager is None:
        raise HTTPException(status_code=404, detail="Replay mode not active")
    return replay_manager


@router.get("/status", response_model=ReplayStatus)
def get_replay_status():
    from ..main import replay_manager
    if replay_manager is None:
        return ReplayStatus(active=False, session_key=None, current_lap=0, total_laps=0)
    return ReplayStatus(
        active=True,
        session_key=settings.replay_session,
        current_lap=replay_manager.current_lap,
        total_laps=replay_manager.total_laps,
    )


@router.post("/seek/{lap}")
def seek_to_lap(lap: int):
    manager = _get_manager()
    clamped, new_rc_messages = manager.seek(lap)

    cache.set("timing",    manager.get_timing().model_dump(mode="json"),    ttl_seconds=3600)
    cache.set("positions", manager.get_positions().model_dump(mode="json"), ttl_seconds=3600)

    state_machine.on_timing_data()
    for msg in new_rc_messages:
        state_machine.on_race_control_message(msg["message"])

    cache.set("race_control", {
        "entries": manager.get_race_control_log(),
        "updated_at": time.time(),
    }, ttl_seconds=3600)

    return {"lap": clamped, "total_laps": manager.total_laps}
