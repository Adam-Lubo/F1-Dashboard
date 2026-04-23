# F1 Dashboard — Design Spec

A Robinhood Legends–inspired, modular F1 race weekend dashboard. Personal / small-audience project. Desktop-first, dark-mode only.

---

## 1. Product overview

A single-page dashboard that adapts to the current F1 session state. Modules update in real time. Users can maintain a watchlist of favorite drivers and teams that get visually highlighted across all modules. No user accounts; preferences stored in localStorage.

### Core design principles

- Always visible persistent modules, with a dynamic center area that swaps based on session state
- Density scales with context: high density when nothing is happening (pre-weekend), tighter focus when racing
- Team livery colors and a single "watchlist gold" used as selective accents against a near-black background
- Monospace fonts for all numeric data
- F1 broadcast color conventions: purple for session-fastest, green for personal best

### Visual identity

A blend of Robinhood Legends (dark, Bloomberg-terminal feel, flat surfaces, minimal chrome) with FOM broadcast cues (F1 red accents, tire compound colors, timing tower conventions). Driver and team colors are the primary accent system.

---

## 2. State machine

The dashboard transitions between discrete states, driven primarily by the presence of timing data and secondarily by the F1 calendar.

| State | Trigger | Color | Behavior |
|---|---|---|---|
| IDLE | No session active, no recent data, and next session >15 min away | Blue hue | Pre-weekend view |
| ARMED | Within ~15 min of a scheduled session start (from OpenF1 `/sessions`) | Blue transitioning to green | "Market about to open" feeling. Notification sound fires once on entry. |
| LIVE | Timing data flowing — new lap times / position updates in last ~30 sec | Full green | Auto-switch to appropriate live view. Sound fires once on state entry. |
| PAUSED | Session live per schedule but no data updates in last ~60 sec | Dimmed green | Hold current view; display could mean red flag in between messages or practice lull |
| RED_FLAG | Explicit race control message | Red | Pulsing inset ring + pulsing top banner over current view |
| YELLOW_FLAG / SC / VSC | Explicit race control message | Amber | Less aggressive pulse; banner only |
| ENDED | Chequered flag received | Blue | Auto-switch to post-session view after ~5 min |

Session ordering, including sprint weekends, comes from OpenF1's `/sessions` endpoint rather than the user's personal Google Calendar, so friends visiting the site get the same experience.

### Notifications

- Sound enabled by default
- One distinct chime on ARMED→LIVE transition (session start)
- One chime on ENDED (chequered flag)
- Toggleable in header

---

## 3. Layout system

### Grid

Three-column grid across all states:

- **Left column (~260px):** contextual primary data — watchlist in IDLE, timing tower in LIVE states, starting grid in POST_QUALI
- **Center column (flex):** the defining module for the current state — ML predictions + historical in IDLE, track map + gap chart in LIVE race, sector dominance + long-run pace in practice
- **Right column (~240px):** persistent supporting info — weather, standings, watchlist summary, championship implications

### Persistent modules (visible across all or most states)

- Status bar (state pill, context, countdown/live metric)
- Weather (live when session is active, forecast otherwise)
- Drivers' standings (top 3 only)
- Constructors' standings (top 3 only, IDLE and practice only)
- Championship implications (always visible during race state, surfaced on red flag)
- Watchlist mini-cards

### Dynamic modules (state-specific)

| State | Center modules |
|---|---|
| IDLE | ML predictions (pre-weekend), historical at circuit, weekend schedule, news |
| PRACTICE | Session timing tower, sector dominance, long-run pace, tire usage this session, session notes |
| QUALI_LIVE | Q-stage timing tower (with Q1/Q2/Q3 indicator and knockout zone), sector dominance, track position, live improvements ticker |
| POST_QUALI / POST_SPRINT_QUALI | Starting grid, rerun ML predictions, news, weather, watchlist post-quali |
| RACE_LIVE / SPRINT_LIVE | Timing tower with battle highlights, track position (minisectors), gap-to-leader chart, tire strategy timeline, race control, pit window/undercut threat |

---

## 4. Module inventory (alphabetical reference)

