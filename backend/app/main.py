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
        try:
            from .workers.live_poller import LivePoller
            poller = LivePoller(cache=cache, state_machine=state_machine)
            task = asyncio.create_task(poller.run())
        except ImportError:
            pass  # live poller not yet implemented
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


@app.get("/health")
def health():
    return {"status": "ok"}
