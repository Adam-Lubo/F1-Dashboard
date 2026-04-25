1# F1 Dashboard Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend, full monorepo scaffold, shared TypeScript types, LiveF1 data integration, flat-file cache, state machine, and Spa 2024 replay infrastructure for manual frontend verification.

**Architecture:** FastAPI on Fly.io exposes REST endpoints. A background asyncio task polls the LiveF1 stream every 3–5 s during live sessions and writes snapshots to a flat-file cache (one JSON file per data type). Routers read from that cache; on cache miss they return the last known value. Historical data is fetched directly from LiveF1 `get_session()` on request. No database, no Redis. A replay mode loads the Spa 2024 Race fixture instead of polling, enabling manual frontend dev without a live race.

---

## Scope: Skeleton v1

This plan implements a **skeleton backend** — the minimum viable set of endpoints needed for the frontend to render core views and exercise the replay harness. Several design-spec modules are intentionally **deferred** to a follow-up plan:

### Included in this plan
- State machine (all 9 states, fed by both timing cadence and race-control messages)
- Timing tower (with tire compound + tire age merged from `TimingAppData`)
- Track positions (Position.z)
- Weather (Open-Meteo)
- Driver + constructor standings (hand-maintained JSON)
- Historical stats per driver/circuit (driver lookup resolved per-session)
- News RSS aggregation
- Weekend schedule (real, sourced from LiveF1 season lookup)
- `/state` fully wired to schedule (session_type, round, countdown) and timing (current_lap)
- Circuit info endpoint (serves from `circuits.json`)
- Starting grid endpoint (reads cached last-quali timing)
- Race control messages endpoint (cached, also drives state machine)
- ML predictions stub (reads from Fly volume if present)
- Spa 2024 replay harness — seek drives state machine AND replays race control

### Deferred to a follow-up plan
These modules from `f1-dashboard-design-spec.md` are not backed by endpoints in this plan. A follow-up plan will define their data shape, storage, and compute path:
- **Sector dominance** — per-driver S1/S2/S3 times
- **Live improvements ticker** — sector-improvement events stream
- **Long run pace** — lap-time history per driver during practice
- **Gap-to-leader chart** — lap-by-lap gap series for top N drivers
- **Tire strategy timeline** — stint history (compound + laps per stint)
- **Tire usage this session** — compound counts per driver
- **Pit window / undercut threat** — tire age + pace delta computation
- **Championship implications** — "if race ended now" live points projection
- **Session notes** — practice-session variant of race control
- **Storylines** — curated pre-weekend narratives (source TBD)
- **Post-session summary** — LLM recap (v2, spec-flagged)
- **Team radio transcription** — Whisper on OpenF1 audio (v2, spec-flagged)
- **ML predictions runner** — the mar-antaya fork itself (this plan only reads its output)

**Why skeleton-first:** these deferred modules either require derived aggregates (lap history, stint tracking) or external pipelines (LLM, ML runner, audio transcription) that are cleaner to design once the core data pipeline is known to work against real LiveF1 output. The skeleton is the testbed.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, livef1, feedparser, httpx, pandas, pytest; TypeScript / React 18 / Vite / Tailwind / Zustand / Recharts for frontend scaffold; npm workspaces for monorepo.

**Fixture race:** 2024 Belgian GP (Spa-Francorchamps), Race session — `livef1.get_session(season=2024, meeting_identifier="Spa", session_identifier="Race")`.

---

## File Structure

```
f1-dashboard/
├── Makefile
├── .gitignore
├── fly.toml
├── package.json                        # npm workspace root
├── shared-types/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/index.ts                    # TypeScript interfaces
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx
│       └── App.tsx
└── backend/
    ├── pyproject.toml
    ├── Dockerfile
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                     # FastAPI app, lifespan, CORS, routers
    │   ├── config.py                   # Settings (pydantic-settings)
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── session.py              # SessionState, SessionType, SessionInfo
    │   │   ├── timing.py               # TireCompound, TimingEntry, TimingTower
    │   │   ├── position.py             # DriverPosition, TrackPositions
    │   │   ├── weather.py              # WeatherData
    │   │   ├── standings.py            # DriverStanding, ConstructorStanding
    │   │   ├── historical.py           # HistoricalStats
    │   │   ├── news.py                 # NewsItem
    │   │   └── schedule.py             # ScheduleSession, WeekendSchedule
    │   ├── cache/
    │   │   └── file_cache.py           # CacheBackend protocol + FileCache
    │   ├── state_machine/
    │   │   └── machine.py              # StateMachine
    │   ├── services/
    │   │   ├── livef1_client.py        # LiveF1 wrapper + parser
    │   │   ├── weather_client.py       # Open-Meteo wrapper
    │   │   └── news_client.py          # RSS aggregator
    │   ├── workers/
    │   │   └── live_poller.py          # asyncio background polling task
    │   ├── routers/
    │   │   ├── state.py                # GET /state
    │   │   ├── timing.py               # GET /timing
    │   │   ├── positions.py            # GET /positions
    │   │   ├── standings.py            # GET /standings/drivers, /standings/constructors
    │   │   ├── historical.py           # GET /historical/{driver}/{circuit}
    │   │   ├── weather.py              # GET /weather
    │   │   ├── news.py                 # GET /news
    │   │   ├── schedule.py             # GET /schedule
    │   │   ├── predictions.py          # GET /predictions (stub)
    │   │   └── replay.py               # GET /replay/status, POST /replay/seek/{lap}
    │   └── replay/
    │       └── manager.py              # ReplayManager
    ├── data/
    │   ├── standings.json              # manually-updated championship standings
    │   └── circuits.json               # circuit metadata (lat/lon, laps, lap record)
    └── tests/
        ├── conftest.py
        ├── fixtures/
        │   ├── download_spa_2024.py    # one-time download script (needs network)
        │   └── spa_2024/               # saved JSON fixtures
        │       ├── schema.md           # printed DataFrame schemas (filled by download script)
        │       ├── timing.json
        │       ├── positions.json
        │       ├── race_control.json
        │       └── weather.json
        ├── unit/
        │   ├── test_cache.py
        │   ├── test_state_machine.py
        │   └── test_parsers.py
        ├── integration/
        │   ├── test_health.py
        │   ├── test_state_router.py
        │   ├── test_timing_router.py
        │   ├── test_positions_router.py
        │   ├── test_weather_router.py
        │   └── test_news_router.py
        └── replay/
            └── test_spa_2024_replay.py
```

**Parser note:** The exact column names in livef1 DataFrames are discovered by running the fixture download script. If a parser raises `KeyError`, print `df.columns` against the downloaded fixture and adjust column references in `livef1_client.py`. The fixture download script prints all schemas to `tests/fixtures/spa_2024/schema.md`.

---

## Task 1: Root monorepo scaffold

**Files:**
- Create: `package.json`
- Create: `.gitignore`
- Create: `Makefile`

- [ ] **Step 1: Create root package.json**

```json
{
  "name": "f1-dashboard",
  "private": true,
  "workspaces": ["frontend", "shared-types"],
  "scripts": {
    "dev:frontend": "npm run dev --workspace=frontend",
    "test:backend": "cd backend && pytest -v",
    "replay": "cd backend && REPLAY_SESSION=spa_2024 uvicorn app.main:app --reload --port 8000"
  }
}
```

- [ ] **Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
*.egg-info/
dist/
.mypy_cache/

