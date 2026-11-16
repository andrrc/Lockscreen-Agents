"""Regras de detecção: em uso / ocioso / fechado / desligado."""
import time

from lockscreen_agents import detector, settings


def test_open_when_process_runs_without_activity(fake_platform, clean_detector):
    fake_platform.processes = {"claude.exe"}
    assert detector.get_states()["claude"] == "open"


def test_working_when_files_changed_recently(fake_platform, clean_detector):
    fake_platform.processes = {"claude.exe"}
    clean_detector["claude"] = time.time() - 5
    assert detector.get_states()["claude"] == "working"


def test_old_activity_is_only_open(fake_platform, clean_detector):
    fake_platform.processes = {"claude.exe"}
    clean_detector["claude"] = time.time() - 3600
    assert detector.get_states()["claude"] == "open"


def test_closed_without_process(fake_platform, clean_detector):
    assert detector.get_states() == {"claude": "closed", "codex": "closed", "cursor": "closed"}


def test_close_grace_keeps_open_for_a_while(fake_platform, clean_detector):
    fake_platform.processes = {"codex.exe"}
    assert detector.get_states()["codex"] == "open"
    fake_platform.processes = set()  # sumiu: ainda dentro da tolerância
    assert detector.get_states()["codex"] == "open"
    detector._last_seen["codex"] -= 1000  # passou da tolerância
    assert detector.get_states()["codex"] == "closed"


def test_focused_window_counts_as_working(fake_platform, clean_detector):
    fake_platform.processes = {"cursor.exe"}
    fake_platform.foreground = "c:\\apps\\cursor.exe"
    fake_platform.idle = 5
    assert detector.get_states()["cursor"] == "working"


def test_focus_ignored_when_user_is_away(fake_platform, clean_detector):
    fake_platform.processes = {"cursor.exe"}
    fake_platform.foreground = "c:\\apps\\cursor.exe"
    fake_platform.idle = 10_000
    assert detector.get_states()["cursor"] == "open"


def test_focus_can_be_turned_off(fake_platform, clean_detector):
    settings.update(follow_focus=False)
    fake_platform.processes = {"cursor.exe"}
    fake_platform.foreground = "c:\\apps\\cursor.exe"
    fake_platform.idle = 5
    assert detector.get_states()["cursor"] == "open"


def test_disabled_tool_is_off(fake_platform, clean_detector):
    settings.update(tools={"codex": False})
    states = detector.get_states()
    assert states["codex"] == "off" and states["claude"] != "off"


def test_signals_are_recorded(fake_platform, clean_detector):
    fake_platform.processes = {"claude.exe"}
    clean_detector["claude"] = time.time() - 10
    detector.get_states()
    sig = detector.LAST["claude"]
    assert sig["running"] is True and 5 < sig["file_age"] < 30 and sig["state"] == "working"
    assert detector.LAST["codex"]["running"] is False
