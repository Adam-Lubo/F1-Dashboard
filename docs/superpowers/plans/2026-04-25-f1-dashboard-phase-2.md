# F1 Dashboard Phase 2 — Derived Aggregates + Live Polling

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the derived-aggregate endpoints that the design spec defers from skeleton v1 (sector dominance, gap chart, tire strategy, undercut threat, championship implications, etc.), plus fix two pieces of skeleton-v1 technical debt (`/schedule` Meeting parsing, live poller integration).

**Why this phase:** the skeleton serves "current state" snapshots well, but most rich frontend modules need *history*: lap-by-lap times, sector deltas, stint progressions, position changes. This plan introduces a lap-history aggregator as the foundation, then layers the derived endpoints on top.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│  TimingData rows (sparse, cumulative)                           │
│      ↓                                                          │
│  LapHistoryAggregator (services/lap_history.py)                 │
│      ↓ scans rows in order, emits LapEntry on each              │
│        LastLapTime_Value transition per driver                  │
│      ↓                                                          │
│  cache.set("lap_history", {driver_code: [LapEntry, …]})         │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────────────────┐
        │                   │                               │
        ↓                   ↓                               ↓
  /sectors             /gap-chart                      /long-run-pace
  /improvements        /championship-implications      /session-notes

┌─────────────────────────────────────────────────────────────────┐
│  FastF1 lap+stint data (separate cache, fixture-backed)         │
│      ↓                                                          │
│  cache.set("stints", {driver_code: [StintEntry, …]})            │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────────────────┐
        │                   │                               │
        ↓                   ↓                               ↓
  /tire-strategy       /tire-usage                    /undercut-threat
```

Endpoints read from cache only. The replay manager and live poller are responsible for writing the aggregates. No direct livef1 calls from routers.

---

## Scope

### Included

- Lap history aggregator (foundation)
- FastF1 integration for tire/stint data
- 9 new endpoints: sectors, gap-chart, long-run-pace, improvements, tire-strategy, tire-usage, undercut-threat, championship-implications, session-notes
- Fix `/schedule` (proper livef1 `Season` → `Meeting` traversal with field-by-field extraction)
- Fix live poller (replace empty `_get_live_session` placeholder with `RealF1Client` SignalR integration OR explicit "polling not supported" guard with documented manual replay-mode workaround)
- Replay manager populates all new caches on each `seek()` so the frontend dev loop covers every endpoint
- Tests for every aggregator and every endpoint

### Deferred to a future phase

- Post-session LLM summary
- Team radio transcription (Whisper)
- ML predictions runner (the mar-antaya fork itself — this phase still only reads its output file)
- Storylines (curation pipeline TBD)
- Mobile-optimized layout (frontend concern)

---

## Verified data findings (from Spa 2024 fixture)

These were measured from the actual fixture data in this repo. Do not assume — implement against these column shapes.

### TimingData (53,040 rows)

| Column | Type | Notes |
|---|---|---|
| `DriverNo` | str | **Primary driver key.** Always populated. |
| `RacingNumber` | str \| None | Only populated in 20 init rows. **Do not use as primary.** |
| `NumberOfLaps` | float \| None | Sparse — only present in some rows. |
| `LastLapTime_Value` | str | e.g. `"1:48.564"`. Empty string = no lap completed yet. |
| `LastLapTime_OverallFastest` | bool | Session-fastest flag for this lap. |
| `LastLapTime_PersonalFastest` | bool | Driver PB flag. |
| `BestLapTime_Value` | str | Driver's best of session. |
| `BestLapTime_Lap` | float | Lap number of the best lap. |
| `Position` | str | Current race position, e.g. `"1"`. Sparse. |
| `GapToLeader` | str | `"+5.123"` for non-leaders; `"LAP 1"` for leader. Sparse. |
| `IntervalToPositionAhead_Value` | str | Flat string, **not nested**. |
| `Sectors_0_Value` | str | S1 time, e.g. `"48.663"`. **0-indexed: S1=Sectors_0, S2=Sectors_1, S3=Sectors_2.** `Sectors_3_Value` is never populated. |
| `Sectors_1_Value` | str | S2 time. |
| `Sectors_2_Value` | str | S3 time. |
| `Sectors_N_OverallFastest` | bool | Per-sector overall-fastest flag. |
| `Sectors_N_PersonalFastest` | bool | Per-sector driver PB. |
| `InPit` | bool | Driver currently in pit. |
| `Retired` | bool | DNF flag. |

### What's NOT in TimingData

- **Tire compound** (`Tyre`, `Compound`, etc.) — none of these columns exist. Use FastF1.
- **Pit stop count by lap** — `NumberOfPitStops` exists but is rarely populated in the fixture. Use FastF1's pit data.
- **Stint boundaries** — derive from FastF1 `lap_data.Stint` and `lap_data.Compound`.

### RaceControlMessages

Already covered in skeleton v1. Columns: `Utc`, `Lap`, `Category`, `Flag`, `Scope`, `Message`, `Status`, `Sector`.

### SessionData

Has `Lap`, `TrackStatus`, `SessionStatus`. Mostly null in the Spa 2024 fixture — not load-bearing for this phase.

---

## Tech stack (additions)

- **fastf1** ≥ 3.4.0 (Python) — historical lap data with tire compounds, stints, pit stops
- All other deps unchanged from phase 1

---

## Task 1: FastF1 integration + Spa 2024 stint fixture

**Files:**
- Modify: `backend/pyproject.toml` (add fastf1 dependency)
- Create: `backend/tests/fixtures/download_spa_2024_fastf1.py`
- Create: `backend/tests/fixtures/spa_2024/fastf1_laps.json`
- Create: `backend/docs/fastf1-api.md` (record verified API surface)

### Step 1: Add fastf1 dependency

Edit `backend/pyproject.toml`, add to dependencies:

```toml
"fastf1>=3.4.0",
```

Install:

```bash
cd backend && source .venv/bin/activate && pip install -e ".[dev]"
```

### Step 2: Verify FastF1 API surface

```bash
python3 -c "
import fastf1
print('version:', fastf1.__version__)
session = fastf1.get_session(2024, 'Belgium', 'R')
session.load(telemetry=False, weather=False, messages=False)
laps = session.laps
print('laps columns:', list(laps.columns))
print('rows:', len(laps))
print('sample:', laps.iloc[10][['Driver', 'LapNumber', 'LapTime', 'Compound', 'TyreLife', 'Stint']].to_dict())
"
```

Record observed columns and a sample row in `backend/docs/fastf1-api.md`. Expected columns include `Driver`, `LapNumber`, `LapTime`, `Compound`, `TyreLife`, `Stint`, `PitInTime`, `PitOutTime`. **If any of these are missing or named differently, update Tasks 3, 8, 9, 10 before implementing.**

### Step 3: Write download script

```python
# backend/tests/fixtures/download_spa_2024_fastf1.py
"""
Download Spa 2024 lap-level data via FastF1 (for tire compound + stint info).

Run once. Output is committed to the repo as fastf1_laps.json.
"""
import json
import sys
from pathlib import Path

import fastf1
import pandas as pd

OUT_PATH = Path(__file__).parent / "spa_2024" / "fastf1_laps.json"
OUT_PATH.parent.mkdir(exist_ok=True)


def main():
    cache_dir = Path(__file__).parent.parent.parent / "cache" / "fastf1"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))

    print("Loading 2024 Belgian GP Race via FastF1...")
    session = fastf1.get_session(2024, "Belgium", "R")
    session.load(telemetry=False, weather=False, messages=False)

    laps = session.laps
    cols = ["Driver", "DriverNumber", "LapNumber", "LapTime",
            "Sector1Time", "Sector2Time", "Sector3Time",
            "Compound", "TyreLife", "FreshTyre", "Stint",
            "PitInTime", "PitOutTime", "TrackStatus", "Position"]
    keep = [c for c in cols if c in laps.columns]
    df = laps[keep].copy()

    # Convert timedeltas to "M:SS.sss" strings (or null)
    for c in ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "PitInTime", "PitOutTime"]:
        if c in df.columns:
            df[c] = df[c].apply(_fmt_td)

    records = json.loads(df.to_json(orient="records"))
    OUT_PATH.write_text(json.dumps(records, indent=2))
    print(f"Saved {len(records)} laps → {OUT_PATH.name}")


