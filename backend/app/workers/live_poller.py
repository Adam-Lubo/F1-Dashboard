import asyncio
import logging
import time
from typing import Any

from ..cache.file_cache import CacheBackend
from ..state_machine.machine import StateMachine
from ..models.session import SessionState
from ..services import livef1_client, schedule_service
from ..services.livef1_client import DriverResolver

logger = logging.getLogger(__name__)

_LIVE_INTERVAL = 3
_IDLE_INTERVAL = 30

_LIVE_STATES = (
    SessionState.LIVE,
    SessionState.ARMED,
    SessionState.PAUSED,
    SessionState.RED_FLAG,
    SessionState.SC,
    SessionState.VSC,
    SessionState.YELLOW_FLAG,
)


def _dump(model) -> dict:
    return model.model_dump(mode="json")


class LivePoller:
    def __init__(self, cache: CacheBackend, state_machine: StateMachine):
        self._cache = cache
        self._sm = state_machine
        self._session_key: str | None = None
        self._resolver: DriverResolver | None = None
        self._seen_rc_utcs: set[str] = set()

    async def run(self) -> None:
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Poller error: {e}")

            interval = _LIVE_INTERVAL if self._sm.state in _LIVE_STATES else _IDLE_INTERVAL
            await asyncio.sleep(interval)

    async def _poll_once(self) -> None:
        if self._sm.state in (SessionState.IDLE, SessionState.ENDED):
            return

        loop = asyncio.get_event_loop()
        session = await loop.run_in_executor(None, self._get_live_session)
        if session is None:
            return

        await self._ensure_resolver(session)

        timing = await self._fetch_timing(session)
        if timing:
            self._cache.set("timing", timing, ttl_seconds=30)
            self._sm.on_timing_data()

        positions = await self._fetch_positions(session)
        if positions:
            self._cache.set("positions", positions, ttl_seconds=30)

        await self._fetch_race_control(session)

    async def _ensure_resolver(self, session: Any) -> None:
        key = str(id(session))
        if key == self._session_key and self._resolver is not None:
            return
        loop = asyncio.get_event_loop()
        try:
            self._resolver = await loop.run_in_executor(
                None, DriverResolver.from_session, session
            )
            self._session_key = key
            self._seen_rc_utcs.clear()
        except Exception as e:
            logger.warning(f"DriverResolver build failed: {e}")

    async def _fetch_timing(self, session: Any) -> dict | None:
        try:
            loop = asyncio.get_event_loop()
            timing_rows = await loop.run_in_executor(
                None, livef1_client.load_data, session, "TimingData"
            )
            tire_rows = await loop.run_in_executor(
                None, livef1_client.load_data, session, "TimingAppData"
            )
            tower = livef1_client.parse_timing_snapshot(
                timing_rows, resolver=self._resolver, tire_rows=tire_rows,
            )
            return _dump(tower)
        except Exception as e:
            logger.warning(f"Timing fetch failed: {e}")
            return None

    async def _fetch_positions(self, session: Any) -> dict | None:
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(
                None, livef1_client.load_data, session, "Position.z"
            )
            positions = livef1_client.parse_position_snapshot(
                rows, resolver=self._resolver,
            )
            return _dump(positions)
        except Exception as e:
            logger.warning(f"Position fetch failed: {e}")
            return None

    async def _fetch_race_control(self, session: Any) -> None:
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(
                None, livef1_client.load_data, session, "RaceControlMessages"
            )
            entries = livef1_client.parse_race_control_rows(rows)
            for entry in entries:
                if entry["utc"] in self._seen_rc_utcs:
                    continue
                self._seen_rc_utcs.add(entry["utc"])
                self._sm.on_race_control_message(entry["message"])
            self._cache.set(
                "race_control",
                {"entries": entries, "updated_at": time.time()},
                ttl_seconds=60,
            )
        except Exception as e:
            logger.warning(f"Race control fetch failed: {e}")

    def _get_live_session(self) -> Any:
        import livef1 as lf1
        live_fn = getattr(lf1, "get_live_session", None)
        if callable(live_fn):
            try:
                return live_fn()
            except Exception as e:
                logger.info(f"get_live_session() unavailable, falling back: {e}")

        try:
            result = schedule_service.current_weekend(self._cache)
            if result is None:
                return None
            weekend, _ = result
            candidate = next(
                (s for s in weekend.sessions if s.is_next or not s.is_complete),
                None,
            )
            if candidate is None:
                return None
            return lf1.get_session(
                season=weekend.season,
                meeting_identifier=weekend.circuit,
                session_identifier=candidate.name,
            )
        except Exception as e:
            logger.warning(f"Schedule-based session fallback failed: {e}")
            return None
