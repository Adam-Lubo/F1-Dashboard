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
                        is_in_battle=False,
                        is_retired=False, dnf=False),
            TimingEntry(position=1, driver_code="VER", team_id="redbull",
                        is_fastest_overall=False, is_personal_best=False,
                        is_in_battle=False,
                        is_retired=False, dnf=False),
        ],
        fastest_lap_driver=None,
        fastest_lap_time=None,
        updated_at=0.0,
    )
    assert tower.entries[0].position == 2
