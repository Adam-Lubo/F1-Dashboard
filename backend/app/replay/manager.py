import json
from pathlib import Path
from ..models.timing import TimingTower
from ..models.position import TrackPositions
from ..services.livef1_client import (
    parse_timing_snapshot, parse_position_snapshot,
    parse_race_control_rows, DriverResolver,
)


def _safe_load(path: Path) -> list[dict]:
    return json.loads(path.read_text()) if path.exists() else []


class ReplayManager:
    def __init__(self, fixtures_dir: Path):
        self._fixtures_dir = fixtures_dir
        self._timing_rows = _safe_load(fixtures_dir / "timingdata.json")
        self._tire_rows = _safe_load(fixtures_dir / "timingappdata.json")
        self._position_rows = _safe_load(fixtures_dir / "position_z.json")
        self._rc_rows = _safe_load(fixtures_dir / "racecontrolmessages.json")
        driver_list_rows = _safe_load(fixtures_dir / "driverlist.json")
        self._resolver = DriverResolver.from_rows(driver_list_rows)

        # Determine total laps from timing data
        laps = [r.get("NumberOfLaps", r.get("number_of_laps", 0)) for r in self._timing_rows]
        valid_laps = []
        for l in laps:
            try:
                v = float(l)
                if v > 0:
                    valid_laps.append(int(v))
            except (TypeError, ValueError):
                pass
        self.total_laps = max(valid_laps) if valid_laps else 44  # Spa 2024 = 44 laps
        self._current_lap = 1
        self._last_rc_utc: str | None = None

    @property
    def current_lap(self) -> int:
        return self._current_lap

    @property
    def resolver(self) -> DriverResolver:
        return self._resolver

    def seek(self, lap: int) -> tuple[int, list[dict]]:
        """
        Move to `lap`. Returns (clamped_lap, new_rc_messages_since_previous_seek).
        """
        self._current_lap = max(1, min(lap, self.total_laps))

        all_up_to_now = parse_race_control_rows(
            self._rows_at_lap(self._rc_rows, self._current_lap)
        )
        new_msgs = [m for m in all_up_to_now
                    if self._last_rc_utc is None or m["utc"] > self._last_rc_utc]
        if all_up_to_now:
            self._last_rc_utc = all_up_to_now[-1]["utc"]
        return self._current_lap, new_msgs

    def _rows_at_lap(self, rows: list[dict], lap: int) -> list[dict]:
        result = []
        for row in rows:
            row_lap = (
                row.get("NumberOfLaps") or
                row.get("number_of_laps") or
                row.get("Lap") or
                row.get("lap")
            )
            if row_lap is None:
                result.append(row)  # always include rows with no lap marker (init rows)
                continue
            try:
                if int(float(row_lap)) <= lap:
                    result.append(row)
            except (TypeError, ValueError):
                result.append(row)
        return result

    def get_timing(self) -> TimingTower:
        rows = self._rows_at_lap(self._timing_rows, self._current_lap)
        tire_rows = self._rows_at_lap(self._tire_rows, self._current_lap)
        return parse_timing_snapshot(rows, resolver=self._resolver, tire_rows=tire_rows)

    def get_positions(self) -> TrackPositions:
        rows = self._rows_at_lap(self._position_rows, self._current_lap)
        return parse_position_snapshot(rows, resolver=self._resolver)

    def get_race_control_log(self) -> list[dict]:
        return parse_race_control_rows(
            self._rows_at_lap(self._rc_rows, self._current_lap)
        )
