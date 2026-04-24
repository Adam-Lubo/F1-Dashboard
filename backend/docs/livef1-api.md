# livef1 API Surface

Findings from inspection of the installed `livef1` package.

## Top-level public names (relevant subset)

```
get_session, get_season, get_meeting, get_car_data_stream,
get_data, get_circuit_keys, Season, Meeting, Session,
LivetimingF1adapters, RealF1Client (via livef1.adapters),
LiveF1Error, TOPICS_MAP, SIGNALR_ENDPOINT
```

Full list:
```python
['BASE_URL', 'BasicResult', 'BeautifulSoup', 'CIRCUIT_KEYS_URL',
 'DEFAULT_METHOD', 'Dict', 'EXCLUDED_COLUMNS_FOR_SEARCH_SUGGESTION',
 'FIA_CATEGORY_SCOPE_RULES', 'List', 'LiveF1Error',
 'LivetimingF1adapters', 'Meeting', 'QUERY_STOPWORDS',
 'REALTIME_CALLBACK_DEFAULT_PARAMETERS', 'SESSIONS_COLUMN_MAP',
 'SIGNALR_ENDPOINT', 'SILVER_SESSION_TABLES', 'START_COORDINATES_URL',
 'STATIC_ENDPOINT', 'Season', 'Session', 'TABLE_GENERATION_FUNCTIONS',
 'TABLE_REQUIREMENTS', 'TOPICS_MAP', 'Union', 'adapters', 'api',
 'build_session_endpoint', 'get_car_data_stream', 'get_circuit_keys',
 'get_data', 'get_meeting', 'get_season', 'get_session', ...]
```

## get_session

```python
livef1.get_session(
    season: int,
    meeting_identifier: str = None,   # e.g. "spa", "Belgian", circuit short name
    session_identifier: str = None,   # e.g. "Race", "Qualifying", "Practice 1"
    meeting_key: int = None,
    session_key: int = None,
) -> livef1.models.session.Session
```

Example:
```python
session = livef1.get_session(2024, "spa", "Race")
```

## Session object

Key methods:
- `session.load_session_data()` — fetches topic names and driver list from livetiming API
- `session.get_data(dataName)` — fetch a topic (e.g. `"CarData.z"`, `"DriverList"`, `"TimingData"`)
- `session.get_data([...], parallel=True)` — fetch multiple topics in parallel
- `session.get_driver(identifier)` — returns a `Driver` object
- `session.drivers` — dict keyed by `RacingNumber` (populated after `load_session_data()`)
- `session.get_topic_names()` — list available data topics for the session
- `session.print_topic_names()` — pretty-print available topics
- `session.get_laps()` — processed lap data (silver table)
- `session.get_car_telemetry()` — processed telemetry (silver table)
- `session.load_session_results()` — scrape session results from f1.com

## Driver list access

Two ways:
1. `session.drivers` — dict after `load_session_data()`, keyed by racing number
2. `session.get_data("DriverList")` — raw topic data

## Live / real-time session helper

There is **no** `get_live_session`, `current_session`, or `live_session` function at the top level.

Live streaming is done via `livef1.adapters.RealF1Client` (also accessible as `livef1.adapters.realtime_client.RealF1Client`):

```python
from livef1.adapters.realtime_client import RealF1Client

client = RealF1Client(topics=["TimingData", "DriverList", "CarData.z"])
# client uses SignalR connection to wss://livetiming.formula1.com/signalr/
# async-based; register handlers and run event loop
```

`RealF1Client` connects to the F1 SignalR endpoint (`SIGNALR_ENDPOINT = "/signalr/"`) using an async SignalR client (bundled `signalr_aio`). It is callback-based.

## Key constants

- `BASE_URL` — F1 livetiming base URL
- `STATIC_ENDPOINT` — static data path
- `SIGNALR_ENDPOINT = "/signalr/"` — real-time endpoint
- `TOPICS_MAP` — mapping of topic names to internal keys

## Implications for this project

- Use `livef1.get_session(season, meeting_identifier, session_identifier)` to fetch historic/replay sessions.
- For live polling, use `RealF1Client` with a topic subscription list and async handlers.
- No built-in "current session" helper — must construct via `get_season` + latest meeting/session key.
- `session.drivers` (populated after `load_session_data()`) is the driver list; keyed by racing number.