- **Battle highlight** (in timing tower) — when two cars are within ~0.5s, their rows get enlarged with a red-tinted border and a "BATTLE FOR POLE/POSITION" strip between them. No separate card module.
- **Championship implications** — "if race/season ended now" live points calc; always visible during race state
- **Circuit info** — track map SVG (from MultiViewer public API), length, laps, lap record, DRS zones note
- **Constructors' standings** — top 3 with points
- **Drivers' standings** — top 3 with points
- **Gap to leader chart** — small line chart showing gap evolution over laps for top 3–5 drivers
- **Historical at circuit** — per watchlisted driver: best finish, avg quali/race, pole/win count
- **Incident card** — shown during red flag state; description, timestamps, ETA to resume
- **Live improvements ticker** — real-time callouts during hot laps (e.g., "NOR S2 fastest +0.051")
- **Long run pace** — multi-driver line chart of lap times on race fuel during practice
- **ML predictions** — win probability by driver, pulled from forked mar-antaya repo output
- **News feed** — RSS aggregation from The Race, Autosport, Motorsport.com, journalist blogs (no X/Twitter)
- **Pit window / undercut threat** — per watchlisted driver: tire age + lap time delta → "undercut in N laps" indicator
- **Post-session summary** (v2) — LLM-generated 3–4 sentence recap, fires on ENDED state
- **Race control** — timeline of race control messages
- **Sector dominance** — three cards for S1/S2/S3 showing fastest driver and runners-up deltas
- **Session notes** — mini race control for practice sessions
- **Session times** — practice timing tower (best lap, gap to P1, laps run)
- **Starting grid** — 2-column grid of P1–P20 with team color strips
- **Storylines** — curated pre-weekend narratives (IDLE only, manually curated or LLM-generated v2)
- **Team radio transcriptions** (v2) — Whisper transcription of OpenF1 team radio audio
- **Timing tower** — race timing tower with position, team color strip, driver, last lap, gap/interval, tire compound
- **Tire strategy timeline** — horizontal stacked bars showing stint history + projected current stint per watchlisted driver
- **Tire usage this session** — which compounds each driver has run in current practice
- **Track position** — SVG track map with driver dots at most recent minisector entry; updates every ~4 sec
- **Watchlist** (sidebar) — user's selected drivers with team color strip, role ("P1 '25", etc.)
- **Watchlist focus / summary** — contextual summary of watchlisted drivers for the current state (position, last lap, key stat)
- **Weather** — current conditions + race-window forecast; includes track temperature during live sessions
- **Weekend schedule** — 5-tile strip (FP1/FP2/FP3/Quali/Race) with local times

---

## 5. Watchlist system

### Data model

- Multiple drivers (no hard cap, reasonable soft limit ~5)
- Favorite team as a separate concept (all drivers on that team auto-highlight, but can be added/removed individually)
- Stored in localStorage only

### Visual treatment

- Gold accent: `#FFD700`
- 2px gold left border on watchlist rows
- Subtle gold-tinted background: `rgba(255, 215, 0, 0.04)`
- Gold ring around driver dot on track map
- Dedicated "watchlist focus" module in right column showing contextual summary per watchlisted driver

---

## 6. Color system

### Base palette

| Token | Value | Use |
|---|---|---|
| bg-0 | `#0a0a0a` | Outer canvas |
| bg-1 | `#141414` | Module cards |
| bg-2 | `#1a1a1a` | Nested elements (grid tiles, sub-cards) |
| border | `rgba(255,255,255,0.08)` | Default card border |
| text-primary | `#e8e8e8` | Main text |
| text-secondary | `#aaa` | Muted |
| text-tertiary | `#888` | Labels |
| text-quiet | `#666` | Least prominent |

### Semantic

| Token | Value | Use |
|---|---|---|
| watchlist | `#FFD700` | Gold accent |
| state-idle | `#378ADD` | Blue |
| state-live | `#97C459` | Green |
| fastest-overall | `#AFA9EC` | Purple (F1 broadcast convention) |
| personal-best | `#97C459` | Green (F1 broadcast convention) |
| flag-red | `#E24B4A` | Red flag |
| flag-yellow | `#EF9F27` | Yellow / SC / VSC |
| tire-soft | `#97C459` | |
| tire-medium | `#EF9F27` | |
| tire-hard | `#E24B4A` | Approximation |

### Team colors (2026 season — verify on setup)

Values come from official team liveries. Applied as 3px vertical strips next to driver codes.

---

## 7. Flag overlay system

### Red flag

- Inset pulsing ring on dashboard container, 1.6s cycle, `#E24B4A` with soft falloff
- Top banner pulses between `#E24B4A` and `#A32D2D`
- Center module swaps to incident card + race control log
- "If race ended now" championship module surfaces in right column

### Yellow flag / SC / VSC

- Top banner only, amber, less aggressive pulse
- No ring overlay (would be visually noisy given how frequent these are)
- Status bar dot turns amber

---

## 8. Data sources

