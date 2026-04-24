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
    return _load_json("timingdata.json")


@pytest.fixture
def position_rows():
    return _load_json("position_z.json")


@pytest.fixture
def driver_list_rows():
    path = FIXTURES / "driverlist.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


@pytest.fixture
def resolver(driver_list_rows):
    if not driver_list_rows:
        return DriverResolver(mapping={
            "1":  ("VER", "redbull"),
            "44": ("HAM", "mercedes"),
            "4":  ("NOR", "mclaren"),
        })
    return DriverResolver.from_rows(driver_list_rows)


def test_timing_snapshot_has_valid_entries(timing_rows, resolver):
    # Rows are sparse incremental updates; initial rows carry the full snapshot.
    # Use a window from the start where all 20 drivers have known positions.
    tower = parse_timing_snapshot(timing_rows[:50], resolver=resolver)
    assert 1 <= len(tower.entries) <= 22
    positions = [e.position for e in tower.entries]
    assert len(set(positions)) == len(positions)  # no duplicate positions


def test_timing_leader_gap_is_leader_string(timing_rows, resolver):
    # Use the same start-of-race window — Position data is present here.
    tower = parse_timing_snapshot(timing_rows[:50], resolver=resolver)
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


def test_classify_rc_messages():
    assert classify_rc_message("RED FLAG") == "Flag"
    assert classify_rc_message("SAFETY CAR DEPLOYED") == "SafetyCar"
    assert classify_rc_message("DRS ENABLED") == "Drs"
    assert classify_rc_message("CAR 1 UNDER INVESTIGATION") == "CarEvent"
    assert classify_rc_message("RESTART AT 14:00") == "Other"


def test_parse_race_control_rows():
    rows = [
        {"Utc": "2024-07-28T13:10:00", "Lap": 12, "Message": "RED FLAG", "Category": "Flag"},
        {"Utc": "2024-07-28T13:00:00", "Lap": 1,  "Message": "GREEN LIGHT - PIT EXIT OPEN", "Category": "Flag"},
    ]
    out = parse_race_control_rows(rows)
    assert len(out) == 2
    assert out[0]["utc"] < out[1]["utc"]
    assert out[1]["category"] == "Flag"
