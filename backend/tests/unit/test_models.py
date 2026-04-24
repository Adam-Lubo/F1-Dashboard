from app.models.session import SessionState, SessionInfo, SessionType
from app.models.timing import TimingEntry, TimingTower, TireCompound
from app.models.position import DriverPosition, TrackPositions
from app.models.weather import WeatherData
from app.models.standings import DriverStanding, ConstructorStanding
from app.models.historical import HistoricalStats
from app.models.news import NewsItem
from app.models.schedule import ScheduleSession, WeekendSchedule


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


def test_timing_tower_preserves_insertion_order():
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


def test_driver_position_defaults():
    pos = DriverPosition(driver_code="VER", team_id="redbull", x=0.5, y=-0.3)
    assert pos.driver_code == "VER"


def test_track_positions_empty():
    tp = TrackPositions(drivers=[])
    assert tp.drivers == []
    assert tp.updated_at == 0.0


def test_weather_data_defaults():
    w = WeatherData(air_temp=27.0, humidity=65.0, wind_speed=12.0,
                    rain_chance=10.0, description="Clear")
    assert w.is_live is False
    assert w.track_temp is None


def test_driver_standing():
    ds = DriverStanding(position=1, driver_code="VER", team_id="redbull",
                        points=127.0, wins=4)
    assert ds.points == 127.0


def test_constructor_standing():
    cs = ConstructorStanding(position=1, team_id="redbull",
                             team_name="Red Bull Racing", points=221.0, wins=4)
    assert cs.team_name == "Red Bull Racing"


def test_historical_stats_defaults():
    hs = HistoricalStats(driver_code="VER", circuit="spa")
    assert hs.races == 0
    assert hs.wins == 0
    assert hs.best_finish is None


def test_news_item():
    item = NewsItem(title="Test", url="https://example.com",
                    source="The Race", published_at="2026-04-20T10:00:00")
    assert item.summary is None


def test_weekend_schedule_cross_module_import():
    session = ScheduleSession(
        type=SessionType.RACE, name="RACE", day="SUN",
        local_time="15:00", utc_time="13:00",
    )
    ws = WeekendSchedule(
        circuit="spa", country="Belgium", round=13, season=2026,
        sessions=[session],
    )
    assert ws.sessions[0].type == SessionType.RACE
