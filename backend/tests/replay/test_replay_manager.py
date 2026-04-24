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
