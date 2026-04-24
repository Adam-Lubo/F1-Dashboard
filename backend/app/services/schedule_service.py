import time
from datetime import datetime, timezone, timedelta
from typing import Any

import livef1

from ..cache.file_cache import CacheBackend
from ..models.schedule import WeekendSchedule, ScheduleSession, SessionType

_TYPE_MAP = {
    "PRACTICE 1": (SessionType.PRACTICE, "FP1", "FRI"),
    "PRACTICE 2": (SessionType.PRACTICE, "FP2", "FRI"),
    "PRACTICE 3": (SessionType.PRACTICE, "FP3", "SAT"),
    "QUALIFYING": (SessionType.QUALIFYING, "QUALI", "SAT"),
    "SPRINT QUALIFYING": (SessionType.SPRINT_QUALI, "SPRINT QUALI", "FRI"),
    "SPRINT": (SessionType.SPRINT, "SPRINT", "SAT"),
    "RACE": (SessionType.RACE, "RACE", "SUN"),
}

_SEASON_CACHE_TTL = 24 * 60 * 60
_SEASON_CACHE_KEY_TMPL = "schedule/season/{season}"


def _normalize_session(raw: dict) -> ScheduleSession | None:
    type_raw = (raw.get("session_type") or raw.get("Name") or "").upper().strip()
    mapped = _TYPE_MAP.get(type_raw)
    if not mapped:
        return None
    kind, name, default_day = mapped

    utc_str = raw.get("StartDate") or raw.get("date_start") or ""
    try:
        start_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    now = datetime.now(timezone.utc)
    is_complete = start_utc < now

    return ScheduleSession(
        type=kind,
        name=name,
        day=default_day,
        local_time=raw.get("local_time", ""),
        utc_time=start_utc.strftime("%H:%M"),
        is_next=False,
        is_complete=is_complete,
    )


def _current_season() -> int:
    return datetime.now(timezone.utc).year


def load_season(cache: CacheBackend, season: int | None = None) -> list[dict]:
    season = season or _current_season()
    cache_key = _SEASON_CACHE_KEY_TMPL.format(season=season)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        season_obj = livef1.get_season(season)
        raw = getattr(season_obj, "meetings", None)
        if raw is None and hasattr(season_obj, "get_meetings"):
            raw = season_obj.get_meetings()
        if raw is None:
            return []
        if hasattr(raw, "to_dict"):
            meetings: list[dict] = raw.to_dict(orient="records")
        else:
            meetings = list(raw)
        # livef1 may return Meeting objects instead of dicts; drop them if so
        if meetings and not isinstance(meetings[0], dict):
            meetings = []
        cache.set(cache_key, meetings, ttl_seconds=_SEASON_CACHE_TTL)
        return meetings
    except Exception:
        return []


def current_weekend(cache: CacheBackend) -> tuple[WeekendSchedule, float | None] | None:
    meetings = load_season(cache)
    now = datetime.now(timezone.utc)
    chosen: dict | None = None
    for m in meetings:
        sessions = m.get("sessions") or m.get("Sessions") or []
        if not sessions:
            continue
        last_end = None
        for s in sessions:
            utc = s.get("StartDate") or s.get("date_start")
            try:
                last_end = datetime.fromisoformat(str(utc).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
        if last_end and last_end + timedelta(hours=3) >= now:
            chosen = m
            break
    if chosen is None and meetings:
        chosen = meetings[-1]
    if chosen is None:
        return None

    normalized: list[ScheduleSession] = []
    next_session_ts: float | None = None
    for s in chosen.get("sessions", chosen.get("Sessions", [])):
        ns = _normalize_session(s)
        if ns is None:
            continue
        normalized.append(ns)
        if not ns.is_complete and next_session_ts is None:
            utc_str = s.get("StartDate") or s.get("date_start") or ""
            try:
                next_session_ts = datetime.fromisoformat(
                    str(utc_str).replace("Z", "+00:00")
                ).timestamp()
            except (TypeError, ValueError):
                pass

    for ns in normalized:
        if not ns.is_complete:
            ns.is_next = True
            break

    circuit_id = _circuit_id(chosen)
    return WeekendSchedule(
        circuit=circuit_id,
        country=chosen.get("Country") or chosen.get("country") or "",
        round=int(chosen.get("round") or chosen.get("Round") or 0),
        season=int(chosen.get("season") or chosen.get("Year") or _current_season()),
        sessions=normalized,
    ), next_session_ts


def _circuit_id(meeting: dict) -> str:
    raw = (
        meeting.get("circuit_short_name")
        or meeting.get("Location")
        or meeting.get("circuit_key")
        or meeting.get("Country")
        or "unknown"
    )
    return str(raw).lower().replace(" ", "_")