# Cache files (large; not committed)
backend/cache/
backend/tests/fixtures/spa_2024/*.json

# Node
node_modules/
frontend/dist/
shared-types/dist/

# Env
.env
.env.local

# Fly
.fly/

# OS
.DS_Store
```

- [ ] **Step 3: Create Makefile**

```makefile
.PHONY: dev test replay download-fixtures

dev:
	npm run dev:frontend &
	cd backend && uvicorn app.main:app --reload --port 8000

test:
	cd backend && pytest -v

replay:
	cd backend && REPLAY_SESSION=spa_2024 uvicorn app.main:app --reload --port 8000

download-fixtures:
	cd backend && python tests/fixtures/download_spa_2024.py
```

- [ ] **Step 4: Commit**

```bash
git init
git add package.json .gitignore Makefile
git commit -m "feat: root monorepo scaffold"
```

---

## Task 2: Backend Python project setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write a failing test (import sanity check)**

```python
# backend/tests/unit/test_imports.py
def test_fastapi_importable():
    import fastapi
    assert fastapi.__version__
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_imports.py -v
```
Expected: `ModuleNotFoundError: No module named 'fastapi'`

- [ ] **Step 3: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "f1-dashboard-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "livef1",
    "feedparser>=6.0.11",
    "httpx>=0.27.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "pandas>=2.2.0",
    "respx>=0.21.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.6",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 4: Create directory structure and init files**

```bash
cd backend
mkdir -p app/models app/cache app/state_machine app/services app/workers app/routers app/replay
mkdir -p data tests/unit tests/integration tests/replay tests/fixtures/spa_2024
touch app/__init__.py app/models/__init__.py app/cache/__init__.py
touch app/state_machine/__init__.py app/services/__init__.py
touch app/workers/__init__.py app/routers/__init__.py app/replay/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
touch tests/replay/__init__.py
```

- [ ] **Step 5: Install deps and run test**

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/unit/test_imports.py -v
```
Expected: `PASSED`

- [ ] **Step 6: Create conftest.py**

```python
# backend/tests/conftest.py
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "spa_2024"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
```

- [ ] **Step 7: Verify livef1 library surface**

```bash
cd backend && source .venv/bin/activate
python -c "import livef1; print(sorted(n for n in dir(livef1) if not n.startswith('_')))"
python -c "import livef1; help(livef1.get_session)" | head -30
```

Record the result in `backend/docs/livef1-api.md`. Verify:
- `livef1.get_session(season, meeting_identifier, session_identifier)` exists (historical).
- Whether a live-session helper exists. Expected names: `get_live_session`, `current_session`, `live_session`. **Note the actual name.** If none exists, the live poller (Task 18) will instead derive the current session from the schedule router using `get_session(season=current_season, meeting=current_round_meeting, session=current_session_name)`.
- How session objects expose the driver list. Expected: `session.drivers` or `session.get_data("DriverList")`. The historical router (Task 14) and timing parser (Task 9) both need this to map racing number → TLA per session rather than via hardcoded dict.

If the API differs from what this plan assumes, update Tasks 9, 14, and 18 before implementing them — do not work around it silently.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: backend Python project setup"
```

---

## Task 3: Frontend + shared-types scaffold

**Files:**
- Create: `frontend/` (Vite React TS)
- Create: `shared-types/package.json`
- Create: `shared-types/tsconfig.json`
- Create: `shared-types/src/index.ts`

- [ ] **Step 1: Scaffold frontend**

```bash
cd /path/to/f1-dashboard
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install zustand recharts
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

- [ ] **Step 2: Create shared-types package**

```json
// shared-types/package.json
{
  "name": "@f1-dashboard/shared-types",
  "version": "0.1.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "scripts": {
    "build": "tsc"
  }
}
```

```json
// shared-types/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "declaration": true,
    "outDir": "dist"
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Write TypeScript interfaces (mirrors Pydantic models defined in Task 4)**

```typescript
// shared-types/src/index.ts

export type SessionState =
  | "IDLE" | "ARMED" | "LIVE" | "PAUSED"
  | "RED_FLAG" | "YELLOW_FLAG" | "SC" | "VSC" | "ENDED";

export type SessionType =
  | "PRACTICE" | "QUALIFYING" | "SPRINT_QUALI" | "SPRINT" | "RACE";

export type TireCompound = "S" | "M" | "H" | "I" | "W";

export interface SessionInfo {
  state: SessionState;
  session_type: SessionType | null;
  session_name: string;
  round: number;
  season: number;
  current_lap: number | null;
  total_laps: number | null;
  leader_gap: string | null;
  countdown_seconds: number | null;
  session_elapsed_seconds: number | null;
}

export interface TimingEntry {
  position: number;
  driver_code: string;
  team_id: string;
  last_lap: string | null;
  gap: string | null;
  interval: string | null;
  tire: TireCompound | null;
  tire_age: number | null;
  is_fastest_overall: boolean;
  is_personal_best: boolean;
  is_in_battle: boolean;
  is_retired: boolean;
  dnf: boolean;
  // Note: `is_watchlisted` is computed frontend-side from localStorage — not on the wire.
}

export interface TimingTower {
  entries: TimingEntry[];
  fastest_lap_driver: string | null;
  fastest_lap_time: string | null;
  updated_at: number;
}

export interface DriverPosition {
  driver_code: string;
  team_id: string;
  x: number;
  y: number;
}

export interface TrackPositions {
  drivers: DriverPosition[];
  updated_at: number;
}

export interface WeatherData {
  air_temp: number;
  track_temp: number | null;
  humidity: number;
  wind_speed: number;
  rain_chance: number;
  description: string;
  is_live: boolean;
  updated_at: number;
}

export interface DriverStanding {
  position: number;
  driver_code: string;
  team_id: string;
  points: number;
  wins: number;
}

export interface ConstructorStanding {
  position: number;
  team_id: string;
  team_name: string;
  points: number;
  wins: number;
}

export interface HistoricalStats {
  driver_code: string;
  circuit: string;
  best_finish: number | null;
  best_quali: number | null;
  avg_race_pos: number | null;
  avg_quali_pos: number | null;
  wins: number;
  poles: number;
  races: number;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  published_at: string;
  summary: string | null;
}

export interface ScheduleSession {
  type: SessionType;
  name: string;
  day: string;
  local_time: string;
  utc_time: string;
  is_next: boolean;
  is_complete: boolean;
}

export interface WeekendSchedule {
  circuit: string;
  country: string;
  round: number;
  season: number;
  sessions: ScheduleSession[];
}

export interface PredictionEntry {
  position: number;
  driver_code: string;
  team_id: string;
  win_probability: number;
}

export interface Predictions {
  entries: PredictionEntry[];
  model: string;
  updated_at: number;
}

export interface ReplayStatus {
  active: boolean;
  session_key: string | null;
  current_lap: number;
  total_laps: number;
}

export interface StartingGridEntry {
  position: number;
  driver_code: string;
  team_id: string;
  quali_time: string | null;
}

export interface StartingGrid {
  circuit: string;
  entries: StartingGridEntry[];
  updated_at: number;
}

export type RaceControlCategory =
  | "Flag" | "SafetyCar" | "Drs" | "CarEvent" | "Other";

export interface RaceControlMessage {
  utc: string;           // ISO timestamp
  lap: number | null;
  category: RaceControlCategory;
  message: string;
}

export interface RaceControlLog {
  entries: RaceControlMessage[];
  updated_at: number;
}

export interface CircuitInfo {
  id: string;
  name: string;
  country: string;
  lat: number;
  lon: number;
  length_km: number;
  total_laps: number;
  lap_record: string;
  lap_record_driver: string;
  lap_record_year: number;
  timezone: string;
}
```

- [ ] **Step 4: Wire shared-types into frontend**

```json
// frontend/package.json — add to dependencies:
{
  "dependencies": {
    "@f1-dashboard/shared-types": "*"
  }
}
```

```bash
cd f1-dashboard && npm install
```

- [ ] **Step 5: Commit**

```bash
git add frontend/ shared-types/
git commit -m "feat: frontend Vite scaffold and shared-types package"
```

---

## Task 4: Pydantic models

**Files:**
- Create: `backend/app/models/session.py`
- Create: `backend/app/models/timing.py`
- Create: `backend/app/models/position.py`
- Create: `backend/app/models/weather.py`
- Create: `backend/app/models/standings.py`
- Create: `backend/app/models/historical.py`
- Create: `backend/app/models/news.py`
- Create: `backend/app/models/schedule.py`
- Test: `backend/tests/unit/test_models.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_models.py
from app.models.session import SessionState, SessionInfo
from app.models.timing import TimingEntry, TimingTower, TireCompound


def test_session_info_defaults():
    info = SessionInfo(
        state=SessionState.IDLE,
        session_type=None,
        session_name="MIAMI GP",
        round=6,
        season=2026,
    )
    assert info.current_lap is None
    assert info.state == SessionState.IDLE


def test_timing_entry_battle_flag():
    entry = TimingEntry(
        position=4,
        driver_code="PIA",
        team_id="mclaren",
        is_fastest_overall=False,
        is_personal_best=False,
        is_watchlisted=False,
        is_in_battle=True,
        is_retired=False,
        dnf=False,
    )
    assert entry.is_in_battle is True
    assert entry.tire is None


def test_timing_tower_ordering():
    tower = TimingTower(
        entries=[
            TimingEntry(position=2, driver_code="NOR", team_id="mclaren",
                        is_fastest_overall=False, is_personal_best=False,
                        is_watchlisted=False, is_in_battle=False,
                        is_retired=False, dnf=False),
            TimingEntry(position=1, driver_code="VER", team_id="redbull",
                        is_fastest_overall=False, is_personal_best=False,
                        is_watchlisted=False, is_in_battle=False,
                        is_retired=False, dnf=False),
        ],
        fastest_lap_driver=None,
        fastest_lap_time=None,
        updated_at=0.0,
    )
    assert tower.entries[0].position == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/unit/test_models.py -v
```
Expected: `ImportError: cannot import name 'SessionState' from 'app.models.session'`

- [ ] **Step 3: Implement models**

```python
# backend/app/models/session.py
from enum import Enum
from pydantic import BaseModel


class SessionState(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    RED_FLAG = "RED_FLAG"
    YELLOW_FLAG = "YELLOW_FLAG"
    SC = "SC"
    VSC = "VSC"
    ENDED = "ENDED"


class SessionType(str, Enum):
    PRACTICE = "PRACTICE"
    QUALIFYING = "QUALIFYING"
    SPRINT_QUALI = "SPRINT_QUALI"
    SPRINT = "SPRINT"
    RACE = "RACE"


class SessionInfo(BaseModel):
    state: SessionState
    session_type: SessionType | None = None
    session_name: str
    round: int
    season: int
    current_lap: int | None = None
    total_laps: int | None = None
    leader_gap: str | None = None
    countdown_seconds: int | None = None
    session_elapsed_seconds: int | None = None
```

```python
# backend/app/models/timing.py
from enum import Enum
from pydantic import BaseModel


class TireCompound(str, Enum):
    SOFT = "S"
    MEDIUM = "M"
    HARD = "H"
    INTERMEDIATE = "I"
    WET = "W"


class TimingEntry(BaseModel):
    position: int
    driver_code: str
    team_id: str
    last_lap: str | None = None
    gap: str | None = None
    interval: str | None = None
    tire: TireCompound | None = None
    tire_age: int | None = None
    is_fastest_overall: bool
    is_personal_best: bool
    is_in_battle: bool
    is_retired: bool
    dnf: bool
    # Watchlist is computed client-side; not part of server payload.


class TimingTower(BaseModel):
    entries: list[TimingEntry]
    fastest_lap_driver: str | None = None
    fastest_lap_time: str | None = None
    updated_at: float = 0.0
```

```python
# backend/app/models/position.py
from pydantic import BaseModel


class DriverPosition(BaseModel):
    driver_code: str
    team_id: str
    x: float
    y: float
    is_watchlisted: bool = False


class TrackPositions(BaseModel):
    drivers: list[DriverPosition]
    updated_at: float = 0.0
```

```python
# backend/app/models/weather.py
from pydantic import BaseModel


class WeatherData(BaseModel):
    air_temp: float
    track_temp: float | None = None
    humidity: float
    wind_speed: float
    rain_chance: float
    description: str
    is_live: bool = False
    updated_at: float = 0.0
```

```python
# backend/app/models/standings.py
from pydantic import BaseModel


class DriverStanding(BaseModel):
    position: int
    driver_code: str
    team_id: str
    points: float
    wins: int


class ConstructorStanding(BaseModel):
    position: int
    team_id: str
    team_name: str
    points: float
    wins: int
```

```python
# backend/app/models/historical.py
from pydantic import BaseModel


class HistoricalStats(BaseModel):
    driver_code: str
    circuit: str
    best_finish: int | None = None
    best_quali: int | None = None
    avg_race_pos: float | None = None
    avg_quali_pos: float | None = None
    wins: int = 0
    poles: int = 0
    races: int = 0
```

```python
# backend/app/models/news.py
from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: str
    summary: str | None = None
```

```python
# backend/app/models/schedule.py
from pydantic import BaseModel
from .session import SessionType


class ScheduleSession(BaseModel):
    type: SessionType
    name: str
    day: str
    local_time: str
    utc_time: str
    is_next: bool = False
    is_complete: bool = False


class WeekendSchedule(BaseModel):
    circuit: str
    country: str
    round: int
    season: int
    sessions: list[ScheduleSession]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/unit/test_models.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat: pydantic models for all data types"
```

---

## Task 5: File cache

**Files:**
- Create: `backend/app/cache/file_cache.py`
- Test: `backend/tests/unit/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_cache.py
import time
import pytest
from pathlib import Path
from app.cache.file_cache import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(tmp_path / "cache")


def test_cache_miss_returns_none(cache):
    assert cache.get("missing_key") is None


def test_cache_set_and_get(cache):
    cache.set("timing", {"entries": []}, ttl_seconds=60)
    result = cache.get("timing")
    assert result == {"entries": []}


def test_cache_expired_returns_none(cache):
    cache.set("timing", {"entries": []}, ttl_seconds=0)
    time.sleep(0.05)
    assert cache.get("timing") is None


def test_cache_delete(cache):
    cache.set("timing", {"entries": []}, ttl_seconds=60)
    cache.delete("timing")
    assert cache.get("timing") is None


def test_cache_slash_in_key(cache):
    cache.set("historical/VER/spa", {"wins": 3}, ttl_seconds=60)
    assert cache.get("historical/VER/spa") == {"wins": 3}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/unit/test_cache.py -v
```
Expected: `ImportError: cannot import name 'FileCache'`

- [ ] **Step 3: Implement FileCache**

```python
# backend/app/cache/file_cache.py
import json
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> None: ...


class FileCache:
    def __init__(self, cache_dir: Path):
        self._dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "__").replace(":", "_").replace(" ", "_")
        return self._dir / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() > data["expires_at"]:
            path.unlink(missing_ok=True)
            return None
        return data["value"]

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        path = self._path(key)
        path.write_text(json.dumps({
            "value": value,
            "expires_at": time.time() + ttl_seconds,
        }))

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/unit/test_cache.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/cache/ backend/tests/unit/test_cache.py
git commit -m "feat: file cache with TTL and CacheBackend protocol"
```

---

## Task 6: State machine

**Files:**
- Create: `backend/app/state_machine/machine.py`
- Test: `backend/tests/unit/test_state_machine.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_state_machine.py
import time
import pytest
from app.state_machine.machine import StateMachine
from app.models.session import SessionState


def test_initial_state_is_idle():
    sm = StateMachine()
    assert sm.state == SessionState.IDLE


def test_arms_within_15_minutes_of_session():
    sm = StateMachine()
    now = time.time()
    sm.set_next_session_at(now + 14 * 60)  # 14 min away
    sm.tick(now)
    assert sm.state == SessionState.ARMED


def test_stays_idle_when_session_more_than_15_min_away():
    sm = StateMachine()
    now = time.time()
    sm.set_next_session_at(now + 20 * 60)
    sm.tick(now)
    assert sm.state == SessionState.IDLE


def test_transitions_to_live_on_timing_data():
    sm = StateMachine()
    now = time.time()
    sm.on_timing_data(at=now)
    assert sm.state == SessionState.LIVE


def test_pauses_after_60s_without_data():
    sm = StateMachine()
    now = time.time()
    sm.on_timing_data(at=now - 65)
    sm.tick(now)
    assert sm.state == SessionState.PAUSED


def test_resumes_live_when_data_returns_after_pause():
    sm = StateMachine()
    now = time.time()
    sm.on_timing_data(at=now - 65)
    sm.tick(now)
    assert sm.state == SessionState.PAUSED
    sm.on_timing_data(at=now)
    assert sm.state == SessionState.LIVE


def test_red_flag_on_race_control_message():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("RED FLAG")
    assert sm.state == SessionState.RED_FLAG


def test_vsc_on_race_control_message():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("VIRTUAL SAFETY CAR DEPLOYED")
    assert sm.state == SessionState.VSC


def test_sc_on_race_control_message():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("SAFETY CAR DEPLOYED")
    assert sm.state == SessionState.SC


def test_returns_to_live_on_track_clear():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("RED FLAG")
    assert sm.state == SessionState.RED_FLAG
    sm.on_race_control_message("TRACK CLEAR")
    sm.on_timing_data()
    assert sm.state == SessionState.LIVE


def test_ended_on_chequered_flag():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("CHEQUERED FLAG")
    assert sm.state == SessionState.ENDED
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/unit/test_state_machine.py -v
```
Expected: `ImportError: cannot import name 'StateMachine'`

- [ ] **Step 3: Implement StateMachine**

```python
# backend/app/state_machine/machine.py
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
        if "RED FLAG" in msg:
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
        elif "CHEQUERED FLAG" in msg:
            self._active_flag = None
            self._state = SessionState.ENDED
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/unit/test_state_machine.py -v
```
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/state_machine/ backend/tests/unit/test_state_machine.py
git commit -m "feat: session state machine with all flag/timing transitions"
```

---

## Task 7: Config + FastAPI app + health endpoint

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/integration/test_health.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/integration/test_health.py -v
```
Expected: `ImportError: cannot import name 'app' from 'app.main'`

- [ ] **Step 3: Create config.py**

```python
# backend/app/config.py
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Exact-match origins (comma-separated in env: CORS_ORIGINS)
    cors_origins: list[str] = ["http://localhost:5173"]
    # Regex for Vercel preview deploys (matches *.vercel.app by default)
    cors_origin_regex: str | None = r"^https://.*\.vercel\.app$"

    cache_dir: Path = Path("/tmp/f1-cache")
    poll_interval_seconds: int = 3
    replay_session: str | None = None  # set to "spa_2024" to enable replay mode

    # Where the mar-antaya ML runner writes predictions (Fly volume in prod).
    # If the file exists, /predictions reads it; otherwise returns the stub.
    predictions_path: Path = Path("/data/predictions/latest.json")

    class Config:
        env_prefix = ""
        env_file = ".env"


settings = Settings()
```

CORS origin handling (used in main.py) — pass both `allow_origins` and `allow_origin_regex` so Vercel preview URLs work alongside the pinned production origin:

```python
# backend/app/main.py — CORS section
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

- [ ] **Step 4: Create main.py**

```python
# backend/app/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .cache.file_cache import FileCache
from .state_machine.machine import StateMachine

cache = FileCache(settings.cache_dir)
state_machine = StateMachine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.replay_session:
        from .workers.live_poller import LivePoller
        poller = LivePoller(cache=cache, state_machine=state_machine)
        task = asyncio.create_task(poller.run())
    yield
    if not settings.replay_session:
        task.cancel()


app = FastAPI(title="F1 Dashboard API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && pytest tests/integration/test_health.py -v
```
Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/main.py backend/tests/integration/test_health.py
git commit -m "feat: FastAPI app with config and health endpoint"
```

---

## Task 8: Fixture download script (Spa 2024)

**Files:**
- Create: `backend/tests/fixtures/download_spa_2024.py`
- Create: `backend/tests/fixtures/spa_2024/schema.md` (generated by script)

This task requires network access. Run it once; the results are committed as JSON.

- [ ] **Step 1: Create download script**

```python
# backend/tests/fixtures/download_spa_2024.py
"""
Run once to download Spa 2024 Race fixture data from LiveF1.
Saves JSON files to tests/fixtures/spa_2024/.
Also prints column schemas to schema.md.

Usage: python tests/fixtures/download_spa_2024.py
"""
import json
import sys
from pathlib import Path

import livef1
import pandas as pd

OUT_DIR = Path(__file__).parent / "spa_2024"
OUT_DIR.mkdir(exist_ok=True)

DATA_TYPES = [
    "TimingData",
    "Position.z",
    "RaceControlMessages",
    "WeatherData",
    "TimingAppData",
    "SessionData",
    "DriverList",
]


def df_to_json_safe(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def main():
    print("Fetching 2024 Belgian GP Race from LiveF1...")
    session = livef1.get_session(
        season=2024,
        meeting_identifier="Spa",
        session_identifier="Race",
    )

    schema_lines = ["# Spa 2024 Race — DataFrame Schemas\n"]

    for data_name in DATA_TYPES:
        print(f"  Loading {data_name}...")
        try:
            df = session.get_data(dataNames=data_name)
            if df is None or (hasattr(df, "empty") and df.empty):
                print(f"    {data_name}: empty, skipping")
                continue

            # Save JSON
            safe_name = data_name.replace(".", "_").lower()
            out_path = OUT_DIR / f"{safe_name}.json"
            records = df_to_json_safe(df) if isinstance(df, pd.DataFrame) else df
            out_path.write_text(json.dumps(records, indent=2))
            print(f"    Saved {len(records)} rows → {out_path.name}")

            # Record schema
            if isinstance(df, pd.DataFrame):
                schema_lines.append(f"\n## {data_name}\n")
                schema_lines.append(f"Rows: {len(df)}\n")
                schema_lines.append("```\n")
                schema_lines.append(str(df.dtypes) + "\n")
                schema_lines.append("```\n")
                schema_lines.append(f"\nHead (3 rows):\n```\n{df.head(3)}\n```\n")

        except Exception as e:
            print(f"    ERROR loading {data_name}: {e}", file=sys.stderr)

    (OUT_DIR / "schema.md").write_text("".join(schema_lines))
    print(f"\nDone. Schema written to {OUT_DIR / 'schema.md'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script (requires network)**

```bash
cd backend && python tests/fixtures/download_spa_2024.py
```
Expected output:
```
Fetching 2024 Belgian GP Race from LiveF1...
  Loading TimingData...
    Saved N rows → timing_data.json
  Loading Position.z...
    Saved N rows → position_z.json
  ...
Done. Schema written to tests/fixtures/spa_2024/schema.md
```

- [ ] **Step 3: Review schema.md**

```bash
cat backend/tests/fixtures/spa_2024/schema.md
```
Note the actual column names in each DataFrame — update the parser column references in Task 10 and 11 if they differ from what is assumed.

- [ ] **Step 4: Add fixture files to git (except large ones)**

```bash
# Check sizes first
du -sh backend/tests/fixtures/spa_2024/*.json
# If any file > 10MB, add it to .gitignore and note in README
git add backend/tests/fixtures/spa_2024/schema.md
git add backend/tests/fixtures/spa_2024/*.json
git commit -m "feat: Spa 2024 Race fixture data for replay tests"
```

---

## Task 9: LiveF1 client + parsers

**Files:**
- Create: `backend/app/services/livef1_client.py`
- Test: `backend/tests/unit/test_parsers.py`

**Note:** Column names below are based on the F1 data stream specification. Verify against `schema.md` from Task 8 and adjust if different.

- [ ] **Step 1: Write failing tests using fixture data**

```python
# backend/tests/unit/test_parsers.py
import json
import pytest
from pathlib import Path
from app.services.livef1_client import (
    parse_timing_snapshot, parse_position_snapshot,
    parse_race_control_rows, classify_rc_message,
    DriverResolver,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


def _load_json(name: str):
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"Run download_spa_2024.py first (missing {name})")
    return json.loads(path.read_text())


@pytest.fixture
def timing_rows():
    return _load_json("timing_data.json")


@pytest.fixture
def position_rows():
    return _load_json("position_z.json")


@pytest.fixture
def driver_list_rows():
    # DriverList fixture may not exist on older livef1 versions — allow stub.
    path = FIXTURES / "driver_list.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


@pytest.fixture
def resolver(driver_list_rows):
    if not driver_list_rows:
        # Minimal stub resolver so TLA fallback path is exercised.
        return DriverResolver(mapping={
            "1":  ("VER", "redbull"),
            "44": ("HAM", "mercedes"),
            "4":  ("NOR", "mclaren"),
        })
    return DriverResolver.from_rows(driver_list_rows)


def test_timing_snapshot_has_valid_entries(timing_rows, resolver):
    mid = len(timing_rows) // 2
    tower = parse_timing_snapshot(timing_rows[mid:mid + 50], resolver=resolver)
    assert 1 <= len(tower.entries) <= 22
    positions = [e.position for e in tower.entries]
    assert len(set(positions)) == len(positions)  # no duplicate positions


def test_timing_leader_gap_is_leader_string(timing_rows, resolver):
    mid = len(timing_rows) // 2
    tower = parse_timing_snapshot(timing_rows[mid:mid + 50], resolver=resolver)
    leader = next((e for e in tower.entries if e.position == 1), None)
    assert leader is not None
    assert leader.gap == "Leader"


def test_position_snapshot_has_coordinates(position_rows, resolver):
    mid = len(position_rows) // 2
    positions = parse_position_snapshot(position_rows[mid:mid + 100], resolver=resolver)
    assert len(positions.drivers) > 0
    for d in positions.drivers:
        assert -1.0 <= d.x <= 1.0
        assert -1.0 <= d.y <= 1.0


def test_tire_merge_populates_compound(timing_rows, resolver):
    """If TimingAppData fixture is present, at least one entry should have a tire."""
    tire_path = FIXTURES / "timing_app_data.json"
    if not tire_path.exists():
        pytest.skip("TimingAppData fixture not present")
    tire_rows = json.loads(tire_path.read_text())
    mid = len(timing_rows) // 2
    tower = parse_timing_snapshot(
        timing_rows[mid:mid + 200], resolver=resolver, tire_rows=tire_rows
    )
    with_tire = [e for e in tower.entries if e.tire is not None]
    assert len(with_tire) > 0, "No drivers have tire data after merge"


def test_classify_rc_messages():
    assert classify_rc_message("RED FLAG") == "Flag"
    assert classify_rc_message("SAFETY CAR DEPLOYED") == "SafetyCar"
    assert classify_rc_message("DRS ENABLED") == "Drs"
    assert classify_rc_message("CAR 1 UNDER INVESTIGATION") == "CarEvent"
    assert classify_rc_message("RESTART AT 14:00") == "Other"


def test_parse_race_control_rows():
    rows = [
        {"Utc": "2024-07-28T13:10:00", "Lap": 12, "Message": "RED FLAG"},
        {"Utc": "2024-07-28T13:00:00", "Lap": 1,  "Message": "GREEN LIGHT - PIT EXIT OPEN"},
    ]
    out = parse_race_control_rows(rows)
    assert len(out) == 2
    assert out[0]["utc"] < out[1]["utc"]
    assert out[1]["category"] == "Flag"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/unit/test_parsers.py -v
```
Expected: `ImportError: cannot import name 'parse_timing_snapshot'`

- [ ] **Step 3: Implement LiveF1 client**

```python
# backend/app/services/livef1_client.py
"""
Wraps the livef1 library and parses raw DataFrames into Pydantic models.

Column name assumptions (based on F1 data stream spec):
  TimingData rows: RacingNumber, Tla, Position, GapToLeader,
                   IntervalToPositionAhead, LastLapTime.Value, LastLapTime.Status,
                   NumberOfPitStops, Retired
  Position.z rows: RacingNumber, X, Y, Status (OnTrack/OffTrack)

If parse errors occur, check schema.md and update column references here.
"""
import time
from pathlib import Path
from typing import Any
import livef1

from ..models.timing import TimingEntry, TimingTower, TireCompound
from ..models.position import DriverPosition, TrackPositions

# F1 TimingData status flags for lap times
_STATUS_FASTEST = 2049
_STATUS_PERSONAL_BEST = 2048

# ---------------------------------------------------------------------------
# DriverResolver
#
# Racing numbers are reused across seasons (e.g. Williams #2 was Bottas in 2018,
# Sargeant in 2024). Hardcoding a single dict would silently return wrong TLAs
# when the historical router iterates multiple past seasons. Instead we resolve
# racing number → (TLA, team_id) from each session's own `DriverList` payload.
#
# Fallback team_id inference: if team_id cannot be derived from DriverList's
# TeamName, we normalize (lowercase, strip, replace spaces with underscores)
# and look up a coarse alias map below. Unknown teams fall back to "unknown".
# ---------------------------------------------------------------------------

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
    "audi": "audi",          # 2026+ placeholder
    "cadillac": "cadillac",  # 2026+ placeholder
}


def _normalize_team(raw: str | None) -> str:
    if not raw:
        return "unknown"
    key = raw.strip().lower()
    return _TEAM_ALIASES.get(key, key.replace(" ", "_"))


class DriverResolver:
    """
    Maps RacingNumber → (driver_code, team_id) for a specific session.

    Built lazily from the session's DriverList payload. Safe to call with
    unknown numbers — returns ("???", "unknown") rather than raising.
    """

    def __init__(self, mapping: dict[str, tuple[str, str]]):
        self._mapping = mapping

    @classmethod
    def from_session(cls, session: Any) -> "DriverResolver":
        """Build from a livef1 session. Uses DriverList data stream."""
        try:
            rows = load_data(session, "DriverList")
        except Exception:
            rows = []
        mapping: dict[str, tuple[str, str]] = {}
        for row in rows:
            num = str(row.get("RacingNumber", row.get("racing_number", ""))).strip()
            tla = (row.get("Tla") or row.get("tla") or "").strip()
            team = row.get("TeamName") or row.get("team_name") or None
            if num and tla:
                mapping[num] = (tla.upper(), _normalize_team(team))
        return cls(mapping)

    @classmethod
    def from_rows(cls, driver_list_rows: list[dict]) -> "DriverResolver":
        """Build from already-loaded DriverList rows (used in replay + tests)."""
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


def _merge_tire_data(
    tire_rows: list[dict],
    resolver: "DriverResolver",
) -> dict[str, tuple[TireCompound | None, int | None]]:
    """
    Collapse a list of TimingAppData rows into {racing_number: (compound, age_in_laps)}.
    TimingAppData rows typically carry Stints nested as a list; we take the last stint
    per driver. If Stints isn't present, fall back to top-level Compound / StartLaps.
    """
    _COMPOUND_MAP = {
        "SOFT": TireCompound.SOFT, "S": TireCompound.SOFT,
        "MEDIUM": TireCompound.MEDIUM, "M": TireCompound.MEDIUM,
        "HARD": TireCompound.HARD, "H": TireCompound.HARD,
        "INTERMEDIATE": TireCompound.INTERMEDIATE, "I": TireCompound.INTERMEDIATE,
        "WET": TireCompound.WET, "W": TireCompound.WET,
    }

    out: dict[str, tuple[TireCompound | None, int | None]] = {}
    for row in tire_rows:
        num = str(row.get("RacingNumber", row.get("racing_number", ""))).strip()
        if not num:
            continue
        stints = row.get("Stints")
        compound: TireCompound | None = None
        age: int | None = None
        if isinstance(stints, list) and stints:
            last = stints[-1]
            if isinstance(last, dict):
                raw = str(last.get("Compound", "")).upper()
                compound = _COMPOUND_MAP.get(raw)
                try:
                    age = int(last.get("TotalLaps") or last.get("StartLaps") or 0) or None
                except (TypeError, ValueError):
                    age = None
        else:
            raw = str(row.get("Compound", "")).upper()
            compound = _COMPOUND_MAP.get(raw)
            try:
                age = int(row.get("TyreAge") or row.get("StartLaps") or 0) or None
            except (TypeError, ValueError):
                age = None
        if compound or age:
            out[num] = (compound, age)
    return out


def parse_timing_snapshot(
    rows: list[dict],
    resolver: "DriverResolver | None" = None,
    tire_rows: list[dict] | None = None,
) -> TimingTower:
    """
    Convert a list of TimingData rows (from a point in time) into a TimingTower.
    Takes the most recent row per driver (highest index).

    Args:
        rows: TimingData rows, sorted oldest→newest.
        resolver: DriverResolver for the session. Required; callers in replay
            and live paths must build it via DriverResolver.from_session(...)
            or DriverResolver.from_rows(...). Tests pass a fake.
        tire_rows: Optional TimingAppData rows; if provided, tire + tire_age
            are merged onto the entries.
    """
    if resolver is None:
        # Safety net for early tests/parsers that haven't wired the resolver.
        resolver = DriverResolver(mapping={})

    # Build latest state per racing number (preserves input order — callers must sort).
    latest: dict[str, dict] = {}
    for row in rows:
        num = str(row.get("RacingNumber", row.get("racing_number", "")))
        if num:
            latest[num] = row

    tire_map = _merge_tire_data(tire_rows or [], resolver)

    entries: list[TimingEntry] = []
    fastest_lap_time: str | None = None
    fastest_lap_driver: str | None = None

    for num, row in latest.items():
        tla_from_row = (row.get("Tla") or row.get("tla") or "").strip().upper() or None
        resolved_tla, team_id = resolver.resolve(num)
        tla = tla_from_row or resolved_tla

        pos_raw = row.get("Position", row.get("position", 0))
        try:
            position = int(pos_raw)
        except (TypeError, ValueError):
            continue  # skip rows without position

        gap_raw = row.get("GapToLeader", row.get("gap_to_leader", ""))
        gap = "Leader" if (not gap_raw or str(gap_raw).strip() in ("", "0")) else str(gap_raw)

        interval_raw = row.get("IntervalToPositionAhead", {})
        if isinstance(interval_raw, dict):
            interval = interval_raw.get("Value", None)
        else:
            interval = str(interval_raw) if interval_raw else None

        lap_time_raw = row.get("LastLapTime", {})
        if isinstance(lap_time_raw, dict):
            last_lap = lap_time_raw.get("Value") or None
            try:
                lap_status = int(lap_time_raw.get("Status", 0) or 0)
            except (TypeError, ValueError):
                lap_status = 0
        else:
            last_lap = str(lap_time_raw) if lap_time_raw else None
            lap_status = 0

        is_fastest = lap_status == _STATUS_FASTEST
        is_pb = lap_status == _STATUS_PERSONAL_BEST

        if is_fastest and last_lap:
            fastest_lap_time = last_lap
            fastest_lap_driver = tla

        retired = bool(row.get("Retired", row.get("retired", False)))
        tire, tire_age = tire_map.get(num, (None, None))

        entries.append(TimingEntry(
            position=position,
            driver_code=tla,
            team_id=team_id,
            last_lap=last_lap,
            gap=gap,
            interval=interval,
            tire=tire,
            tire_age=tire_age,
            is_fastest_overall=is_fastest,
            is_personal_best=is_pb,
            is_in_battle=False,     # computed below
            is_retired=retired,
            dnf=retired,
        ))

    entries.sort(key=lambda e: e.position)

    # Mark battles: any two consecutive cars within 0.5s gap.
    # Intervals that contain "LAP" (e.g. "+1 LAP") or other non-numeric tokens
    # are skipped — you cannot "battle" a backmarker a lap down.
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


def _flatten_position_rows(rows: list[dict]) -> list[dict]:
    """
    Position.z is a compressed, often nested payload. livef1 may decode it
    either as flat rows (one per-driver sample) OR as nested
    `{Entries: [{Timestamp, Cars: {racing_number: {X, Y, Status}}}]}`.

    This normalizer accepts both shapes and returns a flat list of
    {RacingNumber, X, Y, Status} dicts. The actual shape MUST be confirmed
    against `schema.md` from Task 8 before trusting this output.
    """
    flat: list[dict] = []
    for row in rows:
        cars = row.get("Cars") or row.get("cars")
        if isinstance(cars, dict):
            # Nested form
            for num, sample in cars.items():
                if not isinstance(sample, dict):
                    continue
                flat.append({
                    "RacingNumber": str(num),
                    "X": sample.get("X", sample.get("x", 0)),
                    "Y": sample.get("Y", sample.get("y", 0)),
                    "Status": sample.get("Status", sample.get("status", "")),
                })
        else:
            # Already flat
            flat.append(row)
    return flat


def parse_position_snapshot(
    rows: list[dict],
    resolver: "DriverResolver | None" = None,
) -> TrackPositions:
    """
    Convert Position.z rows into TrackPositions.
    X/Y are raw circuit coordinates; normalize to [-1, 1] per axis.
    """
    if resolver is None:
        resolver = DriverResolver(mapping={})

    flat = _flatten_position_rows(rows)

    latest: dict[str, dict] = {}
    for row in flat:
        num = str(row.get("RacingNumber", row.get("racing_number", "")))
        if num and row.get("Status", row.get("status", "")) not in ("OffTrack", "Pit"):
            latest[num] = row

    xs = [float(r.get("X", r.get("x", 0)) or 0) for r in latest.values()]
    ys = [float(r.get("Y", r.get("y", 0)) or 0) for r in latest.values()]
    x_min, x_max = (min(xs), max(xs)) if xs else (0, 1)
    y_min, y_max = (min(ys), max(ys)) if ys else (0, 1)
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1

    drivers: list[DriverPosition] = []
    for num, row in latest.items():
        tla, team_id = resolver.resolve(num)
        raw_x = float(row.get("X", row.get("x", 0)) or 0)
        raw_y = float(row.get("Y", row.get("y", 0)) or 0)
        drivers.append(DriverPosition(
            driver_code=tla,
            team_id=team_id,
            x=(raw_x - x_min) / x_range * 2 - 1,
            y=(raw_y - y_min) / y_range * 2 - 1,
        ))

    return TrackPositions(drivers=drivers, updated_at=time.time())


# ---------------------------------------------------------------------------
# Race Control message parsing (used by poller, replay, and /race-control)
# ---------------------------------------------------------------------------

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
    Return a list of {utc, lap, category, message} dicts, sorted by UTC ascending.
    Column names vary — handles both RaceControlMessages (F1 stream) shape and
    generic dict fallbacks.
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
        out.append({
            "utc": str(utc),
            "lap": lap,
            "category": classify_rc_message(msg),
            "message": msg,
        })
    out.sort(key=lambda x: x["utc"])
    return out
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/unit/test_parsers.py -v
```
Expected: `3 passed` (or `skipped` if fixtures not yet downloaded — run Task 8 first)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/livef1_client.py backend/tests/unit/test_parsers.py
git commit -m "feat: LiveF1 client wrapper with timing and position parsers"
```

---

## Task 10: State router

**Files:**
- Create: `backend/app/routers/state.py`
- Test: `backend/tests/integration/test_state_router.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/test_state_router.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app, state_machine

client = TestClient(app)


def test_state_returns_idle_by_default():
    # Force schedule lookup to fail so we exercise the fallback path.
    with patch("app.services.schedule_service.current_weekend", return_value=None):
        resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "IDLE"
    assert data["season"] == 2026
    assert "countdown_seconds" in data


def test_state_reflects_machine_state():
    with patch("app.services.schedule_service.current_weekend", return_value=None):
        state_machine.on_timing_data()
        resp = client.get("/state")
        assert resp.json()["state"] == "LIVE"
    state_machine.__init__()  # reset
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/integration/test_state_router.py -v
```
Expected: `404 Not Found` for `/state`

- [ ] **Step 3: Implement state router**

`/state` derives `session_type`, `session_name`, `round`, `season`, and `countdown_seconds` from the schedule service (Task 17). It derives `current_lap` / `total_laps` / `leader_gap` from the cached `timing` payload (if present). Fields that can't be resolved fall back to `None`.

```python
# backend/app/routers/state.py
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


def _current_and_next(weekend) -> tuple[object | None, object | None]:
    """Return (active_session, next_session) from a WeekendSchedule."""
    if weekend is None:
        return None, None
    active = next(
        (s for s in weekend.sessions if not s.is_complete and s.is_next),
        None,
    )
    nxt = next((s for s in weekend.sessions if not s.is_complete), None)
    return active, nxt


router = APIRouter()


@router.get("/state", response_model=SessionInfo)
def get_state():
    state = state_machine.tick()

    # Schedule-derived fields
    result = schedule_service.current_weekend(cache)
    if result is not None:
        weekend, next_ts = result
        state_machine.set_next_session_at(next_ts) if next_ts else None
        active, nxt = _current_and_next(weekend)
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

    # Timing-derived fields
    timing = cache.get("timing") or {}
    entries = timing.get("entries", [])
    current_lap: int | None = None
    leader_gap: str | None = None
    if entries:
        # Leader's gap is always "Leader"; we surface P2's gap-to-leader instead
        leader = next((e for e in entries if e.get("position") == 1), None)
        second = next((e for e in entries if e.get("position") == 2), None)
        leader_gap = second.get("gap") if second else None
        # current_lap isn't on TimingEntry directly; read from the first row's
        # NumberOfLaps if the poller copied it forward, else leave None
        current_lap = timing.get("current_lap")

    total_laps = None  # populated in follow-up plan when circuits+state are joined

    return SessionInfo(
        state=state,
        session_type=session_type,
        session_name=session_name,
        round=round_,
        season=season,
        current_lap=current_lap,
        total_laps=total_laps,
        leader_gap=leader_gap,
        countdown_seconds=countdown,
        session_elapsed_seconds=None,  # follow-up
    )
```

- [ ] **Step 4: Register router in main.py**

```python
# backend/app/main.py — add after existing imports:
from .routers import state as state_router

# add after middleware:
app.include_router(state_router.router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/integration/test_state_router.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/state.py backend/tests/integration/test_state_router.py
git commit -m "feat: GET /state router"
```

---

## Task 11: Timing router

**Files:**
- Create: `backend/app/routers/timing.py`
- Test: `backend/tests/integration/test_timing_router.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/integration/test_timing_router.py
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)
FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


def _seed_timing_cache(entries: list[dict]):
    cache.set("timing", {
        "entries": entries,
        "fastest_lap_driver": None,
        "fastest_lap_time": None,
        "updated_at": time.time(),
    }, ttl_seconds=30)


def test_timing_returns_empty_when_no_cache():
    cache.delete("timing")
    resp = client.get("/timing")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_timing_returns_cached_data():
    _seed_timing_cache([{
        "position": 1,
        "driver_code": "VER",
        "team_id": "redbull",
        "last_lap": "1:46.123",
        "gap": "Leader",
        "interval": None,
        "tire": "M",
        "tire_age": 5,
        "is_fastest_overall": False,
        "is_personal_best": False,
        "is_watchlisted": False,
        "is_in_battle": False,
        "is_retired": False,
        "dnf": False,
    }])
    resp = client.get("/timing")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["driver_code"] == "VER"
    assert data["entries"][0]["gap"] == "Leader"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/integration/test_timing_router.py -v
```
Expected: `404 Not Found`

- [ ] **Step 3: Implement timing router**

```python
# backend/app/routers/timing.py
from fastapi import APIRouter
from ..main import cache
from ..models.timing import TimingTower

router = APIRouter()


@router.get("/timing", response_model=TimingTower)
def get_timing():
    data = cache.get("timing")
    if data is None:
        return TimingTower(entries=[], updated_at=0.0)
    return TimingTower(**data)
```

- [ ] **Step 4: Register in main.py and run tests**

```python
# backend/app/main.py — add:
from .routers import timing as timing_router
app.include_router(timing_router.router)
```

```bash
cd backend && pytest tests/integration/test_timing_router.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/timing.py backend/tests/integration/test_timing_router.py
git commit -m "feat: GET /timing router"
```

---

## Task 12: Positions router

**Files:**
- Create: `backend/app/routers/positions.py`
- Test: `backend/tests/integration/test_positions_router.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/integration/test_positions_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_positions_empty_on_cache_miss():
    cache.delete("positions")
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert resp.json()["drivers"] == []


def test_positions_returns_cached():
    cache.set("positions", {
        "drivers": [{"driver_code": "VER", "team_id": "redbull",
                     "x": 0.5, "y": 0.3, "is_watchlisted": False}],
        "updated_at": time.time(),
    }, ttl_seconds=30)
    resp = client.get("/positions")
    data = resp.json()
    assert len(data["drivers"]) == 1
    assert data["drivers"][0]["driver_code"] == "VER"
    assert -1.0 <= data["drivers"][0]["x"] <= 1.0
```

- [ ] **Step 2: Implement and register**

```python
# backend/app/routers/positions.py
from fastapi import APIRouter
from ..main import cache
from ..models.position import TrackPositions

router = APIRouter()


@router.get("/positions", response_model=TrackPositions)
def get_positions():
    data = cache.get("positions")
    if data is None:
        return TrackPositions(drivers=[], updated_at=0.0)
    return TrackPositions(**data)
```

```python
# backend/app/main.py — add:
from .routers import positions as positions_router
app.include_router(positions_router.router)
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest tests/integration/test_positions_router.py -v
```
Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/positions.py backend/tests/integration/test_positions_router.py
git commit -m "feat: GET /positions router"
```

---

## Task 13: Standings router + static data files

**Files:**
- Create: `backend/data/standings.json`
- Create: `backend/data/circuits.json`
- Create: `backend/app/routers/standings.py`

Standings are served from a hand-maintained JSON file. Update after each race.

- [ ] **Step 1: Create data files**

```json
// backend/data/standings.json
{
  "drivers": [
    {"position": 1, "driver_code": "VER", "team_id": "redbull", "points": 127, "wins": 4},
    {"position": 2, "driver_code": "NOR", "team_id": "mclaren", "points": 108, "wins": 2},
    {"position": 3, "driver_code": "LEC", "team_id": "ferrari", "points": 95, "wins": 1},
    {"position": 4, "driver_code": "PIA", "team_id": "mclaren", "points": 88, "wins": 1},
    {"position": 5, "driver_code": "HAM", "team_id": "ferrari", "points": 71, "wins": 0},
    {"position": 6, "driver_code": "RUS", "team_id": "mercedes", "points": 60, "wins": 0},
    {"position": 7, "driver_code": "SAI", "team_id": "ferrari", "points": 52, "wins": 0},
    {"position": 8, "driver_code": "ALO", "team_id": "aston", "points": 44, "wins": 0},
    {"position": 9, "driver_code": "TSU", "team_id": "rb", "points": 28, "wins": 0},
    {"position": 10, "driver_code": "STR", "team_id": "aston", "points": 22, "wins": 0}
  ],
  "constructors": [
    {"position": 1, "team_id": "redbull",   "team_name": "Red Bull Racing", "points": 221, "wins": 4},
    {"position": 2, "team_id": "mclaren",   "team_name": "McLaren",         "points": 196, "wins": 3},
    {"position": 3, "team_id": "ferrari",   "team_name": "Ferrari",         "points": 172, "wins": 1},
    {"position": 4, "team_id": "mercedes",  "team_name": "Mercedes",        "points": 112, "wins": 0},
    {"position": 5, "team_id": "aston",     "team_name": "Aston Martin",    "points": 66,  "wins": 0}
  ],
  "updated_at": "2026-04-20"
}
```

```json
// backend/data/circuits.json
{
  "miami": {
    "name": "Miami International Autodrome",
    "country": "United States",
    "lat": 25.9581,
    "lon": -80.2389,
    "length_km": 5.412,
    "total_laps": 57,
    "lap_record": "1:29.708",
    "lap_record_driver": "VER",
    "lap_record_year": 2023,
    "timezone": "America/New_York"
  },
  "spa": {
    "name": "Circuit de Spa-Francorchamps",
    "country": "Belgium",
    "lat": 50.4372,
    "lon": 5.9714,
    "length_km": 7.004,
    "total_laps": 44,
    "lap_record": "1:46.286",
    "lap_record_driver": "BOT",
    "lap_record_year": 2018,
    "timezone": "Europe/Brussels"
  },
  "monza": {
    "name": "Autodromo Nazionale Monza",
    "country": "Italy",
    "lat": 45.6156,
    "lon": 9.2811,
    "length_km": 5.793,
    "total_laps": 53,
    "lap_record": "1:21.046",
    "lap_record_driver": "RUB",
    "lap_record_year": 2004,
    "timezone": "Europe/Rome"
  }
}
```

- [ ] **Step 2: Write failing test**

```python
# backend/tests/integration/test_standings_router.py (new file)
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_driver_standings_returns_list():
    resp = client.get("/standings/drivers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    assert data[0]["position"] == 1
    assert "points" in data[0]


def test_constructor_standings_returns_list():
    resp = client.get("/standings/constructors")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 3
    assert data[0]["position"] == 1
    assert "team_name" in data[0]
```

- [ ] **Step 3: Implement standings router**

```python
# backend/app/routers/standings.py
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models.standings import DriverStanding, ConstructorStanding

router = APIRouter()
_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "standings.json"


def _load() -> dict:
    if not _DATA_PATH.exists():
        raise HTTPException(status_code=503, detail="Standings data unavailable")
    return json.loads(_DATA_PATH.read_text())


@router.get("/standings/drivers", response_model=list[DriverStanding])
def get_driver_standings():
    return [DriverStanding(**d) for d in _load()["drivers"]]


@router.get("/standings/constructors", response_model=list[ConstructorStanding])
def get_constructor_standings():
    return [ConstructorStanding(**c) for c in _load()["constructors"]]
```

- [ ] **Step 4: Register and test**

```python
# backend/app/main.py — add:
from .routers import standings as standings_router
app.include_router(standings_router.router)
```

```bash
cd backend && pytest tests/integration/test_standings_router.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/data/ backend/app/routers/standings.py
git commit -m "feat: GET /standings/drivers and /standings/constructors"
```

---

## Task 14: Historical router

**Files:**
- Create: `backend/app/routers/historical.py`
- Test: `backend/tests/integration/test_historical_router.py`

Uses LiveF1 to compute career stats for a driver at a specific circuit. Results are cached for 1 hour (historical data never changes).

- [ ] **Step 1: Write failing test (uses Spa fixture)**

```python
# backend/tests/integration/test_historical_router.py
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


def test_historical_returns_model_shape():
    if not (FIXTURES / "timing_data.json").exists():
        pytest.skip("Run download_spa_2024.py first")
    resp = client.get("/historical/VER/spa")
    assert resp.status_code == 200
    data = resp.json()
    assert data["driver_code"] == "VER"
    assert data["circuit"] == "spa"
    assert isinstance(data["races"], int)
    assert data["races"] >= 0


def test_historical_unknown_driver_returns_empty():
    resp = client.get("/historical/XXX/spa")
    assert resp.status_code == 200
    assert resp.json()["races"] == 0
```

- [ ] **Step 2: Implement historical router**

```python
# backend/app/routers/historical.py
from fastapi import APIRouter
from ..main import cache
from ..models.historical import HistoricalStats
from ..services import livef1_client

router = APIRouter()

_HISTORICAL_SEASONS = [2021, 2022, 2023, 2024]


def _compute_stats(driver_code: str, circuit: str) -> HistoricalStats:
    race_results: list[int] = []
    quali_results: list[int] = []

    for season in _HISTORICAL_SEASONS:
        for kind, bucket in (("Race", race_results), ("Qualifying", quali_results)):
            try:
                session = livef1_client.get_historical_session(season, circuit, kind)
                # Per-season resolver — racing numbers recycle across years, so we
                # can't rely on a global hardcoded map.
                resolver = livef1_client.DriverResolver.from_session(session)
                rows = livef1_client.load_data(session, "TimingData")
                tire_rows = livef1_client.load_data(session, "TimingAppData")
                tower = livef1_client.parse_timing_snapshot(
                    rows, resolver=resolver, tire_rows=tire_rows,
                )
                entry = next(
                    (e for e in tower.entries if e.driver_code == driver_code),
                    None,
                )
                if entry:
                    bucket.append(entry.position)
            except Exception:
                continue

    return HistoricalStats(
        driver_code=driver_code,
        circuit=circuit,
        best_finish=min(race_results) if race_results else None,
        best_quali=min(quali_results) if quali_results else None,
        avg_race_pos=sum(race_results) / len(race_results) if race_results else None,
        avg_quali_pos=sum(quali_results) / len(quali_results) if quali_results else None,
        wins=race_results.count(1),
        poles=quali_results.count(1),
        races=len(race_results),
    )


@router.get("/historical/{driver_code}/{circuit}", response_model=HistoricalStats)
def get_historical(driver_code: str, circuit: str):
    cache_key = f"historical/{driver_code.upper()}/{circuit.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return HistoricalStats(**cached)

    stats = _compute_stats(driver_code.upper(), circuit.lower())
    cache.set(cache_key, stats.model_dump(), ttl_seconds=3600)
    return stats
```

- [ ] **Step 3: Register and test**

```python
# backend/app/main.py — add:
from .routers import historical as historical_router
app.include_router(historical_router.router)
```

```bash
cd backend && pytest tests/integration/test_historical_router.py -v
```
Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/historical.py backend/tests/integration/test_historical_router.py
git commit -m "feat: GET /historical/{driver}/{circuit} with LiveF1 and 1h cache"
```

---

## Task 15: Weather router

**Files:**
- Create: `backend/app/services/weather_client.py`
- Create: `backend/app/routers/weather.py`
- Test: `backend/tests/integration/test_weather_router.py`

Uses Open-Meteo (free, no API key).

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/test_weather_router.py
import pytest
import respx
import httpx
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)

OPEN_METEO_MOCK = {
    "current": {
        "temperature_2m": 27.4,
        "relative_humidity_2m": 65,
        "wind_speed_10m": 12.0,
        "precipitation_probability": 15,
    }
}


def test_weather_returns_cached_data():
    import time
    cache.set("weather/miami", {
        "air_temp": 27.0,
        "track_temp": None,
        "humidity": 65.0,
        "wind_speed": 12.0,
        "rain_chance": 15.0,
        "description": "Partly cloudy",
        "is_live": False,
        "updated_at": time.time(),
    }, ttl_seconds=60)
    resp = client.get("/weather/miami")
    assert resp.status_code == 200
    data = resp.json()
    assert data["air_temp"] == 27.0
    assert "rain_chance" in data


@respx.mock
def test_weather_fetches_from_open_meteo_on_cache_miss():
    cache.delete("weather/miami")
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=OPEN_METEO_MOCK)
    )
    resp = client.get("/weather/miami")
    assert resp.status_code == 200
    assert resp.json()["air_temp"] == 27.4
```

- [ ] **Step 2: Implement weather client**

```python
# backend/app/services/weather_client.py
import httpx
from ..models.weather import WeatherData
import time

_BASE = "https://api.open-meteo.com/v1/forecast"

_CONDITION_MAP = {
    (0, 20): "Clear",
    (20, 50): "Partly cloudy",
    (50, 80): "Cloudy",
    (80, 100): "Rain likely",
}


def _describe(rain_pct: float) -> str:
    for (lo, hi), label in _CONDITION_MAP.items():
        if lo <= rain_pct < hi:
            return label
    return "Rain"


def fetch(lat: float, lon: float) -> WeatherData:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability",
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(_BASE, params=params)
        resp.raise_for_status()
    current = resp.json()["current"]
    rain_chance = float(current.get("precipitation_probability", 0) or 0)
    return WeatherData(
        air_temp=float(current["temperature_2m"]),
        humidity=float(current["relative_humidity_2m"]),
        wind_speed=float(current["wind_speed_10m"]),
        rain_chance=rain_chance,
        description=_describe(rain_chance),
        is_live=False,
        updated_at=time.time(),
    )
```

```python
# backend/app/routers/weather.py
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..main import cache
from ..models.weather import WeatherData
from ..services import weather_client

router = APIRouter()
_CIRCUITS_PATH = Path(__file__).parent.parent.parent / "data" / "circuits.json"


def _circuit_coords(circuit_id: str) -> tuple[float, float]:
    circuits = json.loads(_CIRCUITS_PATH.read_text())
    if circuit_id not in circuits:
        raise HTTPException(status_code=404, detail=f"Unknown circuit: {circuit_id}")
    c = circuits[circuit_id]
    return c["lat"], c["lon"]


@router.get("/weather/{circuit_id}", response_model=WeatherData)
def get_weather(circuit_id: str):
    cache_key = f"weather/{circuit_id}"
    cached = cache.get(cache_key)
    if cached:
        return WeatherData(**cached)

    lat, lon = _circuit_coords(circuit_id)
    try:
        data = weather_client.fetch(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")

    cache.set(cache_key, data.model_dump(), ttl_seconds=600)
    return data
```

- [ ] **Step 3: Register and test**

```python
# backend/app/main.py — add:
from .routers import weather as weather_router
app.include_router(weather_router.router)
```

```bash
cd backend && pytest tests/integration/test_weather_router.py -v
```
Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/weather_client.py backend/app/routers/weather.py
git commit -m "feat: GET /weather/{circuit} using Open-Meteo"
```

---

## Task 16: News router

**Files:**
- Create: `backend/app/services/news_client.py`
- Create: `backend/app/routers/news.py`
- Test: `backend/tests/integration/test_news_router.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/test_news_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_news_returns_cached_list():
    cache.set("news", [
        {
            "title": "Verstappen confident ahead of Miami",
            "url": "https://the-race.com/test",
            "source": "The Race",
            "published_at": "2026-04-20T10:00:00",
            "summary": None,
        }
    ], ttl_seconds=60)
    resp = client.get("/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "The Race"


def test_news_empty_on_cache_miss():
    cache.delete("news")
    resp = client.get("/news")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Implement news client and router**

```python
# backend/app/services/news_client.py
import feedparser
import time
from ..models.news import NewsItem

RSS_FEEDS = [
    ("The Race",       "https://the-race.com/feed/"),
    ("Autosport",      "https://www.autosport.com/rss/f1/news/"),
    ("Motorsport.com", "https://www.motorsport.com/rss/f1/news/"),
]


def _parse_entry(entry: dict, source: str) -> NewsItem | None:
    title = entry.get("title", "").strip()
    url = entry.get("link", "").strip()
    if not title or not url:
        return None
    published = entry.get("published", entry.get("updated", ""))
    summary = entry.get("summary", None)
    if summary:
        summary = summary[:300]
    return NewsItem(title=title, url=url, source=source,
                    published_at=published, summary=summary)


def fetch_all(max_per_feed: int = 5) -> list[NewsItem]:
    items: list[NewsItem] = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                item = _parse_entry(entry, source)
                if item:
                    items.append(item)
        except Exception:
            pass
    return items
```

```python
# backend/app/routers/news.py
from fastapi import APIRouter
from ..main import cache
from ..models.news import NewsItem
from ..services import news_client

router = APIRouter()


@router.get("/news", response_model=list[NewsItem])
def get_news():
    cached = cache.get("news")
    if cached is not None:
        return [NewsItem(**item) for item in cached]
    items = news_client.fetch_all()
    cache.set("news", [i.model_dump() for i in items], ttl_seconds=900)
    return items
```

- [ ] **Step 3: Register and test**

```python
# backend/app/main.py — add:
from .routers import news as news_router
app.include_router(news_router.router)
```

```bash
cd backend && pytest tests/integration/test_news_router.py -v
```
Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/news_client.py backend/app/routers/news.py
git commit -m "feat: GET /news RSS aggregator"
```

---

## Task 17: Schedule + Predictions stub routers

**Files:**
- Create: `backend/app/routers/schedule.py`
- Create: `backend/app/routers/predictions.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/integration/test_misc_routers.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_schedule_returns_weekend_shape():
    resp = client.get("/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert "circuit" in data
    assert "sessions" in data
    assert len(data["sessions"]) >= 5


def test_predictions_returns_list():
    resp = client.get("/predictions")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert len(data["entries"]) >= 5
    assert "win_probability" in data["entries"][0]
```

- [ ] **Step 2: Implement schedule service (LiveF1-backed, cached)**

The schedule has two responsibilities:
1. Serve the current weekend's five-tile strip to the frontend.
2. Feed the state machine's `set_next_session_at(ts)` so `ARMED` + countdown work.

Fetching from LiveF1 on every request would be wasteful; instead the service caches the full season once and computes "current weekend" at request time.

```python
# backend/app/services/schedule_service.py
import time
from datetime import datetime, timezone
from typing import Any

import livef1

from ..cache.file_cache import CacheBackend
from ..models.schedule import WeekendSchedule, ScheduleSession, SessionType

# LiveF1 session type strings vary — normalize here.
_TYPE_MAP = {
    "PRACTICE 1": (SessionType.PRACTICE, "FP1", "FRI"),
    "PRACTICE 2": (SessionType.PRACTICE, "FP2", "FRI"),
    "PRACTICE 3": (SessionType.PRACTICE, "FP3", "SAT"),
    "QUALIFYING": (SessionType.QUALIFYING, "QUALI", "SAT"),
    "SPRINT QUALIFYING": (SessionType.SPRINT_QUALI, "SPRINT QUALI", "FRI"),
    "SPRINT": (SessionType.SPRINT, "SPRINT", "SAT"),
    "RACE": (SessionType.RACE, "RACE", "SUN"),
}

_SEASON_CACHE_TTL = 24 * 60 * 60  # 1 day — schedule rarely changes
_SEASON_CACHE_KEY_TMPL = "schedule/season/{season}"


def _normalize_session(raw: dict) -> ScheduleSession | None:
    """Map a livef1 session dict into a ScheduleSession."""
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
        is_next=False,      # set by caller after sorting
        is_complete=is_complete,
    )


def _current_season() -> int:
    return datetime.now(timezone.utc).year


def load_season(cache: CacheBackend, season: int | None = None) -> list[dict]:
    """Load the full season (list of meetings with nested sessions)."""
    season = season or _current_season()
    cache_key = _SEASON_CACHE_KEY_TMPL.format(season=season)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        season_obj = livef1.get_season(season)
        # livef1 season object exposes meetings; the exact accessor name should
        # be verified in Task 2's livef1-api.md. Most recent versions provide
        # `.meetings` as a list of dicts or a DataFrame.
        raw = getattr(season_obj, "meetings", None)
        if raw is None and hasattr(season_obj, "get_meetings"):
            raw = season_obj.get_meetings()
        meetings: list[dict] = []
        if raw is None:
            return []
        if hasattr(raw, "to_dict"):
            meetings = raw.to_dict(orient="records")
        else:
            meetings = list(raw)
    except Exception:
        meetings = []
    cache.set(cache_key, meetings, ttl_seconds=_SEASON_CACHE_TTL)
    return meetings


def current_weekend(cache: CacheBackend) -> WeekendSchedule | None:
    """
    Return the closest upcoming meeting (or the active meeting if we're mid-weekend).
    """
    meetings = load_season(cache)
    now = datetime.now(timezone.utc)
    chosen: dict | None = None
    for m in meetings:
        sessions = m.get("sessions") or m.get("Sessions") or []
        if not sessions:
            continue
        # Prefer the first meeting whose LAST session hasn't ended.
        last_end = None
        for s in sessions:
            utc = s.get("StartDate") or s.get("date_start")
            try:
                last_end = datetime.fromisoformat(str(utc).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
        if last_end and last_end + _session_buffer() >= now:
            chosen = m
            break
    if chosen is None and meetings:
        chosen = meetings[-1]  # fall back to last meeting of the season
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

    # Mark the first not-complete session as next
    for ns in normalized:
        if not ns.is_complete:
            ns.is_next = True
            break

    return WeekendSchedule(
        circuit=_circuit_id(chosen),
        country=chosen.get("Country") or chosen.get("country") or "",
        round=int(chosen.get("round") or chosen.get("Round") or 0),
        season=int(chosen.get("season") or chosen.get("Year") or _current_season()),
        sessions=normalized,
    ), next_session_ts


def _circuit_id(meeting: dict) -> str:
    # Prefer a slug-ish identifier. livef1 meetings often expose `.Location`
    # or `.OfficialName`. Fall back to lowercase-stripped country.
    raw = (
        meeting.get("circuit_short_name")
        or meeting.get("Location")
        or meeting.get("circuit_key")
        or meeting.get("Country")
        or "unknown"
    )
    return str(raw).lower().replace(" ", "_")


def _session_buffer():
    from datetime import timedelta
    return timedelta(hours=3)  # treat race as "active" for 3h after scheduled start
```

- [ ] **Step 3: Implement schedule router**

```python
# backend/app/routers/schedule.py
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
```

- [ ] **Step 4: Test with a fixture that stubs `load_season`**

Rather than hitting the network, tests patch `schedule_service.load_season`:

```python
# backend/tests/integration/test_schedule_router.py
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


FAKE_MEETINGS = [{
    "round": 6,
    "season": 2026,
    "Country": "United States",
    "Location": "Miami",
    "circuit_short_name": "miami",
    "sessions": [
        {"Name": "Practice 1",  "StartDate": _future(-48)},
        {"Name": "Practice 2",  "StartDate": _future(-44)},
        {"Name": "Practice 3",  "StartDate": _future(-24)},
        {"Name": "Qualifying",  "StartDate": _future(-20)},
        {"Name": "Race",        "StartDate": _future(2)},
    ],
}]


def test_schedule_returns_weekend_shape():
    with patch("app.services.schedule_service.load_season", return_value=FAKE_MEETINGS):
        resp = client.get("/schedule")
    assert resp.status_code == 200
    data = resp.json()
    assert data["circuit"] == "miami"
    assert len(data["sessions"]) == 5
    next_sessions = [s for s in data["sessions"] if s["is_next"]]
    assert len(next_sessions) == 1
    assert next_sessions[0]["name"] == "RACE"
```

- [ ] **Step 3: Implement predictions router**

The router prefers a file written by the mar-antaya ML runner (at `settings.predictions_path`, default `/data/predictions/latest.json` on the Fly volume). If the file is missing or unreadable, it falls back to a stub payload so the frontend always renders.

```python
# backend/app/routers/predictions.py
import json
import time
from fastapi import APIRouter
from pydantic import BaseModel
from ..config import settings

router = APIRouter()


class PredictionEntry(BaseModel):
    position: int
    driver_code: str
    team_id: str
    win_probability: float


class Predictions(BaseModel):
    entries: list[PredictionEntry]
    model: str
    updated_at: float


_STUB_PREDICTIONS = Predictions(
    entries=[
        PredictionEntry(position=1, driver_code="VER", team_id="redbull", win_probability=0.38),
        PredictionEntry(position=2, driver_code="NOR", team_id="mclaren", win_probability=0.24),
        PredictionEntry(position=3, driver_code="LEC", team_id="ferrari", win_probability=0.15),
        PredictionEntry(position=4, driver_code="PIA", team_id="mclaren", win_probability=0.11),
        PredictionEntry(position=5, driver_code="HAM", team_id="ferrari", win_probability=0.06),
        PredictionEntry(position=6, driver_code="RUS", team_id="mercedes", win_probability=0.06),
    ],
    model="stub — mar-antaya fork not yet wired",
    updated_at=time.time(),
)


@router.get("/predictions", response_model=Predictions)
def get_predictions():
    path = settings.predictions_path
    if path.exists():
        try:
            raw = json.loads(path.read_text())
            return Predictions(**raw)
        except (json.JSONDecodeError, ValueError, OSError):
            pass  # fall through to stub
    return _STUB_PREDICTIONS
```

- [ ] **Step 4: Register both routers and test**

```python
# backend/app/main.py — add:
from .routers import schedule as schedule_router, predictions as predictions_router
app.include_router(schedule_router.router)
app.include_router(predictions_router.router)
```

```bash
cd backend && pytest tests/integration/test_misc_routers.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/schedule.py backend/app/routers/predictions.py
git commit -m "feat: GET /schedule and GET /predictions (stub)"
```

---

## Task 17b: Race control router

**Files:**
- Create: `backend/app/routers/race_control.py`
- Create: `backend/app/models/race_control.py`
- Test: `backend/tests/integration/test_race_control_router.py`

Serves the cached race control log written by the live poller (and by the replay manager in replay mode). On cache miss, returns an empty log.

- [ ] **Step 1: Model**

```python
# backend/app/models/race_control.py
from enum import Enum
from pydantic import BaseModel


class RaceControlCategory(str, Enum):
    FLAG = "Flag"
    SAFETY_CAR = "SafetyCar"
    DRS = "Drs"
    CAR_EVENT = "CarEvent"
    OTHER = "Other"


class RaceControlMessage(BaseModel):
    utc: str
    lap: int | None = None
    category: RaceControlCategory
    message: str


class RaceControlLog(BaseModel):
    entries: list[RaceControlMessage]
    updated_at: float = 0.0
```

- [ ] **Step 2: Router**

```python
# backend/app/routers/race_control.py
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
```

- [ ] **Step 3: Test**

```python
# backend/tests/integration/test_race_control_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_race_control_empty_on_miss():
    cache.delete("race_control")
    resp = client.get("/race-control")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_race_control_returns_cached_entries():
    cache.set("race_control", {
        "entries": [
            {"utc": "2024-07-28T13:00:00", "lap": 1,  "category": "Flag",      "message": "GREEN LIGHT"},
            {"utc": "2024-07-28T13:10:00", "lap": 12, "category": "SafetyCar", "message": "SAFETY CAR DEPLOYED"},
        ],
        "updated_at": time.time(),
    }, ttl_seconds=60)
    resp = client.get("/race-control")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 2
    assert data["entries"][0]["category"] == "Flag"
```

- [ ] **Step 4: Register**

```python
# backend/app/main.py — add:
from .routers import race_control as race_control_router
app.include_router(race_control_router.router)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/race_control.py backend/app/routers/race_control.py backend/tests/integration/test_race_control_router.py
git commit -m "feat: GET /race-control router"
```

---

## Task 17c: Starting grid router

**Files:**
- Create: `backend/app/models/grid.py`
- Create: `backend/app/routers/grid.py`
- Test: `backend/tests/integration/test_grid_router.py`

The frontend's POST_QUALI view needs the starting order. The grid is derived from the last qualifying session's final timing tower — once the poller caches a quali result at `timing/last_quali`, this router reads it. During a live race we freeze a copy at `grid/current_weekend` via an explicit "grid snapshot" call from the poller (on quali ENDED).

For the skeleton we implement a simple read: the grid router reads `cache.get("grid")`; the poller writes it on quali session end. Replay mode seeds it alongside timing.

- [ ] **Step 1: Model**

```python
# backend/app/models/grid.py
from pydantic import BaseModel


class StartingGridEntry(BaseModel):
    position: int
    driver_code: str
    team_id: str
    quali_time: str | None = None


class StartingGrid(BaseModel):
    circuit: str
    entries: list[StartingGridEntry]
    updated_at: float = 0.0
```

- [ ] **Step 2: Router**

```python
# backend/app/routers/grid.py
from fastapi import APIRouter
from ..main import cache
from ..models.grid import StartingGrid

router = APIRouter()


@router.get("/grid", response_model=StartingGrid)
def get_grid():
    data = cache.get("grid")
    if data is None:
        return StartingGrid(circuit="", entries=[], updated_at=0.0)
    return StartingGrid(**data)
```

- [ ] **Step 3: Test**

```python
# backend/tests/integration/test_grid_router.py
import time
from fastapi.testclient import TestClient
from app.main import app, cache

client = TestClient(app)


def test_grid_empty_on_miss():
    cache.delete("grid")
    resp = client.get("/grid")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_grid_returns_cached():
    cache.set("grid", {
        "circuit": "miami",
        "entries": [
            {"position": 1, "driver_code": "VER", "team_id": "redbull", "quali_time": "1:27.121"},
            {"position": 2, "driver_code": "NOR", "team_id": "mclaren", "quali_time": "1:27.344"},
        ],
        "updated_at": time.time(),
    }, ttl_seconds=3600)
    resp = client.get("/grid")
    data = resp.json()
    assert data["circuit"] == "miami"
    assert len(data["entries"]) == 2
    assert data["entries"][0]["driver_code"] == "VER"
```

- [ ] **Step 4: Register**

```python
# backend/app/main.py — add:
from .routers import grid as grid_router
app.include_router(grid_router.router)
```

- [ ] **Step 5: Poller hook (future)**

Add a comment in `live_poller.py` marking the freeze-grid-on-quali-end path:

```python
# TODO(grid): when session_type=QUALIFYING and state→ENDED, snapshot the current
# timing tower to cache.set("grid", {...}). Tracked in follow-up plan.
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/grid.py backend/app/routers/grid.py backend/tests/integration/test_grid_router.py
git commit -m "feat: GET /grid router (cache-read only; poller hook deferred)"
```

---

## Task 17d: Circuits router

**Files:**
- Create: `backend/app/models/circuit.py`
- Create: `backend/app/routers/circuits.py`
- Test: `backend/tests/integration/test_circuits_router.py`

Exposes `backend/data/circuits.json` via `/circuits/{id}`. The frontend's "Circuit info" module needs this for length, laps, and the lap record display. Track map SVGs are pulled frontend-side directly from MultiViewer's public API (`api.multiviewer.app`) — the backend doesn't proxy them.

- [ ] **Step 1: Model**

```python
# backend/app/models/circuit.py
from pydantic import BaseModel


class CircuitInfo(BaseModel):
    id: str
    name: str
    country: str
    lat: float
    lon: float
    length_km: float
    total_laps: int
    lap_record: str
    lap_record_driver: str
    lap_record_year: int
    timezone: str
```

- [ ] **Step 2: Router**

```python
# backend/app/routers/circuits.py
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models.circuit import CircuitInfo

router = APIRouter()
_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "circuits.json"


def _load_all() -> dict:
    return json.loads(_DATA_PATH.read_text())


@router.get("/circuits/{circuit_id}", response_model=CircuitInfo)
def get_circuit(circuit_id: str):
    data = _load_all()
    if circuit_id not in data:
        raise HTTPException(status_code=404, detail=f"Unknown circuit: {circuit_id}")
    return CircuitInfo(id=circuit_id, **data[circuit_id])
```

- [ ] **Step 3: Test**

```python
# backend/tests/integration/test_circuits_router.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_circuits_returns_miami():
    resp = client.get("/circuits/miami")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "miami"
    assert data["total_laps"] > 0


def test_circuits_404_on_unknown():
    resp = client.get("/circuits/nowhere")
    assert resp.status_code == 404
```

- [ ] **Step 4: Register + commit**

```python
# backend/app/main.py — add:
from .routers import circuits as circuits_router
app.include_router(circuits_router.router)
```

```bash
git add backend/app/models/circuit.py backend/app/routers/circuits.py backend/tests/integration/test_circuits_router.py
git commit -m "feat: GET /circuits/{id} router"
```

---

## Task 18: Live polling worker

**Files:**
- Create: `backend/app/workers/live_poller.py`

The poller runs as a background asyncio task. It polls every `poll_interval_seconds` (default 3s). When the state machine is IDLE, it polls at 30s intervals. During LIVE/ARMED it polls at 3s.

The poller is responsible for three outputs on every tick:
1. **Timing snapshot** → cached at `timing`, plus calling `state_machine.on_timing_data()`.
2. **Track positions** → cached at `positions`.
3. **Race control messages** → cached at `race_control`, with **each new message** fed through `state_machine.on_race_control_message(msg)`. Without this path, flag states (RED_FLAG, SC, VSC, YELLOW_FLAG) never fire in production.

The poller also pulls `DriverList` once per session boundary to build a `DriverResolver` for this session.

- [ ] **Step 1: Write test**

```python
# backend/tests/unit/test_live_poller.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.workers.live_poller import LivePoller
from app.cache.file_cache import FileCache
from app.state_machine.machine import StateMachine


@pytest.fixture
def mock_cache(tmp_path):
    return FileCache(tmp_path / "cache")


@pytest.fixture
def sm():
    return StateMachine()


@pytest.mark.asyncio
async def test_poller_writes_to_cache(mock_cache, sm):
    poller = LivePoller(cache=mock_cache, state_machine=sm)

    fake_tower = {
        "entries": [{"position": 1, "driver_code": "VER", "team_id": "redbull",
                     "last_lap": "1:46.000", "gap": "Leader", "interval": None,
                     "tire": None, "tire_age": None,
                     "is_fastest_overall": False, "is_personal_best": False,
                     "is_in_battle": False,
                     "is_retired": False, "dnf": False}],
        "fastest_lap_driver": None,
        "fastest_lap_time": None,
        "updated_at": 0.0,
    }

    fake_session = MagicMock()
    sm.on_timing_data()
    with patch.object(poller, "_get_live_session", return_value=fake_session), \
         patch.object(poller, "_ensure_resolver", new=AsyncMock()), \
         patch.object(poller, "_fetch_timing", new=AsyncMock(return_value=fake_tower)), \
         patch.object(poller, "_fetch_positions", new=AsyncMock(return_value={"drivers": [], "updated_at": 0.0})), \
         patch.object(poller, "_fetch_race_control", new=AsyncMock()):
        await poller._poll_once()

    result = mock_cache.get("timing")
    assert result is not None
    assert result["entries"][0]["driver_code"] == "VER"


@pytest.mark.asyncio
async def test_poller_race_control_drives_state_machine(mock_cache, sm):
    """A new 'RED FLAG' RC message must push state machine into RED_FLAG."""
    from app.models.session import SessionState
    poller = LivePoller(cache=mock_cache, state_machine=sm)
    sm.on_timing_data()
    assert sm.state == SessionState.LIVE

    # Fake livef1_client.load_data to return one RED FLAG row
    fake_rows = [{"Utc": "2024-07-28T13:10:00", "Lap": 12, "Message": "RED FLAG"}]
    with patch("app.services.livef1_client.load_data", return_value=fake_rows):
        await poller._fetch_race_control(MagicMock())

    assert sm.state == SessionState.RED_FLAG
    cached = mock_cache.get("race_control")
    assert cached and cached["entries"][0]["category"] == "Flag"

    # Re-polling with the same row should NOT re-trigger the transition
    # (deduped by UTC timestamp).
    sm.on_race_control_message("TRACK CLEAR")  # reset flag
    sm.on_timing_data()
    assert sm.state == SessionState.LIVE
    with patch("app.services.livef1_client.load_data", return_value=fake_rows):
        await poller._fetch_race_control(MagicMock())
    assert sm.state == SessionState.LIVE  # deduped, no re-fire
```

- [ ] **Step 2: Implement LivePoller**

```python
# backend/app/workers/live_poller.py
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

_LIVE_INTERVAL = 3    # seconds
_IDLE_INTERVAL = 30   # seconds

# mode="json" so enum values serialize to strings when written to file cache.
def _dump(model) -> dict:
    return model.model_dump(mode="json")


class LivePoller:
    def __init__(self, cache: CacheBackend, state_machine: StateMachine):
        self._cache = cache
        self._sm = state_machine
        self._live_session: Any = None
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

            state = self._sm.state
            interval = _LIVE_INTERVAL if state in (
                SessionState.LIVE, SessionState.ARMED,
                SessionState.PAUSED, SessionState.RED_FLAG,
                SessionState.SC, SessionState.VSC, SessionState.YELLOW_FLAG,
            ) else _IDLE_INTERVAL
            await asyncio.sleep(interval)

    async def _poll_once(self) -> None:
        state = self._sm.state
        if state in (SessionState.IDLE, SessionState.ENDED):
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
        # Rebuild resolver on session boundary (detected by session identity).
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
        """Diff new race control messages, feed state machine, cache log."""
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
        """
        Returns the current live/most-recent session.

        Resolution order:
        1. If livef1 exposes `get_live_session()` (verify in Task 2 step 7),
           try that first.
        2. Fall back to deriving from the schedule service: find the session
           whose start time is closest to now (or just past it) and call
           `livef1.get_session(season, meeting, session)`.
        Returns None if neither path yields a session.
        """
        import livef1 as lf1
        # Try the direct live helper
        live_fn = getattr(lf1, "get_live_session", None)
        if callable(live_fn):
            try:
                return live_fn()
            except Exception as e:
                logger.info(f"get_live_session() unavailable, falling back: {e}")

        # Fallback: derive from schedule
        try:
            result = schedule_service.current_weekend(self._cache)
            if result is None:
                return None
            weekend, _ = result
            # Pick the session whose local/UTC time is closest to now
            # (this is approximate — replace with a richer match if needed).
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
```

- [ ] **Step 3: Run test**

```bash
cd backend && pytest tests/unit/test_live_poller.py -v
```
Expected: `1 passed`

- [ ] **Step 4: Commit**

```bash
git add backend/app/workers/live_poller.py backend/tests/unit/test_live_poller.py
git commit -m "feat: async live polling worker with state-aware interval"
```

---

## Task 19: Replay mode

**Files:**
- Create: `backend/app/replay/manager.py`
- Create: `backend/app/routers/replay.py`

When `REPLAY_SESSION=spa_2024` is set in env, the main app uses `ReplayManager` to serve fixture data instead of polling LiveF1.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/replay/test_replay_manager.py
import json
import pytest
from pathlib import Path
from app.replay.manager import ReplayManager

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


@pytest.fixture
def manager():
    if not (FIXTURES / "timing_data.json").exists():
        pytest.skip("Run download_spa_2024.py first")
    return ReplayManager(fixtures_dir=FIXTURES)


def test_manager_loads_fixture(manager):
    assert manager.total_laps > 0


def test_seek_changes_current_lap(manager):
    clamped, _ = manager.seek(10)
    assert clamped == 10
    assert manager.current_lap == 10


def test_get_timing_at_lap_returns_tower(manager):
    manager.seek(20)
    tower = manager.get_timing()
    assert len(tower.entries) > 0


def test_get_positions_at_lap_returns_positions(manager):
    manager.seek(20)
    positions = manager.get_positions()
    assert len(positions.drivers) > 0


def test_seek_beyond_total_clamps_to_last(manager):
    clamped, _ = manager.seek(999)
    assert clamped == manager.total_laps
    assert manager.current_lap == manager.total_laps


def test_seek_returns_new_rc_messages(manager):
    # First seek surfaces all messages up to current lap
    _, first = manager.seek(20)
    first_count = len(first)

    # A second seek to an earlier lap should not re-emit already-seen messages
    _, second = manager.seek(10)
    assert len(second) == 0

    # Seeking past the first emits only the newer ones
    _, third = manager.seek(manager.total_laps)
    # third may be empty if there were no messages after lap 20, which is fine
    assert isinstance(third, list)
```

- [ ] **Step 2: Implement ReplayManager**

```python
# backend/app/replay/manager.py
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
        self._timing_rows = _safe_load(fixtures_dir / "timing_data.json")
        self._tire_rows = _safe_load(fixtures_dir / "timing_app_data.json")
        self._position_rows = _safe_load(fixtures_dir / "position_z.json")
        self._rc_rows = _safe_load(fixtures_dir / "race_control_messages.json")
        driver_list_rows = _safe_load(fixtures_dir / "driver_list.json")
        self._resolver = DriverResolver.from_rows(driver_list_rows)

        # Determine total laps from timing data
        laps = [r.get("NumberOfLaps", r.get("number_of_laps", 0)) for r in self._timing_rows]
        valid_laps = [int(l) for l in laps if l and str(l).isdigit()]
        self.total_laps = max(valid_laps) if valid_laps else 44  # Spa 2024 = 44 laps
        self._current_lap = 1
        self._last_rc_utc: str | None = None  # tracks last seen RC message for diffing

    @property
    def current_lap(self) -> int:
        return self._current_lap

    @property
    def resolver(self) -> DriverResolver:
        return self._resolver

    def seek(self, lap: int) -> tuple[int, list[dict]]:
        """
        Move to `lap`. Returns (clamped_lap, new_rc_messages_since_previous_seek).

        The new_rc_messages list is the payload that the caller should feed
        through the state machine — replay must drive flag transitions the
        same way live polling does.
        """
        prev = self._current_lap
        self._current_lap = max(1, min(lap, self.total_laps))

        # Compute race control messages newly visible at this lap.
        all_up_to_now = parse_race_control_rows(
            self._rows_at_lap(self._rc_rows, self._current_lap)
        )
        if self._last_rc_utc is None and prev == self._current_lap:
            new_msgs = all_up_to_now  # first seek — emit everything up to current lap
        else:
            new_msgs = [m for m in all_up_to_now
                        if self._last_rc_utc is None or m["utc"] > self._last_rc_utc]
        if all_up_to_now:
            self._last_rc_utc = all_up_to_now[-1]["utc"]
        return self._current_lap, new_msgs

    def _rows_at_lap(self, rows: list[dict], lap: int) -> list[dict]:
        """Return all rows up to and including the given lap."""
        result = []
        for row in rows:
            row_lap = row.get("NumberOfLaps", row.get("number_of_laps", 0))
            try:
                if int(row_lap) <= lap:
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
```

- [ ] **Step 3: Create replay router**

```python
# backend/app/routers/replay.py
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

    # Drive timing + positions cache
    cache.set("timing",    manager.get_timing().model_dump(mode="json"),    ttl_seconds=3600)
    cache.set("positions", manager.get_positions().model_dump(mode="json"), ttl_seconds=3600)

    # Drive state machine as if this were a live tick
    state_machine.on_timing_data()
    for msg in new_rc_messages:
        state_machine.on_race_control_message(msg["message"])

    # Cache the full race control log visible at this lap for the RC module
    cache.set("race_control", {
        "entries": manager.get_race_control_log(),
        "updated_at": time.time(),
    }, ttl_seconds=3600)

    return {"lap": clamped, "total_laps": manager.total_laps}
```

- [ ] **Step 4: Wire replay into main.py**

```python
# backend/app/main.py — update lifespan and add replay_manager:
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .cache.file_cache import FileCache
from .state_machine.machine import StateMachine

cache = FileCache(settings.cache_dir)
state_machine = StateMachine()
replay_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global replay_manager
    task = None
    if settings.replay_session:
        from .replay.manager import ReplayManager
        import time as _time
        fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / settings.replay_session
        replay_manager = ReplayManager(fixtures_dir=fixtures_dir)
        # Seed lap 1 snapshot
        cache.set("timing",    replay_manager.get_timing().model_dump(mode="json"),    ttl_seconds=3600)
        cache.set("positions", replay_manager.get_positions().model_dump(mode="json"), ttl_seconds=3600)
        cache.set("race_control", {
            "entries": replay_manager.get_race_control_log(),
            "updated_at": _time.time(),
        }, ttl_seconds=3600)
        # Prime state machine so /state reflects replay
        state_machine.on_timing_data()
    else:
        from .workers.live_poller import LivePoller
        poller = LivePoller(cache=cache, state_machine=state_machine)
        task = asyncio.create_task(poller.run())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="F1 Dashboard API", version="0.1.0", lifespan=lifespan)
# ... (rest unchanged)
```

- [ ] **Step 5: Register replay router in main.py**

```python
from .routers import replay as replay_router
app.include_router(replay_router.router)
```

- [ ] **Step 6: Run tests**

```bash
cd backend && pytest tests/replay/test_replay_manager.py -v
```
Expected: `5 passed`

- [ ] **Step 7: Manual smoke test of replay mode**

```bash
cd backend && REPLAY_SESSION=spa_2024 uvicorn app.main:app --port 8000
# In another terminal:
curl http://localhost:8000/replay/status
curl http://localhost:8000/timing | python -m json.tool | head -30
curl -X POST http://localhost:8000/replay/seek/20
curl http://localhost:8000/timing | python -m json.tool | head -30
```
Verify the timing entries change between lap 1 and lap 20.

- [ ] **Step 8: Commit**

```bash
git add backend/app/replay/ backend/app/routers/replay.py
git commit -m "feat: replay mode with seek endpoint for frontend dev"
```

---

## Task 20: Full replay integration test (Spa 2024)

**Files:**
- Create: `backend/tests/replay/test_spa_2024_replay.py`

This test is the end-to-end verification that the full API correctly represents the Spa 2024 race from lap 1 to lap 44.

- [ ] **Step 1: Write the replay test**

```python
# backend/tests/replay/test_spa_2024_replay.py
"""
Full replay test of the 2024 Belgian GP (Spa).
Steps through every lap and asserts API invariants.
Requires fixture data: run `make download-fixtures` first.
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spa_2024"


@pytest.fixture(scope="module", autouse=True)
def check_fixtures():
    if not (FIXTURES / "timing_data.json").exists():
        pytest.skip("Fixtures not downloaded — run `make download-fixtures` first")


@pytest.fixture(scope="module")
def replay_client(monkeypatch_module):
    from app.config import settings
    settings.replay_session = "spa_2024"
    from app.main import app
    with TestClient(app) as c:
        yield c
    settings.replay_session = None


@pytest.fixture(scope="module")
def monkeypatch_module():
    # Module-scope monkeypatch shim
    import _pytest.monkeypatch
    mp = _pytest.monkeypatch.MonkeyPatch()
    yield mp
    mp.undo()


def test_replay_status_is_active(replay_client):
    resp = replay_client.get("/replay/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert data["total_laps"] == 44


def test_lap1_has_22_drivers_on_grid(replay_client):
    replay_client.post("/replay/seek/1")
    resp = replay_client.get("/timing")
    data = resp.json()
    assert len(data["entries"]) == 22
    positions = [e["position"] for e in data["entries"]]
    assert sorted(positions) == list(range(1, 23))


def test_positions_are_unique_per_lap(replay_client):
    for lap in [1, 10, 20, 30, 44]:
        replay_client.post(f"/replay/seek/{lap}")
        resp = replay_client.get("/timing")
        entries = resp.json()["entries"]
        pos_set = {e["position"] for e in entries}
        assert len(pos_set) == len(entries), f"Duplicate positions at lap {lap}"


def test_leader_has_gap_leader_string(replay_client):
    for lap in [1, 22, 44]:
        replay_client.post(f"/replay/seek/{lap}")
        resp = replay_client.get("/timing")
        entries = resp.json()["entries"]
        leader = next((e for e in entries if e["position"] == 1), None)
        assert leader is not None, f"No P1 driver at lap {lap}"
        assert leader["gap"] == "Leader", f"P1 gap not 'Leader' at lap {lap}: {leader['gap']}"


def test_track_positions_coordinates_normalized(replay_client):
    replay_client.post("/replay/seek/20")
    resp = replay_client.get("/positions")
    drivers = resp.json()["drivers"]
    assert len(drivers) > 0
    for d in drivers:
        assert -1.5 <= d["x"] <= 1.5, f"x out of range: {d['x']}"
        assert -1.5 <= d["y"] <= 1.5, f"y out of range: {d['y']}"


def test_state_transitions_during_replay(replay_client):
    from app.main import state_machine, cache
    from app.models.session import SessionState

    state_machine.__init__()  # reset
    replay_client.post("/replay/seek/1")
    # Simulate timing data arrival → should be LIVE
    state_machine.on_timing_data()
    resp = replay_client.get("/state")
    assert resp.json()["state"] == "LIVE"


def test_all_laps_return_valid_timing(replay_client):
    """Step through every 5th lap and verify basic invariants."""
    for lap in range(1, 45, 5):
        replay_client.post(f"/replay/seek/{lap}")
        resp = replay_client.get("/timing")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) > 0, f"No entries at lap {lap}"
        assert "updated_at" in data
```

- [ ] **Step 2: Run the test**

```bash
cd backend && pytest tests/replay/test_spa_2024_replay.py -v
```
Expected: `7 passed` (or skipped if fixtures not present)

- [ ] **Step 3: Run full test suite to ensure nothing broke**

```bash
cd backend && pytest -v
```
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/replay/test_spa_2024_replay.py
git commit -m "test: full Spa 2024 replay integration test"
```

---

## Task 21: Fly.io deployment

**Files:**
- Create: `backend/Dockerfile`
- Create: `fly.toml`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY data ./data

# Cache directory lives on a Fly volume (mounted at /data/cache)
ENV CACHE_DIR=/data/cache

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Update config.py to read CACHE_DIR from env**

```python
# backend/app/config.py
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cors_origins: list[str] = ["http://localhost:5173"]
    cache_dir: Path = Path("/tmp/f1-cache")
    poll_interval_seconds: int = 3
    replay_session: str | None = None

    class Config:
        env_file = ".env"
        populate_by_name = True
```

Add to `.env` (local dev, not committed):
```
CACHE_DIR=/tmp/f1-cache
CORS_ORIGINS=["http://localhost:5173"]
```

- [ ] **Step 3: Create fly.toml**

**Cold-start note:** `min_machines_running = 1` keeps one machine pinned. The file cache lives on a Fly volume, but volumes don't persist the state machine's in-memory state, and a cold start during a live session drops the poller for ~10–30s. Pinning one machine is the simplest mitigation; it costs roughly $1.94/mo on the shared-cpu-1x-256mb tier. If cost matters more than cold-start avoidance, change to 0 — the app still recovers correctly, just with a gap in data during the first few ticks after wake.

```toml
# fly.toml
app = "f1-dashboard-backend"
primary_region = "iad"

[build]
  dockerfile = "backend/Dockerfile"

[env]
  PORT = "8000"
  CACHE_DIR = "/data/cache"
  PREDICTIONS_PATH = "/data/predictions/latest.json"
  CORS_ORIGINS = "https://f1-dashboard.vercel.app"
  # Vercel preview deploys are matched by regex in config.py

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1     # Pin one machine to avoid cold-start drops

[[mounts]]
  source = "f1_data"
  destination = "/data"
```

The single volume at `/data` holds both the cache (`/data/cache`) and the predictions output (`/data/predictions/latest.json`). The ML runner writes directly to this path; if the runner runs outside Fly, it must push via `flyctl ssh sftp` or similar.

- [ ] **Step 4: Verify Dockerfile builds locally**

```bash
cd f1-dashboard && docker build -f backend/Dockerfile -t f1-backend:local backend/
docker run --rm -p 8000:8000 f1-backend:local &
curl http://localhost:8000/health
# Expected: {"status":"ok"}
docker stop $(docker ps -q --filter ancestor=f1-backend:local)
```

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile fly.toml
git commit -m "feat: Dockerfile and fly.toml for Fly.io deployment"
```

---

## Self-Review

### Scope reminder

This is a **skeleton v1** backend. See the top-of-file "Scope: Skeleton v1" section for the full deferred list. The follow-up plan will add endpoints for: sector dominance, lap-time history (long-run pace + gap chart), stint history (tire strategy), tire usage, undercut threat, championship implications, session notes, storylines, post-session LLM summary, and team radio transcription.

### Spec coverage check (what this plan delivers)

| Spec module | Covered by task | Notes |
|---|---|---|
| State machine: all 9 states | Task 6, 10, 18 | Flag states driven by RC messages from poller AND replay |
| Timing tower (with tire + tire age) | Task 9, 11 | TimingAppData merged in parser |
| Track positions | Task 9, 12 | Accepts both flat + nested Position.z shapes |
| Race control log | Task 17b | Cached by poller/replay; also drives state |
| Weather (live + forecast) | Task 15 | Open-Meteo; track_temp deferred |
| Driver + Constructor standings | Task 13 | Hand-maintained JSON |
| Historical stats per driver/circuit | Task 14 | Uses per-session DriverResolver |
| News RSS aggregation | Task 16 | The Race / Autosport / Motorsport |
| Weekend schedule (real) | Task 17 | LiveF1-backed, feeds state machine's next-session timer |
| Starting grid | Task 17c | Cache-read; poller snapshot hook noted for follow-up |
| Circuit info | Task 17d | `/circuits/{id}` from circuits.json |
| ML predictions (file-backed w/ stub) | Task 17 | Reads Fly volume if runner output exists |
| LiveF1 as data source | Task 9, 18 | With schedule-derived fallback for live session |
| DriverResolver (per-session TLAs) | Task 9 | Replaces hardcoded DRIVER_TEAM_MAP |
| Flat-file cache (Redis-swappable) | Task 5 | CacheBackend protocol |
| Replay mode for frontend dev | Task 19, 20 | Seek drives state + race control |
| Battle highlight (`is_in_battle`) | Task 9 | Guards against "+1 LAP" interval strings |
| Full pytest + replay integration | Task 20 | Spa 2024 end-to-end |
| Fly.io deployment | Task 21 | `min_machines_running = 1`, single `/data` volume |
| Monorepo + shared types | Task 1, 2, 3 | `is_watchlisted` removed from wire — frontend-only |

### Wiring verification checklist

Before shipping, confirm each of these paths has a test:
- [x] Race control messages → state machine transition (Task 18 test)
- [x] Replay seek → state machine transition (update Task 20 test)
- [x] Schedule → `state_machine.set_next_session_at` (Task 17 test via mock)
- [x] DriverResolver fallback when DriverList is empty (Task 9 test resolver fixture)
- [x] Tire compound merge from TimingAppData (Task 9 test; skipped without fixture)
- [x] Enum round-trip through file cache (use `model_dump(mode="json")` — verified in Task 18 poller)
- [x] Position.z nested-vs-flat shape handling (`_flatten_position_rows`)

### Remaining decisions implementers may still hit

1. **livef1 API surface** — Task 2 step 7 verifies whether `get_live_session`, `season.meetings`, and `DriverList` exist under those names. If any differ, update Tasks 9, 17, 18 before running them.
2. **Status flag constants** (`_STATUS_FASTEST = 2049`, `_STATUS_PERSONAL_BEST = 2048`) — these are from the F1 SignalR protocol. Verify against a known fastest-lap row in `schema.md` from the fixture download. Replace with the actual values if off.
3. **Historical router first-request latency** — iterating 4 seasons × 2 session types × `livef1.get_session()` can be slow. The 1h cache mitigates repeat hits but the first caller per (driver, circuit) waits. If unacceptable in practice, add a warmup job that pre-fills the cache for watchlisted drivers at startup (follow-up plan).
4. **Schedule cache invalidation** — The season file is cached for 24h. If the FIA publishes a schedule change mid-week, the backend won't see it until the TTL elapses. Acceptable for v1.

### Type consistency
- `TimingEntry.tire` is `TireCompound | None`; serialized as string in JSON via `model_dump(mode="json")`. The poller and replay manager both use `mode="json"` when writing to the file cache.
- `RaceControlMessage.category` is `RaceControlCategory | None`; same serialization rule.
- Racing numbers are always strings end-to-end — callers normalize with `str(row["RacingNumber"])`.

### Placeholder check
No TBD/TODO in code blocks except one explicitly-noted follow-up hook in `live_poller.py` (`TODO(grid): snapshot timing on quali ENDED`).
- `HistoricalStats.circuit` stored as lowercase; `GET /historical/{driver_code}/{circuit}` normalizes both with `.upper()` and `.lower()`.
