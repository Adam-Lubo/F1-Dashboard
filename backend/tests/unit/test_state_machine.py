import time
import pytest
from app.state_machine.machine import StateMachine
from app.models.session import SessionState


def test_initial_state_is_idle():
    sm = StateMachine()
    assert sm.state == SessionState.IDLE


def test_arms_within_15_minutes_of_session():
    sm = StateMachine()
    now = time.time()
    sm.set_next_session_at(now + 14 * 60)  # 14 min away
    sm.tick(now)
    assert sm.state == SessionState.ARMED


def test_stays_idle_when_session_more_than_15_min_away():
    sm = StateMachine()
    now = time.time()
    sm.set_next_session_at(now + 20 * 60)
    sm.tick(now)
    assert sm.state == SessionState.IDLE


def test_transitions_to_live_on_timing_data():
    sm = StateMachine()
    now = time.time()
    sm.on_timing_data(at=now)
    assert sm.state == SessionState.LIVE


def test_pauses_after_60s_without_data():
    sm = StateMachine()
    now = time.time()
    sm.on_timing_data(at=now - 65)
    sm.tick(now)
    assert sm.state == SessionState.PAUSED


def test_resumes_live_when_data_returns_after_pause():
    sm = StateMachine()
    now = time.time()
    sm.on_timing_data(at=now - 65)
    sm.tick(now)
    assert sm.state == SessionState.PAUSED
    sm.on_timing_data(at=now)
    assert sm.state == SessionState.LIVE


def test_red_flag_on_race_control_message():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("RED FLAG")
    assert sm.state == SessionState.RED_FLAG


def test_vsc_on_race_control_message():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("VIRTUAL SAFETY CAR DEPLOYED")
    assert sm.state == SessionState.VSC


def test_sc_on_race_control_message():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("SAFETY CAR DEPLOYED")
    assert sm.state == SessionState.SC


def test_returns_to_live_on_track_clear():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("RED FLAG")
    assert sm.state == SessionState.RED_FLAG
    sm.on_race_control_message("TRACK CLEAR")
    sm.on_timing_data()
    assert sm.state == SessionState.LIVE


def test_ended_on_chequered_flag():
    sm = StateMachine()
    sm.on_timing_data()
    sm.on_race_control_message("CHEQUERED FLAG")
    assert sm.state == SessionState.ENDED