| Source | Use | Notes |
|---|---|---|
| **OpenF1** (api.openf1.org) | Session schedule, timing, positions, race control, weather (live), car telemetry | Historical free; live tier is paid. Start with free tier + live minisectors via LiveF1 fallback if needed. |
| **LiveF1** (Python) | Direct F1 SignalR stream for live positions if not paying for OpenF1 live tier | `Position.z` and `CarData.z` topics. Unofficial. |
| **FastF1** (Python) | Historical session data, long-run analysis, sector times, post-session | Mandatory caching. |
| **MultiViewer** (api.multiviewer.app) | Public circuit SVGs for track map base | |
| **Open-Meteo** or **OpenWeatherMap** | Weather (non-live windows, forecasts) | Free tier sufficient. |
| **RSS feeds** | News — The Race, Autosport, Motorsport.com, journalist blogs | Curated list. No X/Twitter. |
| **Forked mar-antaya/2026_f1_predictions** | ML predictions pre-weekend and re-run post-quali | Self-hosted on cron. Requires model modification to accept quali results as input. |
| **Ergast** (if still alive) | Historical stats fallback | Being deprecated; don't build critical deps on it. |

### Caching

Mandatory. FastF1 requires local caching. OpenF1 requests should be cached per session. A Redis layer (or flat JSON files written by the backend) means frontend fetches our API, not upstream sources directly.

---

## 9. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vercel)                                          │
│  React + Vite, Tailwind, Recharts/D3, Zustand               │
│  - Polls backend every 2–5 sec during LIVE states           │
│  - Stores watchlist in localStorage                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────────┐
│  Backend (Fly.io or Railway)                                │
│  FastAPI                                                    │
│  - /state → current session state + state machine           │
│  - /timing, /positions, /weather, /news, /predictions       │
│  - /standings, /historical/:driver/:circuit                 │
└──────┬──────────────────────────┬────────────────────────┬──┘
       │                          │                        │
┌──────▼──────────┐  ┌────────────▼────────────┐  ┌───────▼──────┐
│  Redis cache    │  │  Python data workers    │  │  Static      │
│  (fly managed)  │  │  - FastF1 / LiveF1      │  │  RSS cache   │
│                 │  │  - OpenF1 polling       │  │  (file or    │
│                 │  │  - ML prediction runner │  │   Redis)     │
└─────────────────┘  └─────────────────────────┘  └──────────────┘
```

- **Frontend:** React + Vite + Tailwind on Vercel. Recharts for line charts, D3 for track map, Zustand for state.
- **Backend:** FastAPI on Fly.io or Railway. One service that exposes REST endpoints and runs scheduled workers (cron for ML runs, polling for live timing).
- **Cache:** Redis. Short TTLs (2–5 sec) for live data, long for news and schedule.
- **ML predictions:** Forked repo as a standalone worker. Runs on schedule. Outputs JSON to a known location (S3, Fly volume, or backend DB).
- **No auth, no DB of users.** Watchlist is localStorage. Optional future: lightweight SQLite for historical caching / server-side analytics.

---

## 10. Build order

1. **Monorepo setup.** Frontend (Vite + React + TS), backend (FastAPI + Python), shared types package. Commit hooks, CI for lints.
2. **Layout shell + state machine.** All five views render with mocked data. Persistent modules + state switching UI work end-to-end. Notification sounds. Flag overlays toggleable via dev controls.
3. **Live data wiring.** Point 1 backend to OpenF1 / FastF1 for a past race (e.g., use 2025 Abu Dhabi as a replay target). Frontend uses real past data to validate each live view.
4. **Schedule + news + weather.** Low-stakes feeds that unlock IDLE/POST states.
5. **ML predictions pipeline.** Fork the repo, dockerize, schedule, write outputs where backend can read them. Modify model to accept quali results.
6. **Module-by-module refinement.** Battle highlights, sector dominance, long-run pace, undercut threat, championship implications, historical-at-circuit.
7. **Live deploy test.** Stand up on Vercel + Fly during a real session. Fix everything that breaks.
8. **v2 backlog:** post-session LLM summary, team radio transcription.

---

## 11. Open decisions deferred to implementation

- Whether to upgrade to OpenF1 paid tier for live positions or stick with minisector approximation via LiveF1
- Whether to self-host the ML runner or use GitHub Actions cron
- Exact LLM for post-session summary (Haiku vs local Llama) — decide when reaching v2
- Whether "storylines" module is hand-curated or LLM-generated

---

## 12. Non-goals

- Mobile-optimized layout (desktop-first, mobile stacks naively)
- Light mode
- User accounts, auth, profiles
- Commercialization / monetization
- Covering F1 Academy, F2, F3, or historical seasons as first-class features
- Real-time onboard telemetry dashboards (speed/throttle/brake per driver) — available via FastF1 post-session but not in scope for live views
