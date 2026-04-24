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

    fake_rows = [{"Utc": "2024-07-28T13:10:00", "Lap": 12, "Message": "RED FLAG"}]
    with patch("app.services.livef1_client.load_data", return_value=fake_rows):
        await poller._fetch_race_control(MagicMock())

    assert sm.state == SessionState.RED_FLAG
    cached = mock_cache.get("race_control")
    assert cached and cached["entries"][0]["category"] == "Flag"

    # Re-polling with the same row should NOT re-trigger the transition
    sm.on_race_control_message("TRACK CLEAR")  # reset flag
    sm.on_timing_data()
    assert sm.state == SessionState.LIVE
    with patch("app.services.livef1_client.load_data", return_value=fake_rows):
        await poller._fetch_race_control(MagicMock())
    assert sm.state == SessionState.LIVE  # deduped, no re-fire
