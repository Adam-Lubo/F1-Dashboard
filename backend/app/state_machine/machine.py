import time
from app.models.session import SessionState

_ARMED_WINDOW = 15 * 60   # seconds before session to arm
_PAUSE_TIMEOUT = 60        # seconds without data before pausing


class StateMachine:
    def __init__(self):
        self._state = SessionState.IDLE
        self._last_data_at: float | None = None
        self._next_session_at: float | None = None
        self._active_flag: str | None = None

    @property
    def state(self) -> SessionState:
        return self._state

    def set_next_session_at(self, ts: float) -> None:
        self._next_session_at = ts

    def tick(self, now: float | None = None) -> SessionState:
        now = now or time.time()

        # Flag states take priority
        if self._active_flag == "RED FLAG":
            self._state = SessionState.RED_FLAG
            return self._state
        if self._active_flag == "VIRTUAL SAFETY CAR":
            self._state = SessionState.VSC
            return self._state
        if self._active_flag == "SAFETY CAR":
            self._state = SessionState.SC
            return self._state
        if self._active_flag == "YELLOW FLAG":
            self._state = SessionState.YELLOW_FLAG
            return self._state

        # Data staleness
        if self._state in (SessionState.LIVE, SessionState.PAUSED):
            if self._last_data_at is not None:
                if now - self._last_data_at > _PAUSE_TIMEOUT:
                    self._state = SessionState.PAUSED
                else:
                    self._state = SessionState.LIVE

        # IDLE → ARMED transition
        if self._state == SessionState.IDLE and self._next_session_at is not None:
            if self._next_session_at - now <= _ARMED_WINDOW:
                self._state = SessionState.ARMED

        return self._state

    def on_timing_data(self, at: float | None = None) -> None:
        self._last_data_at = at or time.time()
        if self._state not in (SessionState.ENDED,) and self._active_flag is None:
            self._state = SessionState.LIVE

    def on_race_control_message(self, message: str) -> None:
        msg = message.upper()
        if "CHEQUERED FLAG" in msg:
            self._active_flag = None
            self._state = SessionState.ENDED
        elif "RED FLAG" in msg:
            self._active_flag = "RED FLAG"
            self._state = SessionState.RED_FLAG
        elif "VIRTUAL SAFETY CAR" in msg:
            self._active_flag = "VIRTUAL SAFETY CAR"
            self._state = SessionState.VSC
        elif "SAFETY CAR" in msg:
            self._active_flag = "SAFETY CAR"
            self._state = SessionState.SC
        elif "YELLOW FLAG" in msg:
            self._active_flag = "YELLOW FLAG"
            self._state = SessionState.YELLOW_FLAG
        elif "TRACK CLEAR" in msg or "GREEN LIGHT" in msg or "SAFETY CAR IN" in msg:
            self._active_flag = None
            if self._state not in (SessionState.IDLE, SessionState.ENDED):
                self._state = SessionState.LIVE if self._last_data_at else SessionState.ARMED
