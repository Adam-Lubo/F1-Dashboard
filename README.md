# F1 Dashboard

A personal F1 race weekend dashboard. Real-time timing tower, track positions, race control, weather, standings, and news — with a Robinhood Legends–inspired dark UI. Desktop-first, no accounts, no auth.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind v4 + Zustand + Recharts |
| Backend | FastAPI + Python 3.11 + Uvicorn |
| Live data | [livef1](https://github.com/theOehrly/Live-Timing) (F1 SignalR stream) |
| Historical | livef1 `get_session()` |
| Weather | Open-Meteo (free tier) |
| News | RSS — The Race / Autosport / Motorsport.com |
| Cache | Flat JSON files (no Redis, no DB) |
| Hosting | Fly.io (backend) + Vercel (frontend) |
| Shared types | `@f1-dashboard/shared-types` npm workspace package |

---

## Monorepo layout

```
f1-dashboard/
├── backend/                  # FastAPI app
│   ├── app/
│   │   ├── cache/            # FileCache + CacheBackend protocol
│   │   ├── models/           # Pydantic models
│   │   ├── replay/           # Spa 2024 replay harness
│   │   ├── routers/          # 13 REST endpoints
│   │   ├── services/         # livef1 client, weather, news, schedule
│   │   ├── state_machine/    # 9-state session FSM
│   │   ├── workers/          # live polling worker
│   │   ├── config.py
│   │   └── main.py
│   ├── data/
│   │   ├── standings.json    # hand-maintained (update after each race)
│   │   └── circuits.json
│   ├── tests/
│   │   ├── integration/
│   │   ├── replay/           # end-to-end Spa 2024 replay tests
│   │   └── unit/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                 # React + Vite scaffold
├── shared-types/             # TypeScript interfaces mirroring Pydantic models
├── fly.toml
├── Makefile
└── package.json              # npm workspaces root
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/state` | Session state + countdown + current lap |
| GET | `/timing` | Timing tower (20 drivers, lap times, gaps, tire) |
| GET | `/positions` | Track positions, normalized XY |
| GET | `/standings/drivers` | Driver standings (hand-maintained) |
| GET | `/standings/constructors` | Constructor standings (hand-maintained) |
| GET | `/historical/{driver}/{circuit}` | Best finish, avg quali/race, wins, poles |
| GET | `/weather/{circuit_id}` | Current conditions + forecast (Open-Meteo) |
| GET | `/news` | Latest headlines from F1 RSS feeds |
| GET | `/schedule` | Current weekend 5-session strip |
| GET | `/predictions` | ML win probabilities (reads from Fly volume; stub if absent) |
| GET | `/race-control` | Race control message log |
| GET | `/grid` | Starting grid (written by poller on quali end) |
| GET | `/circuits/{circuit_id}` | Circuit info (length, laps, lap record) |
| GET | `/replay/status` | Replay mode status |
| POST | `/replay/seek/{lap}` | Jump to a lap and update all caches |

---

## Session state machine

The backend tracks a 9-state session FSM driven by two inputs:

- **Timing data arriving** — `on_timing_data()` sets `LIVE` (unless a flag is active or session ended)
- **Race control messages** — `on_race_control_message(msg)` drives flag states

| State | Meaning |
|---|---|
| `IDLE` | No session, next session >15 min away |
| `ARMED` | Within 15 min of next scheduled session |
| `LIVE` | Timing data flowing |
| `PAUSED` | Live per schedule but no data for >60s |
| `RED_FLAG` | Red flag race control message |
| `YELLOW_FLAG` | Yellow flag |
| `SC` | Safety car deployed |
| `VSC` | Virtual safety car |
| `ENDED` | Chequered flag received |

---

## Local dev

### Prerequisites

- Python 3.11+
- Node 18+

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
npm install          # installs all workspaces
npm run dev:frontend
```

### Run tests

```bash
make test
# or directly:
cd backend && pytest -v -k "not test_historical_returns_model_shape"
```

The `test_historical_returns_model_shape` test requires a network call to livef1 and is excluded from the default run.

---

## Replay mode (frontend dev without a live race)

The replay harness loads the 2024 Belgian GP (Spa) fixture and lets you scrub through all 44 laps.

**Download fixtures (one-time, ~200 MB):**

```bash
make download-fixtures
# or:
cd backend && python tests/fixtures/download_spa_2024.py
```

**Start backend in replay mode:**

```bash
REPLAY_SESSION=spa_2024 uvicorn app.main:app --port 8000
```

**Seek to a lap:**

```bash
curl -X POST http://localhost:8000/replay/seek/20
curl http://localhost:8000/timing | python -m json.tool
```

All caches (`timing`, `positions`, `race_control`) are updated on each seek. The state machine is driven in replay mode exactly as it would be live — flag transitions fire when the race control log for that lap includes a red flag, safety car, etc.

---

## Deployment

The backend deploys to [Fly.io](https://fly.io). A single persistent volume at `/data` holds both the flat-file cache (`/data/cache`) and the ML predictions output (`/data/predictions/latest.json`).

```bash
fly deploy
```

`fly.toml` is at the repo root. `min_machines_running = 1` keeps one machine warm to avoid cold-start gaps during a live session.

The frontend deploys to Vercel. The backend's CORS config allows `https://f1-dashboard.vercel.app` and any `*.vercel.app` preview deploy URL.

---

## Configuration

Backend is configured via environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `CACHE_DIR` | `/tmp/f1-cache` | Directory for flat-file cache |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `POLL_INTERVAL_SECONDS` | `3` | Live poller interval (active sessions) |
| `REPLAY_SESSION` | `None` | Set to `spa_2024` to enable replay mode |
| `PREDICTIONS_PATH` | `/data/predictions/latest.json` | Path to ML runner output |

---

## Static data

`backend/data/standings.json` and `backend/data/circuits.json` are hand-maintained. Update `standings.json` after each race round. The circuits file currently includes Miami, Spa, and Monza — extend as needed.

---

## What's not built yet

These modules from the design spec are deferred to a follow-up plan:

- Sector dominance (S1/S2/S3 fastest per driver)
- Gap-to-leader chart (lap-by-lap gap series)
- Long run pace (lap time history during practice)
- Tire strategy timeline (stint history per driver)
- Pit window / undercut threat
- Championship implications ("if race ended now")
- ML predictions runner (the forked mar-antaya/2026_f1_predictions repo itself — this plan only reads its output file)
- Post-session LLM summary (v2)
- Team radio transcription (v2)