def _fmt_td(td) -> str | None:
    if pd.isna(td):
        return None
    total = td.total_seconds()
    minutes = int(total // 60)
    seconds = total - minutes * 60
    return f"{minutes}:{seconds:06.3f}" if minutes else f"{seconds:.3f}"


if __name__ == "__main__":
    main()
```

### Step 4: Run the script (requires network)

```bash
cd backend && python3 tests/fixtures/download_spa_2024_fastf1.py
```

### Step 5: Add fastf1_laps.json to .gitignore if too large

```bash
ls -lh backend/tests/fixtures/spa_2024/fastf1_laps.json
# If > 5MB, add to .gitignore
```

### Step 6: Commit

```bash
git add backend/pyproject.toml \
        backend/tests/fixtures/download_spa_2024_fastf1.py \
        backend/docs/fastf1-api.md
# Add fastf1_laps.json only if under 5MB
git commit -m "feat: FastF1 integration with Spa 2024 lap+stint fixture"
```

---

## Task 2: Lap history aggregator

**Files:**
- Create: `backend/app/models/lap_history.py`
- Create: `backend/app/services/lap_history.py`
- Test: `backend/tests/unit/test_lap_history.py`

The aggregator walks TimingData rows in order, maintains cumulative per-driver state, and emits a `LapEntry` every time `LastLapTime_Value` changes for a driver. The output is `{driver_code: [LapEntry, …]}`.

### Step 1: Pydantic model

```python
# backend/app/models/lap_history.py
from pydantic import BaseModel


class LapEntry(BaseModel):
    lap: int
    lap_time: str                  # "1:48.564"
    s1: str | None = None
    s2: str | None = None
    s3: str | None = None
    s1_overall_fastest: bool = False
    s2_overall_fastest: bool = False
    s3_overall_fastest: bool = False
    s1_personal_best: bool = False
    s2_personal_best: bool = False
    s3_personal_best: bool = False
    position: int | None = None
    gap_to_leader: str | None = None
    is_overall_fastest: bool = False
    is_personal_best: bool = False
    in_pit: bool = False


class LapHistory(BaseModel):
    laps: dict[str, list[LapEntry]]  # keyed by driver code (TLA)
    updated_at: float = 0.0
```

### Step 2: Aggregator implementation

```python
# backend/app/services/lap_history.py
"""
Build a per-driver lap-by-lap history from TimingData rows.

Algorithm:
  1. Walk rows in order.
  2. For each row, maintain cumulative state per driver (sparse merge —
     only update fields where the new value is non-None and non-empty).
  3. When `LastLapTime_Value` changes from the previous value for a driver,
     emit a LapEntry capturing the cumulative state at that moment.

Driver key: prefer `RacingNumber`; fall back to `DriverNo`. Most rows have
`RacingNumber=None` so the fallback is the load-bearing path.
"""
import time
from typing import Any

from ..models.lap_history import LapEntry, LapHistory
from .livef1_client import DriverResolver


def _is_meaningful(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    return True


def build_lap_history(
    rows: list[dict],
    resolver: DriverResolver | None = None,
) -> LapHistory:
    if resolver is None:
        resolver = DriverResolver(mapping={})

    state: dict[str, dict] = {}
    last_lap_seen: dict[str, str] = {}
    history: dict[str, list[LapEntry]] = {}

    for row in rows:
        num = str(row.get("RacingNumber") or row.get("DriverNo") or "").strip()
        if not num:
            continue

        cur = state.setdefault(num, {})
        for k, v in row.items():
            if _is_meaningful(v):
                cur[k] = v

        new_lap_time = row.get("LastLapTime_Value")
        if not (isinstance(new_lap_time, str) and new_lap_time.strip()):
            continue
        if last_lap_seen.get(num) == new_lap_time:
            continue
        last_lap_seen[num] = new_lap_time

        try:
            lap_no = int(float(cur.get("NumberOfLaps") or 0))
        except (TypeError, ValueError):
            lap_no = 0
        if lap_no <= 0:
            continue

        try:
            position = int(str(cur.get("Position") or "0").strip())
        except (TypeError, ValueError):
            position = None

        tla, _ = resolver.resolve(num)
        entry = LapEntry(
            lap=lap_no,
            lap_time=new_lap_time.strip(),
            s1=_str_or_none(cur.get("Sectors_0_Value")),
            s2=_str_or_none(cur.get("Sectors_1_Value")),
            s3=_str_or_none(cur.get("Sectors_2_Value")),
            s1_overall_fastest=bool(row.get("Sectors_0_OverallFastest", False)),
            s2_overall_fastest=bool(row.get("Sectors_1_OverallFastest", False)),
            s3_overall_fastest=bool(row.get("Sectors_2_OverallFastest", False)),
            s1_personal_best=bool(row.get("Sectors_0_PersonalFastest", False)),
            s2_personal_best=bool(row.get("Sectors_1_PersonalFastest", False)),
            s3_personal_best=bool(row.get("Sectors_2_PersonalFastest", False)),
            position=position,
            gap_to_leader=_str_or_none(cur.get("GapToLeader")),
            is_overall_fastest=bool(row.get("LastLapTime_OverallFastest", False)),
            is_personal_best=bool(row.get("LastLapTime_PersonalFastest", False)),
            in_pit=bool(cur.get("InPit", False)),
        )
        history.setdefault(tla, []).append(entry)

    return LapHistory(laps=history, updated_at=time.time())


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None
```

### Step 3: Tests

```python
# backend/tests/unit/test_lap_history.py
import json
import pytest
from pathlib import Path

from app.services.lap_history import build_lap_history
from app.services.livef1_client import DriverResolver

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


@pytest.fixture
def all_rows():
    return json.loads((FIXTURES / "timingdata.json").read_text())


@pytest.fixture
def resolver():
    rows = json.loads((FIXTURES / "driverlist.json").read_text())
    return DriverResolver.from_rows(rows)


def test_lap_history_has_entries_per_driver(all_rows, resolver):
    h = build_lap_history(all_rows, resolver)
    # Race winner Russell completed all 44 laps
    assert "RUS" in h.laps
    assert len(h.laps["RUS"]) >= 40  # account for safety-car / pit anomalies


def test_lap_history_lap_numbers_monotonic(all_rows, resolver):
    h = build_lap_history(all_rows, resolver)
    rus = h.laps["RUS"]
    laps = [e.lap for e in rus]
    assert laps == sorted(laps)


def test_lap_times_are_well_formed(all_rows, resolver):
    h = build_lap_history(all_rows, resolver)
    for entries in h.laps.values():
        for e in entries:
            # "1:48.564" or "48.564" (sub-minute lap, rare but possible)
            assert ":" in e.lap_time or "." in e.lap_time


def test_overall_fastest_flag_appears_at_least_once(all_rows, resolver):
    h = build_lap_history(all_rows, resolver)
    has_fastest = False
    for entries in h.laps.values():
        if any(e.is_overall_fastest for e in entries):
            has_fastest = True
            break
    assert has_fastest, "no driver ever holds OverallFastest in fixture"


def test_per_driver_lap_count_does_not_exceed_44(all_rows, resolver):
    h = build_lap_history(all_rows, resolver)
    for tla, entries in h.laps.items():
        assert max(e.lap for e in entries) <= 44, f"{tla} has lap > 44"
```

### Step 4: Run tests

```bash
cd backend && pytest tests/unit/test_lap_history.py -v
```

Expected: 5 passed.

### Step 5: Commit

```bash
git add backend/app/models/lap_history.py \
        backend/app/services/lap_history.py \
        backend/tests/unit/test_lap_history.py
git commit -m "feat: lap history aggregator (per-driver lap-by-lap entries)"
```

---

## Task 3: Stint aggregator (FastF1-backed)

**Files:**
- Create: `backend/app/models/stint.py`
- Create: `backend/app/services/stint_aggregator.py`
- Test: `backend/tests/unit/test_stint_aggregator.py`

Reads the FastF1 lap fixture and returns per-driver stint history.

### Step 1: Pydantic model

```python
# backend/app/models/stint.py
from pydantic import BaseModel
from .timing import TireCompound


class StintEntry(BaseModel):
    stint_number: int
    compound: TireCompound | None = None
    start_lap: int
    end_lap: int            # last completed lap on this stint (inclusive)
    laps_completed: int
    fresh_tyre: bool = False


class StintHistory(BaseModel):
    stints: dict[str, list[StintEntry]]  # keyed by driver code (TLA)
    updated_at: float = 0.0
```

### Step 2: Aggregator

```python
# backend/app/services/stint_aggregator.py
"""
Build per-driver stint history from FastF1 lap data.

FastF1 columns used (verify in Task 1):
  Driver        — TLA, e.g. "VER"
  LapNumber     — 1-indexed lap number
  Compound      — "SOFT" | "MEDIUM" | "HARD" | "INTERMEDIATE" | "WET"
  Stint         — 1-indexed stint number per driver
  TyreLife      — number of laps on this set of tyres at this lap
  FreshTyre     — bool, whether this stint started on a new set
"""
import time

from ..models.stint import StintEntry, StintHistory
from ..models.timing import TireCompound

_COMPOUND_MAP = {
    "SOFT": TireCompound.SOFT,
    "MEDIUM": TireCompound.MEDIUM,
    "HARD": TireCompound.HARD,
    "INTERMEDIATE": TireCompound.INTERMEDIATE,
    "WET": TireCompound.WET,
}


def build_stint_history(fastf1_laps: list[dict]) -> StintHistory:
    by_driver: dict[str, dict[int, list[dict]]] = {}
    for row in fastf1_laps:
        tla = row.get("Driver")
        stint_no = row.get("Stint")
        if not tla or stint_no is None:
            continue
        try:
            stint_no = int(stint_no)
        except (TypeError, ValueError):
            continue
        by_driver.setdefault(tla, {}).setdefault(stint_no, []).append(row)

    out: dict[str, list[StintEntry]] = {}
    for tla, stints in by_driver.items():
        ordered: list[StintEntry] = []
        for sn in sorted(stints.keys()):
            laps = stints[sn]
            lap_nums = [int(l["LapNumber"]) for l in laps if l.get("LapNumber") is not None]
            if not lap_nums:
                continue
            compound_raw = next((l.get("Compound") for l in laps if l.get("Compound")), None)
            compound = _COMPOUND_MAP.get(str(compound_raw).upper()) if compound_raw else None
            fresh = bool(laps[0].get("FreshTyre", False))
            ordered.append(StintEntry(
                stint_number=sn,
                compound=compound,
                start_lap=min(lap_nums),
                end_lap=max(lap_nums),
                laps_completed=len(lap_nums),
                fresh_tyre=fresh,
            ))
        out[tla] = ordered

    return StintHistory(stints=out, updated_at=time.time())
```

### Step 3: Tests

```python
# backend/tests/unit/test_stint_aggregator.py
import json
import pytest
from pathlib import Path

from app.services.stint_aggregator import build_stint_history

FIXTURE = Path(__file__).parent.parent / "fixtures" / "spa_2024" / "fastf1_laps.json"


@pytest.fixture
def laps():
    if not FIXTURE.exists():
        pytest.skip("fastf1_laps.json missing — run download_spa_2024_fastf1.py")
    return json.loads(FIXTURE.read_text())


def test_stints_per_driver(laps):
    h = build_stint_history(laps)
    # Most drivers run 1–3 stints
    for tla, stints in h.stints.items():
        assert 1 <= len(stints) <= 5, f"{tla} has {len(stints)} stints"


def test_stint_lap_ranges_are_contiguous(laps):
    h = build_stint_history(laps)
    for tla, stints in h.stints.items():
        for i in range(1, len(stints)):
            prev = stints[i - 1]
            cur = stints[i]
            assert cur.start_lap >= prev.end_lap, \
                f"{tla} stint {cur.stint_number} starts before previous ended"


def test_compound_is_recognized(laps):
    h = build_stint_history(laps)
    found_compound = any(
        s.compound is not None
        for stints in h.stints.values()
        for s in stints
    )
    assert found_compound
```

### Step 4: Commit

```bash
git add backend/app/models/stint.py \
        backend/app/services/stint_aggregator.py \
        backend/tests/unit/test_stint_aggregator.py
git commit -m "feat: stint history aggregator from FastF1 lap data"
```

---

## Task 4: Replay manager wiring + cache writing

**Files:**
- Modify: `backend/app/replay/manager.py`
- Modify: `backend/app/main.py` (replay-mode lifespan)

The replay manager needs to populate `lap_history` and `stints` caches alongside the existing `timing` / `positions` / `race_control` caches. This way every endpoint built in subsequent tasks works against replay data.

### Step 1: Add aggregator hooks to ReplayManager

Add these methods to `ReplayManager` (after `get_race_control_log`):

```python
def get_lap_history(self) -> LapHistory:
    from ..services.lap_history import build_lap_history
    rows = self._rows_at_lap(self._timing_rows, self._current_lap)
    return build_lap_history(rows, resolver=self._resolver)

def get_stint_history(self) -> StintHistory:
    from ..services.stint_aggregator import build_stint_history
    if not self._fastf1_laps:
        return StintHistory(stints={}, updated_at=0.0)
    # Filter laps to current_lap-and-prior so the timeline matches replay state
    capped = [l for l in self._fastf1_laps
              if l.get("LapNumber") is not None and int(l["LapNumber"]) <= self._current_lap]
    return build_stint_history(capped)
```

Add to `__init__`:

```python
self._fastf1_laps = _safe_load(fixtures_dir / "fastf1_laps.json")
```

Add the imports at the top:

```python
from ..models.lap_history import LapHistory
from ..models.stint import StintHistory
```

### Step 2: Update seek endpoint and lifespan to write the new caches

In `backend/app/routers/replay.py`, update `seek_to_lap`:

```python
cache.set("lap_history", manager.get_lap_history().model_dump(mode="json"), ttl_seconds=3600)
cache.set("stints",      manager.get_stint_history().model_dump(mode="json"), ttl_seconds=3600)
```

In `backend/app/main.py`, update the replay-mode lifespan branch to seed the same caches at startup.

### Step 3: Commit

```bash
git add backend/app/replay/manager.py \
        backend/app/routers/replay.py \
        backend/app/main.py
git commit -m "feat: replay manager populates lap_history and stints caches on seek"
```

---

## Task 5: Sector dominance endpoint

**Files:**
- Create: `backend/app/models/sectors.py`
- Create: `backend/app/routers/sectors.py`
- Test: `backend/tests/integration/test_sectors_router.py`

Three cards (S1, S2, S3) showing the session-fastest driver and the runners-up deltas in that sector.

### Step 1: Model

```python
# backend/app/models/sectors.py
from pydantic import BaseModel


class SectorRanking(BaseModel):
    driver_code: str
    team_id: str
    time: str           # "48.663"
    delta: float        # seconds back of fastest (0 for the leader)


class SectorCard(BaseModel):
    sector: int                 # 1, 2, or 3
    fastest_driver: str | None
    fastest_time: str | None
    rankings: list[SectorRanking]


class SectorDominance(BaseModel):
    cards: list[SectorCard]     # always 3 entries (S1/S2/S3)
    updated_at: float = 0.0
```

### Step 2: Router

```python
# backend/app/routers/sectors.py
from fastapi import APIRouter
from ..main import cache
from ..models.sectors import SectorDominance, SectorCard, SectorRanking
from ..models.lap_history import LapHistory

router = APIRouter()


def _parse_secs(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


@router.get("/sectors", response_model=SectorDominance)
def get_sectors():
    raw = cache.get("lap_history")
    if not raw:
        return SectorDominance(cards=_empty_cards())
    lh = LapHistory(**raw)

    # For each driver, take their best sector value across all laps in history.
    cards: list[SectorCard] = []
    for sector_idx in (1, 2, 3):
        attr = f"s{sector_idx}"
        best_per_driver: dict[str, tuple[float, str]] = {}
        for tla, entries in lh.laps.items():
            best: float | None = None
            best_str: str | None = None
            for e in entries:
                t = _parse_secs(getattr(e, attr))
                if t is None or t <= 0:
                    continue
                if best is None or t < best:
                    best = t
                    best_str = getattr(e, attr)
            if best is not None and best_str is not None:
                best_per_driver[tla] = (best, best_str)

        ranked = sorted(best_per_driver.items(), key=lambda kv: kv[1][0])
        if not ranked:
            cards.append(SectorCard(sector=sector_idx, fastest_driver=None,
                                    fastest_time=None, rankings=[]))
            continue
        leader_tla, (leader_secs, leader_str) = ranked[0]
        rankings = [SectorRanking(
            driver_code=tla,
            team_id="",   # filled in below if we have a resolver-like lookup
            time=ts,
            delta=round(secs - leader_secs, 3),
        ) for tla, (secs, ts) in ranked[:8]]  # top 8 only

        cards.append(SectorCard(
            sector=sector_idx,
            fastest_driver=leader_tla,
            fastest_time=leader_str,
            rankings=rankings,
        ))

    return SectorDominance(cards=cards, updated_at=lh.updated_at)


def _empty_cards() -> list[SectorCard]:
    return [SectorCard(sector=i, fastest_driver=None, fastest_time=None, rankings=[])
            for i in (1, 2, 3)]
```

### Step 3: Test

```python
# backend/tests/integration/test_sectors_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_sectors_empty_without_history():
    cache.delete("lap_history")
    resp = client.get("/sectors")
    assert resp.status_code == 200
    cards = resp.json()["cards"]
    assert len(cards) == 3
    assert all(c["fastest_driver"] is None for c in cards)


def test_sectors_picks_fastest_with_seeded_history():
    cache.set("lap_history", {
        "laps": {
            "VER": [{"lap": 1, "lap_time": "1:46.000",
                     "s1": "30.500", "s2": "35.000", "s3": "40.500"}],
            "NOR": [{"lap": 1, "lap_time": "1:46.300",
                     "s1": "30.300", "s2": "35.500", "s3": "40.500"}],
        },
        "updated_at": time.time(),
    }, ttl_seconds=60)

    resp = client.get("/sectors")
    cards = {c["sector"]: c for c in resp.json()["cards"]}
    assert cards[1]["fastest_driver"] == "NOR"
    assert cards[2]["fastest_driver"] == "VER"
    # tied S3 — first encountered wins
    assert cards[3]["fastest_driver"] in ("VER", "NOR")
```

### Step 4: Register + commit

```python
# backend/app/main.py — add to imports + include_router calls
from .routers import sectors as sectors_router
app.include_router(sectors_router.router)
```

```bash
git add backend/app/models/sectors.py \
        backend/app/routers/sectors.py \
        backend/tests/integration/test_sectors_router.py \
        backend/app/main.py
git commit -m "feat: GET /sectors sector dominance endpoint"
```

---

## Task 6: Gap-to-leader chart endpoint

**Files:**
- Create: `backend/app/models/gap_chart.py`
- Create: `backend/app/routers/gap_chart.py`
- Test: `backend/tests/integration/test_gap_chart_router.py`

Returns lap-by-lap gap-to-leader series for the top N drivers (default 5). The frontend renders this as a line chart.

### Step 1: Model + router

```python
# backend/app/models/gap_chart.py
from pydantic import BaseModel


class GapPoint(BaseModel):
    lap: int
    gap_seconds: float | None  # None = no data / leader


class DriverGapSeries(BaseModel):
    driver_code: str
    team_id: str
    points: list[GapPoint]


class GapChart(BaseModel):
    series: list[DriverGapSeries]
    updated_at: float = 0.0
```

```python
# backend/app/routers/gap_chart.py
import re
from fastapi import APIRouter
from ..main import cache
from ..models.gap_chart import GapChart, GapPoint, DriverGapSeries
from ..models.lap_history import LapHistory

router = APIRouter()

_GAP_NUMERIC = re.compile(r"^\+(\d+\.\d+)$")


def _parse_gap(s: str | None) -> float | None:
    if not s:
        return None
    m = _GAP_NUMERIC.match(s.strip())
    if m:
        return float(m.group(1))
    if s.strip().upper().startswith("LAP"):
        return None  # lapped or leader
    return None


@router.get("/gap-chart", response_model=GapChart)
def get_gap_chart(top: int = 5):
    raw = cache.get("lap_history")
    if not raw:
        return GapChart(series=[])
    lh = LapHistory(**raw)

    # Determine leaderboard from the latest lap each driver completed
    final_pos: list[tuple[str, int]] = []
    for tla, entries in lh.laps.items():
        if not entries:
            continue
        last = entries[-1]
        if last.position is not None:
            final_pos.append((tla, last.position))
    final_pos.sort(key=lambda kv: kv[1])
    chosen = [tla for tla, _ in final_pos[:top]]

    series: list[DriverGapSeries] = []
    for tla in chosen:
        pts = [GapPoint(lap=e.lap, gap_seconds=_parse_gap(e.gap_to_leader))
               for e in lh.laps[tla]]
        series.append(DriverGapSeries(driver_code=tla, team_id="", points=pts))

    return GapChart(series=series, updated_at=lh.updated_at)
```

### Step 2: Test + register

```python
# backend/tests/integration/test_gap_chart_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_gap_chart_empty_without_history():
    cache.delete("lap_history")
    resp = client.get("/gap-chart")
    assert resp.status_code == 200
    assert resp.json()["series"] == []


def test_gap_chart_returns_top_drivers():
    cache.set("lap_history", {
        "laps": {
            "VER": [{"lap": 1, "lap_time": "1:46.0", "position": 1, "gap_to_leader": "LAP 1"},
                    {"lap": 2, "lap_time": "1:45.9", "position": 1, "gap_to_leader": "LAP 2"}],
            "NOR": [{"lap": 1, "lap_time": "1:46.5", "position": 2, "gap_to_leader": "+0.500"},
                    {"lap": 2, "lap_time": "1:46.4", "position": 2, "gap_to_leader": "+1.000"}],
        },
        "updated_at": time.time(),
    }, ttl_seconds=60)
    resp = client.get("/gap-chart?top=2")
    series = resp.json()["series"]
    assert len(series) == 2
    nor = next(s for s in series if s["driver_code"] == "NOR")
    assert nor["points"][1]["gap_seconds"] == 1.0
    ver = next(s for s in series if s["driver_code"] == "VER")
    assert ver["points"][0]["gap_seconds"] is None  # leader → None
```

```python
# backend/app/main.py — register
from .routers import gap_chart as gap_chart_router
app.include_router(gap_chart_router.router)
```

```bash
git add backend/app/models/gap_chart.py \
        backend/app/routers/gap_chart.py \
        backend/tests/integration/test_gap_chart_router.py \
        backend/app/main.py
git commit -m "feat: GET /gap-chart lap-by-lap gap series"
```

---

## Task 7: Long-run pace endpoint

**Files:**
- Create: `backend/app/models/long_run_pace.py`
- Create: `backend/app/routers/long_run_pace.py`
- Test: `backend/tests/integration/test_long_run_pace_router.py`

For practice sessions: per-driver moving average over their completed flying laps, excluding in-laps and out-laps. Frontend renders as a multi-driver line chart.

### Step 1: Model

```python
# backend/app/models/long_run_pace.py
from pydantic import BaseModel


class PacePoint(BaseModel):
    lap: int
    lap_time_seconds: float
    rolling_avg_seconds: float | None  # None for laps with insufficient window


class DriverPaceSeries(BaseModel):
    driver_code: str
    team_id: str
    points: list[PacePoint]


class LongRunPace(BaseModel):
    series: list[DriverPaceSeries]
    window: int        # e.g., 5 — number of laps in rolling avg
    updated_at: float = 0.0
```

### Step 2: Router

```python
# backend/app/routers/long_run_pace.py
import re
from fastapi import APIRouter
from ..main import cache
from ..models.long_run_pace import LongRunPace, PacePoint, DriverPaceSeries
from ..models.lap_history import LapHistory

router = APIRouter()


def _parse_lap_time(s: str | None) -> float | None:
    if not s:
        return None
    m = re.match(r"^(?:(\d+):)?(\d+\.\d+)$", s.strip())
    if not m:
        return None
    minutes = int(m.group(1)) if m.group(1) else 0
    seconds = float(m.group(2))
    return minutes * 60 + seconds


@router.get("/long-run-pace", response_model=LongRunPace)
def get_long_run_pace(window: int = 5):
    raw = cache.get("lap_history")
    if not raw:
        return LongRunPace(series=[], window=window)
    lh = LapHistory(**raw)

    series: list[DriverPaceSeries] = []
    for tla, entries in lh.laps.items():
        pts: list[PacePoint] = []
        running: list[float] = []
        for e in entries:
            if e.in_pit:
                continue
            t = _parse_lap_time(e.lap_time)
            if t is None:
                continue
            running.append(t)
            avg = (sum(running[-window:]) / min(window, len(running))
                   if len(running) >= window else None)
            pts.append(PacePoint(lap=e.lap, lap_time_seconds=t, rolling_avg_seconds=avg))
        if pts:
            series.append(DriverPaceSeries(driver_code=tla, team_id="", points=pts))

    return LongRunPace(series=series, window=window, updated_at=lh.updated_at)
```

### Step 3: Test + register + commit

(Pattern matches Task 6's tests.)

```bash
git commit -m "feat: GET /long-run-pace rolling average per driver"
```

---

## Task 8: Live improvements ticker (polling endpoint, not SSE)

**Files:**
- Create: `backend/app/models/improvements.py`
- Create: `backend/app/routers/improvements.py`
- Test: `backend/tests/integration/test_improvements_router.py`

Returns the **most recent N events** where a driver improved a sector or set a new overall fastest. The frontend polls this every few seconds during live sessions (no SSE — keeps replay/live symmetry simple).

### Step 1: Model

```python
# backend/app/models/improvements.py
from pydantic import BaseModel
from typing import Literal


class ImprovementEvent(BaseModel):
    lap: int
    driver_code: str
    team_id: str
    kind: Literal["S1_FASTEST", "S2_FASTEST", "S3_FASTEST", "LAP_FASTEST"]
    time: str           # the time string ("48.663" or "1:46.123")
    delta_to_previous: float | None  # vs the prior holder of this title


class ImprovementsFeed(BaseModel):
    events: list[ImprovementEvent]   # newest first
    updated_at: float = 0.0
```

### Step 2: Router

```python
# backend/app/routers/improvements.py
from fastapi import APIRouter
from ..main import cache
from ..models.improvements import ImprovementsFeed, ImprovementEvent
from ..models.lap_history import LapHistory

router = APIRouter()


@router.get("/improvements", response_model=ImprovementsFeed)
def get_improvements(limit: int = 20):
    raw = cache.get("lap_history")
    if not raw:
        return ImprovementsFeed(events=[])
    lh = LapHistory(**raw)

    events: list[ImprovementEvent] = []
    # Build a flat list of (lap, tla, entry) sorted by lap so events appear in order
    flat: list[tuple[int, str, dict]] = []
    for tla, entries in lh.laps.items():
        for e in entries:
            flat.append((e.lap, tla, e))
    flat.sort(key=lambda x: x[0])

    for lap_no, tla, e in flat:
        if e.s1_overall_fastest and e.s1:
            events.append(ImprovementEvent(lap=lap_no, driver_code=tla, team_id="",
                                            kind="S1_FASTEST", time=e.s1,
                                            delta_to_previous=None))
        if e.s2_overall_fastest and e.s2:
            events.append(ImprovementEvent(lap=lap_no, driver_code=tla, team_id="",
                                            kind="S2_FASTEST", time=e.s2,
                                            delta_to_previous=None))
        if e.s3_overall_fastest and e.s3:
            events.append(ImprovementEvent(lap=lap_no, driver_code=tla, team_id="",
                                            kind="S3_FASTEST", time=e.s3,
                                            delta_to_previous=None))
        if e.is_overall_fastest:
            events.append(ImprovementEvent(lap=lap_no, driver_code=tla, team_id="",
                                            kind="LAP_FASTEST", time=e.lap_time,
                                            delta_to_previous=None))

    # Newest first; cap to `limit`
    events.reverse()
    return ImprovementsFeed(events=events[:limit], updated_at=lh.updated_at)
```

### Step 3: Test + register + commit

```bash
git commit -m "feat: GET /improvements live improvements ticker"
```

---

## Task 9: Tire strategy timeline endpoint

**Files:**
- Create: `backend/app/models/tire_strategy.py`
- Create: `backend/app/routers/tire_strategy.py`
- Test: `backend/tests/integration/test_tire_strategy_router.py`

Reads `cache["stints"]` and exposes per-driver stint history.

### Step 1: Model + router

```python
# backend/app/models/tire_strategy.py
from pydantic import BaseModel
from .stint import StintEntry


class TireStrategy(BaseModel):
    drivers: dict[str, list[StintEntry]]    # keyed by TLA
    updated_at: float = 0.0
```

```python
# backend/app/routers/tire_strategy.py
from fastapi import APIRouter
from ..main import cache
from ..models.tire_strategy import TireStrategy

router = APIRouter()


@router.get("/tire-strategy", response_model=TireStrategy)
def get_tire_strategy():
    raw = cache.get("stints")
    if not raw:
        return TireStrategy(drivers={}, updated_at=0.0)
    return TireStrategy(drivers=raw["stints"], updated_at=raw.get("updated_at", 0.0))
```

### Step 2: Test + register + commit

(Tests confirm a seeded `stints` cache is faithfully exposed.)

```bash
git commit -m "feat: GET /tire-strategy from cached stint history"
```

---

## Task 10: Tire usage this session endpoint

**Files:**
- Create: `backend/app/models/tire_usage.py`
- Create: `backend/app/routers/tire_usage.py`
- Test: `backend/tests/integration/test_tire_usage_router.py`

Per-driver count of laps run on each compound. Designed primarily for practice sessions but also informative during a race.

```python
# backend/app/models/tire_usage.py
from pydantic import BaseModel
from .timing import TireCompound


class TireUsage(BaseModel):
    counts: dict[str, dict[TireCompound, int]]  # {TLA: {compound: laps}}
    updated_at: float = 0.0
```

```python
# backend/app/routers/tire_usage.py
from collections import defaultdict
from fastapi import APIRouter
from ..main import cache
from ..models.stint import StintHistory
from ..models.tire_usage import TireUsage
from ..models.timing import TireCompound

router = APIRouter()


@router.get("/tire-usage", response_model=TireUsage)
def get_tire_usage():
    raw = cache.get("stints")
    if not raw:
        return TireUsage(counts={}, updated_at=0.0)
    sh = StintHistory(**raw)
    counts: dict[str, dict[TireCompound, int]] = defaultdict(lambda: defaultdict(int))
    for tla, stints in sh.stints.items():
        for s in stints:
            if s.compound:
                counts[tla][s.compound] += s.laps_completed
    return TireUsage(counts={tla: dict(c) for tla, c in counts.items()},
                     updated_at=sh.updated_at)
```

```bash
git commit -m "feat: GET /tire-usage compound counts per driver"
```

---

## Task 11: Pit window / undercut threat endpoint

**Files:**
- Create: `backend/app/models/undercut.py`
- Create: `backend/app/routers/undercut.py`
- Test: `backend/tests/integration/test_undercut_router.py`

Computes a simple undercut signal per pair of consecutive cars: gap is shrinking and the trailing car has fresher tyres. Returns a flat list of "threat" rows.

### Step 1: Model

```python
# backend/app/models/undercut.py
from pydantic import BaseModel


class UndercutThreat(BaseModel):
    target_driver: str           # lead car at risk
    threat_driver: str           # car behind threatening to undercut
    gap_seconds: float
    target_tyre_age: int
    threat_tyre_age: int
    pace_delta_per_lap: float    # threat's avg lap time minus target's, last 3 laps
    estimate_laps_to_pit_window: int | None  # heuristic; may be None


class UndercutFeed(BaseModel):
    threats: list[UndercutThreat]
    updated_at: float = 0.0
```

### Step 2: Router

```python
# backend/app/routers/undercut.py
import re
from fastapi import APIRouter
from ..main import cache
from ..models.lap_history import LapHistory
from ..models.stint import StintHistory
from ..models.undercut import UndercutFeed, UndercutThreat

router = APIRouter()


def _parse_lap_time(s: str | None) -> float | None:
    if not s:
        return None
    m = re.match(r"^(?:(\d+):)?(\d+\.\d+)$", s.strip())
    if not m:
        return None
    minutes = int(m.group(1)) if m.group(1) else 0
    return minutes * 60 + float(m.group(2))


@router.get("/undercut-threat", response_model=UndercutFeed)
def get_undercut():
    lh_raw = cache.get("lap_history")
    st_raw = cache.get("stints")
    if not lh_raw or not st_raw:
        return UndercutFeed(threats=[])
    lh = LapHistory(**lh_raw)
    sh = StintHistory(**st_raw)

    # Snapshot: last entry per driver
    snapshots: list[dict] = []
    for tla, entries in lh.laps.items():
        if not entries:
            continue
        last = entries[-1]
        if last.position is None:
            continue
        # Tyre age — last stint's tyre age = laps_completed of the last stint
        stint_age = 0
        if tla in sh.stints and sh.stints[tla]:
            stint_age = sh.stints[tla][-1].laps_completed
        # Pace = avg of last 3 lap_times excluding in-pit
        last_three = [_parse_lap_time(e.lap_time)
                      for e in entries[-3:] if not e.in_pit]
        last_three = [t for t in last_three if t is not None]
        pace = sum(last_three) / len(last_three) if last_three else None
        snapshots.append({
            "tla": tla, "position": last.position,
            "tyre_age": stint_age, "pace": pace,
        })

    snapshots.sort(key=lambda s: s["position"])
    threats: list[UndercutThreat] = []
    for i in range(1, len(snapshots)):
        target = snapshots[i - 1]
        threat = snapshots[i]
        if target["pace"] is None or threat["pace"] is None:
            continue
        # Threat must be on fresher tyres
        if threat["tyre_age"] >= target["tyre_age"]:
            continue
        delta = threat["pace"] - target["pace"]
        # Threat must be faster (negative delta)
        if delta >= 0:
            continue
        # We don't have IntervalToPositionAhead in lap_history; the heuristic
        # surfaces fresh-tyre + faster-pace pairings only. The frontend can
        # combine this with the live /timing payload for the gap.
        threats.append(UndercutThreat(
            target_driver=target["tla"],
            threat_driver=threat["tla"],
            gap_seconds=0.0,           # filled in by frontend from /timing
            target_tyre_age=target["tyre_age"],
            threat_tyre_age=threat["tyre_age"],
            pace_delta_per_lap=round(delta, 3),
            estimate_laps_to_pit_window=None,
        ))

    return UndercutFeed(threats=threats, updated_at=lh.updated_at)
```

### Step 3: Test + register + commit

```bash
git commit -m "feat: GET /undercut-threat fresh-tyre + faster-pace pairings"
```

---

## Task 12: Championship implications endpoint

**Files:**
- Create: `backend/app/models/championship.py`
- Create: `backend/app/routers/championship.py`
- Test: `backend/tests/integration/test_championship_router.py`

"If race ended now": project current `/timing` order against F1 points (25, 18, 15, 12, 10, 8, 6, 4, 2, 1 + 1 for fastest lap if in top 10) plus current standings in `data/standings.json`.

### Step 1: Model

```python
# backend/app/models/championship.py
from pydantic import BaseModel


class ProjectedDriver(BaseModel):
    driver_code: str
    current_points: float
    points_gained: int
    new_points: float
    new_position: int


class ProjectedConstructor(BaseModel):
    team_id: str
    team_name: str
    current_points: float
    points_gained: int
    new_points: float
    new_position: int


class ChampionshipImplications(BaseModel):
    drivers: list[ProjectedDriver]
    constructors: list[ProjectedConstructor]
    updated_at: float = 0.0
```

### Step 2: Router

```python
# backend/app/routers/championship.py
import json
import time
from collections import defaultdict
from pathlib import Path
from fastapi import APIRouter
from ..main import cache
from ..models.championship import (
    ChampionshipImplications, ProjectedDriver, ProjectedConstructor,
)

router = APIRouter()
_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "standings.json"
_RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def _load_standings() -> dict:
    return json.loads(_DATA_PATH.read_text())


@router.get("/championship-implications", response_model=ChampionshipImplications)
def get_championship_implications():
    timing = cache.get("timing")
    standings = _load_standings()
    if not timing:
        return ChampionshipImplications(drivers=[], constructors=[])
    entries = timing.get("entries", [])

    # Driver projections
    driver_pts = {d["driver_code"]: float(d["points"]) for d in standings["drivers"]}
    team_pts = {c["team_id"]: float(c["points"]) for c in standings["constructors"]}
    team_names = {c["team_id"]: c["team_name"] for c in standings["constructors"]}
    driver_team = {d["driver_code"]: d["team_id"] for d in standings["drivers"]}

    drivers: list[ProjectedDriver] = []
    team_gain: dict[str, int] = defaultdict(int)

    fastest_lap_driver = timing.get("fastest_lap_driver")
    for e in entries:
        pos = e.get("position")
        code = e.get("driver_code")
        if pos is None or code is None:
            continue
        gain = _RACE_POINTS[pos - 1] if 1 <= pos <= 10 else 0
        if pos <= 10 and code == fastest_lap_driver:
            gain += 1
        cur = driver_pts.get(code, 0.0)
        new_total = cur + gain
        drivers.append(ProjectedDriver(
            driver_code=code,
            current_points=cur,
            points_gained=gain,
            new_points=new_total,
            new_position=0,  # filled below
        ))
        team_id = driver_team.get(code)
        if team_id:
            team_gain[team_id] += gain

    drivers.sort(key=lambda d: d.new_points, reverse=True)
    for i, d in enumerate(drivers, start=1):
        d.new_position = i

    constructors: list[ProjectedConstructor] = []
    for team_id, gain in team_gain.items():
        cur = team_pts.get(team_id, 0.0)
        constructors.append(ProjectedConstructor(
            team_id=team_id,
            team_name=team_names.get(team_id, team_id),
            current_points=cur,
            points_gained=gain,
            new_points=cur + gain,
            new_position=0,
        ))
    constructors.sort(key=lambda c: c.new_points, reverse=True)
    for i, c in enumerate(constructors, start=1):
        c.new_position = i

    return ChampionshipImplications(drivers=drivers, constructors=constructors,
                                     updated_at=time.time())
```

### Step 3: Test

```python
# backend/tests/integration/test_championship_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_championship_empty_when_no_timing():
    cache.delete("timing")
    resp = client.get("/championship-implications")
    assert resp.status_code == 200
    assert resp.json()["drivers"] == []


def test_championship_projects_25_for_winner():
    cache.set("timing", {
        "entries": [
            {"position": 1, "driver_code": "VER", "team_id": "redbull",
             "last_lap": "1:46.0", "gap": "Leader", "interval": None,
             "tire": None, "tire_age": None,
             "is_fastest_overall": True, "is_personal_best": True,
             "is_in_battle": False, "is_retired": False, "dnf": False},
            {"position": 2, "driver_code": "NOR", "team_id": "mclaren",
             "last_lap": "1:46.5", "gap": "+0.5", "interval": "+0.5",
             "tire": None, "tire_age": None,
             "is_fastest_overall": False, "is_personal_best": True,
             "is_in_battle": False, "is_retired": False, "dnf": False},
        ],
        "fastest_lap_driver": "VER",
        "fastest_lap_time": "1:46.0",
        "updated_at": time.time(),
    }, ttl_seconds=60)
    resp = client.get("/championship-implications")
    drivers = {d["driver_code"]: d for d in resp.json()["drivers"]}
    # Winner with fastest lap = 25 + 1
    assert drivers["VER"]["points_gained"] == 26
    assert drivers["NOR"]["points_gained"] == 18
```

### Step 4: Register + commit

```bash
git commit -m "feat: GET /championship-implications live points projection"
```

---

## Task 13: Session notes endpoint

**Files:**
- Create: `backend/app/routers/session_notes.py`
- Test: `backend/tests/integration/test_session_notes_router.py`

A practice-session-friendly view of race control: filters out routine flag/track-clear noise and surfaces investigations, lap deletions, and incidents.

### Step 1: Router

```python
# backend/app/routers/session_notes.py
from fastapi import APIRouter
from ..main import cache
from ..models.race_control import RaceControlLog, RaceControlMessage, RaceControlCategory

router = APIRouter()

_INTERESTING_CATEGORIES = {
    RaceControlCategory.CAR_EVENT,    # investigations, deletions, incidents
    RaceControlCategory.FLAG,
    RaceControlCategory.SAFETY_CAR,
}
_NOISY_PREFIXES = ("GREEN LIGHT", "PIT EXIT", "DRS ENABLED", "DRS DISABLED")


@router.get("/session-notes", response_model=RaceControlLog)
def get_session_notes():
    raw = cache.get("race_control")
    if not raw:
        return RaceControlLog(entries=[], updated_at=0.0)
    log = RaceControlLog(**raw)
    filtered = [
        e for e in log.entries
        if e.category in _INTERESTING_CATEGORIES
        and not any(e.message.upper().startswith(p) for p in _NOISY_PREFIXES)
    ]
    return RaceControlLog(entries=filtered, updated_at=log.updated_at)
```

### Step 2: Test + register + commit

```bash
git commit -m "feat: GET /session-notes filtered race-control feed for practice sessions"
```

---

## Task 14: Fix /schedule (proper Meeting object parsing)

**Files:**
- Modify: `backend/app/services/schedule_service.py`

Replace the current "drop non-dict meetings" guard with actual parsing of livef1 `Meeting` objects.

### Step 1: Verify Meeting object structure

```bash
cd backend && python3 -c "
import livef1
season = livef1.get_season(2025)
m = season.meetings[0]
print('type:', type(m).__name__)
print('attrs:', [a for a in dir(m) if not a.startswith('_')])
print('vars:', vars(m).keys() if hasattr(m, '__dict__') else 'no __dict__')
sessions = getattr(m, 'sessions', None)
print('sessions type:', type(sessions).__name__, 'len:', len(sessions) if sessions else 0)
if sessions:
    s = sessions[0]
    print('session type:', type(s).__name__)
    print('session attrs:', [a for a in dir(s) if not a.startswith('_')])
"
```

Update `backend/docs/livef1-api.md` with the verified attribute names.

### Step 2: Implement Meeting → dict conversion

```python
# In load_season, replace the "drop non-dict" branch with conversion:
def _meeting_to_dict(m) -> dict:
    if isinstance(m, dict):
        return m
    sessions = getattr(m, "sessions", None) or []
    return {
        "round": getattr(m, "round", None) or getattr(m, "Round", 0),
        "season": getattr(m, "season", None) or getattr(m, "Year", _current_season()),
        "Country": getattr(m, "country", None) or getattr(m, "Country", ""),
        "Location": getattr(m, "location", None) or getattr(m, "Location", ""),
        "circuit_short_name": getattr(m, "circuit_short_name", None),
        "sessions": [_session_to_dict(s) for s in sessions],
    }


def _session_to_dict(s) -> dict:
    if isinstance(s, dict):
        return s
    return {
        "Name": getattr(s, "name", None) or getattr(s, "Name", ""),
        "session_type": getattr(s, "session_type", None) or getattr(s, "Name", ""),
        "StartDate": getattr(s, "start_date", None) or getattr(s, "StartDate", ""),
    }
```

Replace `meetings = list(raw)` with:

```python
meetings = [_meeting_to_dict(m) for m in raw]
```

Remove the "drop non-dict" guard (no longer needed).

### Step 3: Add an integration test

```python
# backend/tests/integration/test_schedule_router_real.py
"""Real network test — runs against live livef1.get_season."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

pytestmark = pytest.mark.skip(reason="network — opt in with -k 'real_schedule'")
client = TestClient(app)


def test_schedule_returns_real_weekend_real_schedule():
    resp = client.get("/schedule")
    # Either 200 with valid weekend or 503 if season has no upcoming meetings
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "circuit" in data
        assert isinstance(data["sessions"], list)
```

### Step 4: Run tests + commit

```bash
git add backend/app/services/schedule_service.py \
        backend/docs/livef1-api.md \
        backend/tests/integration/test_schedule_router_real.py
git commit -m "fix: parse livef1 Meeting objects into schedule dicts"
```

---

## Task 15: Live poller integration with RealF1Client

**Files:**
- Modify: `backend/app/workers/live_poller.py`
- Test: `backend/tests/unit/test_live_poller_realtime.py`

The skeleton's `_get_live_session()` returns `None` outside replay mode because livef1 has no `get_live_session()` helper. RealF1Client is the canonical live data path and is async-callback-based, which conflicts with the polling pattern. This task replaces the polling architecture *for live mode* with a streaming architecture: the poller subscribes to RealF1Client topics and writes to the cache as messages arrive, while continuing to expose the same cache keys the routers already read.

**Architectural change:** in live mode, `LivePoller.run()` no longer ticks on an interval. It opens a RealF1Client connection, subscribes to topics, and accumulates rows in memory. A separate periodic task (every `POLL_INTERVAL_SECONDS`) parses the accumulated rows into models and writes the caches.

### Step 1: Verify RealF1Client API

```bash
cd backend && python3 -c "
from livef1.adapters.realtime_client import RealF1Client
c = RealF1Client(topics=['TimingData', 'DriverList'])
print('attrs:', [a for a in dir(c) if not a.startswith('_')])
"
```

Document findings in `backend/docs/livef1-api.md`. Look for: `connect`, `disconnect`, message-handler registration mechanism, and how to extract data rows from incoming messages.

### Step 2: Implement the dual-task poller

```python
# backend/app/workers/live_poller.py — outline; flesh out per RealF1Client API
import asyncio
import logging
import time
from typing import Any

from ..cache.file_cache import CacheBackend
from ..state_machine.machine import StateMachine
from ..models.session import SessionState
from ..services import livef1_client
from ..services.lap_history import build_lap_history
from ..services.stint_aggregator import build_stint_history
from ..services.livef1_client import DriverResolver

logger = logging.getLogger(__name__)

_PARSE_INTERVAL = 3   # seconds — how often we flatten accumulated rows to caches


class LivePoller:
    def __init__(self, cache: CacheBackend, state_machine: StateMachine):
        self._cache = cache
        self._sm = state_machine
        self._timing_rows: list[dict] = []
        self._position_rows: list[dict] = []
        self._rc_rows: list[dict] = []
        self._driver_list_rows: list[dict] = []
        self._resolver: DriverResolver | None = None
        self._seen_rc_utcs: set[str] = set()
        self._client_task: asyncio.Task | None = None

    async def run(self) -> None:
        """Top-level: start RealF1Client + parse loop concurrently."""
        try:
            self._client_task = asyncio.create_task(self._stream())
            while True:
                try:
                    await self._parse_and_cache()
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.error(f"Parse error: {e}")
                await asyncio.sleep(_PARSE_INTERVAL)
        finally:
            if self._client_task:
                self._client_task.cancel()

    async def _stream(self) -> None:
        """Connect to RealF1Client and accumulate raw messages.

        Implementation note: RealF1Client's exact handler-registration API
        was verified in step 1. Follow that pattern. On message receipt,
        normalize to dict rows matching the TimingData fixture shape and
        append to the appropriate _XXX_rows list.
        """
        ...  # actual RealF1Client wiring goes here

    async def _parse_and_cache(self) -> None:
        if self._sm.state in (SessionState.IDLE, SessionState.ENDED):
            return
        if not self._resolver and self._driver_list_rows:
            self._resolver = DriverResolver.from_rows(self._driver_list_rows)

        # Timing tower
        if self._timing_rows:
            tower = livef1_client.parse_timing_snapshot(
                self._timing_rows, resolver=self._resolver,
            )
            self._cache.set("timing", tower.model_dump(mode="json"), ttl_seconds=30)
            self._sm.on_timing_data()

            # Lap history aggregator
            lh = build_lap_history(self._timing_rows, resolver=self._resolver)
            self._cache.set("lap_history", lh.model_dump(mode="json"), ttl_seconds=3600)

        # Positions
        if self._position_rows:
            pos = livef1_client.parse_position_snapshot(
                self._position_rows, resolver=self._resolver,
            )
            self._cache.set("positions", pos.model_dump(mode="json"), ttl_seconds=30)

        # Race control — diff and feed state machine
        if self._rc_rows:
            entries = livef1_client.parse_race_control_rows(self._rc_rows)
            for entry in entries:
                if entry["utc"] in self._seen_rc_utcs:
                    continue
                self._seen_rc_utcs.add(entry["utc"])
                self._sm.on_race_control_message(entry["message"])
            self._cache.set("race_control",
                            {"entries": entries, "updated_at": time.time()},
                            ttl_seconds=60)
```

### Step 3: Tests

```python
# backend/tests/unit/test_live_poller_realtime.py
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.workers.live_poller import LivePoller
from app.cache.file_cache import FileCache
from app.state_machine.machine import StateMachine


@pytest.fixture
def mock_cache(tmp_path):
    return FileCache(tmp_path / "cache")


@pytest.mark.asyncio
async def test_parse_and_cache_writes_lap_history(mock_cache):
    sm = StateMachine()
    poller = LivePoller(cache=mock_cache, state_machine=sm)
    sm.on_timing_data()  # → LIVE
    poller._timing_rows = [
        {"DriverNo": "1", "RacingNumber": "1", "NumberOfLaps": 1.0,
         "LastLapTime_Value": "1:46.000", "Position": "1"},
    ]
    poller._driver_list_rows = [
        {"RacingNumber": "1", "Tla": "VER", "TeamName": "Red Bull Racing"},
    ]
    await poller._parse_and_cache()
    assert mock_cache.get("timing") is not None
    assert mock_cache.get("lap_history") is not None
```

(Full RealF1Client streaming logic is harder to unit-test — leave that to manual smoke testing during a real session.)

### Step 4: Manual smoke test

Document this in `backend/docs/live-mode-smoke-test.md`:

```
1. Pick an active F1 session (FP1/FP2/FP3/Q/Sprint/Race).
2. Without REPLAY_SESSION set, run `uvicorn app.main:app --port 8000`.
3. Watch logs for "RealF1Client connected" within 10s.
4. Curl /timing every ~5s; confirm entries grow as the session progresses.
5. Curl /lap-history (if exposed) or query the cache file directly to confirm
   per-driver lap entries accumulate.
```

### Step 5: Commit

```bash
git add backend/app/workers/live_poller.py \
        backend/tests/unit/test_live_poller_realtime.py \
        backend/docs/live-mode-smoke-test.md
git commit -m "feat: live poller with RealF1Client streaming + periodic parse-and-cache"
```

---

## Self-Review

### Spec coverage check

| Deferred module from skeleton plan | Covered by |
|---|---|
| Sector dominance | Task 5 |
| Live improvements ticker | Task 8 |
| Long run pace | Task 7 |
| Gap-to-leader chart | Task 6 |
| Tire strategy timeline | Task 9 |
| Tire usage this session | Task 10 |
| Pit window / undercut threat | Task 11 |
| Championship implications | Task 12 |
| Session notes | Task 13 |

### Wiring verification checklist

Before considering this phase complete, confirm each path is exercised by a test:

- [ ] Lap history aggregator produces ≥40 laps for race winner
- [ ] Replay seek populates `lap_history` and `stints` caches
- [ ] Replay seek cap on FastF1 laps matches `current_lap`
- [ ] Sector dominance returns 3 cards even with empty cache
- [ ] Gap chart filters by `top` query parameter
- [ ] Long-run pace's rolling-avg window is honored (`window=5` default)
- [ ] Improvements feed is newest-first
- [ ] Tire strategy / tire usage are read-only views over the same `stints` cache
- [ ] Undercut feed requires both `lap_history` and `stints`
- [ ] Championship implications reads `data/standings.json`, not hardcoded values
- [ ] Session notes filters out `GREEN LIGHT` and `DRS ENABLED` noise
- [ ] `/schedule` returns 200 against live livef1 (Task 14)
- [ ] Live poller `_parse_and_cache` writes both `timing` and `lap_history`

### Implementation order recommendations

These tasks have dependencies; implement in roughly this order:

1. Task 1 (FastF1) → Task 2 (lap history) → Task 3 (stints) — foundational
2. Task 4 (replay manager wiring) — enables manual testing of all subsequent tasks
3. Tasks 5–13 — independent endpoints (any order)
4. Task 14 (`/schedule` fix) — independent of all the above
5. Task 15 (live poller) — last because it's the highest-risk and only verifiable during a live session

### Known limitations

1. **Tire data depends on FastF1**, which depends on the F1 livetiming archive. For a live session, FastF1's lap data won't be available until after the session — meaning tire strategy / tire usage / undercut endpoints will be empty during a live race. The live poller (Task 15) cannot fill this gap; it would require a parallel TimingAppData fix in livef1 or scraping a third-party tire feed.

2. **`Sectors_3_Value` is never populated** in the Spa fixture. If a future circuit's data uses 4 sectors, the lap-history aggregator must be extended.

3. **Pit window / undercut heuristic is intentionally simple** — fresh-tyre + faster-pace pairings only. The frontend gets the gap from `/timing` and combines.

4. **Championship implications use a static points table.** If F1 changes the points system mid-season (e.g., adds sprint points), `_RACE_POINTS` must be updated and a sprint-points table added.

### Type consistency

- All new model fields use Pydantic v2 with `mode="json"` serialization for cache writes.
- TireCompound is reused from `app.models.timing` — do not redefine.
- Lap times are always strings on the wire (`"1:48.564"`); seconds-as-float only in routers that compute deltas.
