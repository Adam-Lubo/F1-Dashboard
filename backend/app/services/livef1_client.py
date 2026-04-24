"""
Wraps the livef1 library and parses raw rows (from JSON fixtures or live data)
into Pydantic models.

Verified column names (from Spa 2024 Race fixture):
  TimingData rows: RacingNumber, Position, GapToLeader,
                   IntervalToPositionAhead_Value (flat str),
                   LastLapTime_Value, LastLapTime_OverallFastest (bool),
                   LastLapTime_PersonalFastest (bool), NumberOfLaps, Retired
  Position.z rows: DriverNo, X, Y, Z, Status (flat rows, no nesting)
  RaceControlMessages: Utc, Lap, Category, Message
  DriverList: RacingNumber, Tla, TeamName
"""
import time
from typing import Any
import livef1

from ..models.timing import TimingEntry, TimingTower, TireCompound
from ..models.position import DriverPosition, TrackPositions

_TEAM_ALIASES: dict[str, str] = {
    "red bull racing": "redbull",
    "oracle red bull racing": "redbull",
    "mclaren": "mclaren",
    "ferrari": "ferrari",
    "scuderia ferrari": "ferrari",
    "mercedes": "mercedes",
    "aston martin": "aston",
    "alpine": "alpine",
    "williams": "williams",
    "rb": "rb",
    "racing bulls": "rb",
    "alphatauri": "rb",
    "kick sauber": "sauber",
    "sauber": "sauber",
    "alfa romeo": "sauber",
    "haas": "haas",
    "haas ferrari": "haas",
    "audi": "audi",
    "cadillac": "cadillac",
}


def _normalize_team(raw: str | None) -> str:
    if not raw:
        return "unknown"
    key = raw.strip().lower()
    return _TEAM_ALIASES.get(key, key.replace(" ", "_"))


class DriverResolver:
    """Maps RacingNumber → (driver_code, team_id) for a specific session."""

    def __init__(self, mapping: dict[str, tuple[str, str]]):
        self._mapping = mapping

    @classmethod
    def from_session(cls, session: Any) -> "DriverResolver":
        try:
            rows = load_data(session, "DriverList")
        except Exception:
            rows = []
        return cls.from_rows(rows)

    @classmethod
    def from_rows(cls, driver_list_rows: list[dict]) -> "DriverResolver":
        mapping: dict[str, tuple[str, str]] = {}
        for row in driver_list_rows:
            num = str(row.get("RacingNumber", row.get("racing_number", ""))).strip()
            tla = (row.get("Tla") or row.get("tla") or "").strip()
            team = row.get("TeamName") or row.get("team_name") or None
            if num and tla:
                mapping[num] = (tla.upper(), _normalize_team(team))
        return cls(mapping)

    def resolve(self, racing_number: str | int) -> tuple[str, str]:
        num = str(racing_number).strip()
        return self._mapping.get(num, ("???", "unknown"))


def get_historical_session(season: int, meeting: str, session_type: str) -> Any:
    return livef1.get_session(
        season=season,
        meeting_identifier=meeting,
        session_identifier=session_type,
    )


def load_data(session: Any, data_name: str) -> list[dict]:
    """Load a data stream from a session and return as list of dicts."""
    import pandas as pd
    df = session.get_data(dataNames=data_name)
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    if isinstance(df, pd.DataFrame):
        return df.to_dict(orient="records")
    return list(df)


