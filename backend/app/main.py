import asyncio
from contextlib import asynccontextmanager
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
        from pathlib import Path
        fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / settings.replay_session
        replay_manager = ReplayManager(fixtures_dir=fixtures_dir)
        cache.set("timing",    replay_manager.get_timing().model_dump(mode="json"),    ttl_seconds=3600)
        cache.set("positions", replay_manager.get_positions().model_dump(mode="json"), ttl_seconds=3600)
        cache.set("race_control", {
            "entries": replay_manager.get_race_control_log(),
            "updated_at": _time.time(),
        }, ttl_seconds=3600)
        state_machine.on_timing_data()
    else:
        from .workers.live_poller import LivePoller
        poller = LivePoller(cache=cache, state_machine=state_machine)
        task = asyncio.create_task(poller.run())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="F1 Dashboard API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


from .routers import (
    state as state_router,
    timing as timing_router,
    positions as positions_router,
    standings as standings_router,
    historical as historical_router,
    weather as weather_router,
    news as news_router,
    schedule as schedule_router,
    predictions as predictions_router,
    race_control as race_control_router,
    grid as grid_router,
    circuits as circuits_router,
)

app.include_router(state_router.router)
app.include_router(timing_router.router)
app.include_router(positions_router.router)
app.include_router(standings_router.router)
app.include_router(historical_router.router)
app.include_router(weather_router.router)
app.include_router(news_router.router)
app.include_router(schedule_router.router)
app.include_router(predictions_router.router)
app.include_router(race_control_router.router)
app.include_router(grid_router.router)
app.include_router(circuits_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