def parse_timing_snapshot(
    rows: list[dict],
    resolver: "DriverResolver | None" = None,
    tire_rows: list[dict] | None = None,  # kept for API compat; TimingAppData unavailable
) -> TimingTower:
    """
    Convert TimingData rows into a TimingTower.
    Takes the most recent row per driver (last wins).

    Column names verified against Spa 2024 Race fixture:
    - RacingNumber (str)
    - Position (str)
    - GapToLeader (str)
    - IntervalToPositionAhead_Value (str, flat)
    - LastLapTime_Value (str)
    - LastLapTime_OverallFastest (bool)
    - LastLapTime_PersonalFastest (bool)
    - NumberOfLaps (float or None)
    - Retired (bool)
    """
    if resolver is None:
        resolver = DriverResolver(mapping={})

    # Build latest state per driver via cumulative merge.
    # Rows are sparse incremental updates — a None field means "no change",
    # so we keep the last non-None value for each field rather than replacing
    # the entire record with the latest row.
    latest: dict[str, dict] = {}
    for row in rows:
        num = str(row.get("RacingNumber") or row.get("DriverNo") or "").strip()
        if not num:
            continue
        if num not in latest:
            latest[num] = dict(row)
        else:
            for k, v in row.items():
                if v is not None:
                    latest[num][k] = v

    entries: list[TimingEntry] = []
    fastest_lap_time: str | None = None
    fastest_lap_driver: str | None = None

    for num, row in latest.items():
        tla, team_id = resolver.resolve(num)

        pos_raw = row.get("Position", "")
        try:
            position = int(str(pos_raw).strip())
        except (TypeError, ValueError):
            continue  # skip rows without valid position

        # Gap to leader: P1 always shows "Leader".
        # In the fixture, P1's GapToLeader contains the current lap number
        # string (e.g. "LAP 22") rather than an empty string, so we use
        # position to determine leadership rather than trusting the gap value.
        gap_raw = str(row.get("GapToLeader", "") or "").strip()
        if position == 1:
            gap = "Leader"
        elif gap_raw and gap_raw != "0":
            gap = gap_raw
        else:
            gap = None

        # Interval to car ahead (flat string, not dict)
        interval_raw = str(row.get("IntervalToPositionAhead_Value", "") or "").strip()
        interval = interval_raw if interval_raw else None

        # Last lap time (flat strings + boolean flags)
        last_lap = str(row.get("LastLapTime_Value", "") or "").strip() or None
        is_fastest = bool(row.get("LastLapTime_OverallFastest", False))
        is_pb = bool(row.get("LastLapTime_PersonalFastest", False))

        if is_fastest and last_lap:
            fastest_lap_time = last_lap
            fastest_lap_driver = tla

        retired = bool(row.get("Retired", False))

        entries.append(TimingEntry(
            position=position,
            driver_code=tla,
            team_id=team_id,
            last_lap=last_lap,
            gap=gap,
            interval=interval,
            tire=None,       # TimingAppData unavailable in livef1 for this fixture
            tire_age=None,
            is_fastest_overall=is_fastest,
            is_personal_best=is_pb,
            is_in_battle=False,  # computed below
            is_retired=retired,
            dnf=retired,
        ))

    entries.sort(key=lambda e: e.position)

    # Mark battles: consecutive cars within 0.5s interval
    for i in range(len(entries) - 1):
        nxt = entries[i + 1]
        if not (nxt.interval and nxt.interval.startswith("+")):
            continue
        if "LAP" in nxt.interval.upper():
            continue
        try:
            gap_secs = float(nxt.interval.lstrip("+"))
        except ValueError:
            continue
        if gap_secs <= 0.5:
            entries[i].is_in_battle = True
            entries[i + 1].is_in_battle = True

    return TimingTower(
        entries=entries,
        fastest_lap_driver=fastest_lap_driver,
        fastest_lap_time=fastest_lap_time,
        updated_at=time.time(),
    )


def parse_position_snapshot(
    rows: list[dict],
    resolver: "DriverResolver | None" = None,
) -> TrackPositions:
    """
    Convert Position.z rows into TrackPositions.
    Rows are flat: DriverNo, X, Y, Z, Status.
    X/Y normalized to [-1, 1].
    """
    if resolver is None:
        resolver = DriverResolver(mapping={})

    # Take latest non-pit row per driver
    latest: dict[str, dict] = {}
    for row in rows:
        num = str(row.get("DriverNo", row.get("RacingNumber", ""))).strip()
        status = str(row.get("Status", "") or "")
        if num and status not in ("OffTrack", "Pit"):
            latest[num] = row

    xs = [float(r.get("X", 0) or 0) for r in latest.values()]
    ys = [float(r.get("Y", 0) or 0) for r in latest.values()]
    x_min, x_max = (min(xs), max(xs)) if xs else (0, 1)
    y_min, y_max = (min(ys), max(ys)) if ys else (0, 1)
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1

    drivers: list[DriverPosition] = []
    for num, row in latest.items():
        tla, team_id = resolver.resolve(num)
        raw_x = float(row.get("X", 0) or 0)
        raw_y = float(row.get("Y", 0) or 0)
        drivers.append(DriverPosition(
            driver_code=tla,
            team_id=team_id,
            x=(raw_x - x_min) / x_range * 2 - 1,
            y=(raw_y - y_min) / y_range * 2 - 1,
        ))

    return TrackPositions(drivers=drivers, updated_at=time.time())


def classify_rc_message(message: str) -> str:
    """Categorize a race control message for the frontend log."""
    m = message.upper()
    if any(k in m for k in ["RED FLAG", "YELLOW", "GREEN LIGHT", "CHEQUERED FLAG", "TRACK CLEAR"]):
        return "Flag"
    if "SAFETY CAR" in m or "VSC" in m or "VIRTUAL SAFETY CAR" in m:
        return "SafetyCar"
    if "DRS" in m:
        return "Drs"
    if any(k in m for k in ["PENALTY", "INVESTIGATION", "INCIDENT", "NOTED"]):
        return "CarEvent"
    return "Other"


def parse_race_control_rows(rows: list[dict]) -> list[dict]:
    """
    Return list of {utc, lap, category, message} dicts sorted by UTC ascending.
    Uses the Category column if available, otherwise classifies from message.
    """
    out: list[dict] = []
    for r in rows:
        msg = (r.get("Message") or r.get("message") or "").strip()
        if not msg:
            continue
        utc = r.get("Utc") or r.get("utc") or r.get("Timestamp") or ""
        lap_raw = r.get("Lap") or r.get("lap")
        try:
            lap = int(lap_raw) if lap_raw is not None else None
        except (TypeError, ValueError):
            lap = None
        # Prefer pre-computed Category from livef1 if available
        category = r.get("Category") or r.get("category") or classify_rc_message(msg)
        out.append({
            "utc": str(utc),
            "lap": lap,
            "category": category,
            "message": msg,
        })
    out.sort(key=lambda x: x["utc"])
    return out
