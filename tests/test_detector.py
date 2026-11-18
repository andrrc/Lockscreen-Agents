"""Regras de detecção: em uso / ocioso / fechado / desligado."""
import os
import time

from lockscreen_agents import detector, settings

CURSOR_PATH = os.path.join("apps", "cursor.exe")  # separador do sistema em que o teste roda


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
    assert detector.get_states() == {"claude": "closed", "codex": "closed", "cursor": "closed", "gemini": "closed"}


def test_close_grace_keeps_open_for_a_while(fake_platform, clean_detector):
    fake_platform.processes = {"codex.exe"}
    assert detector.get_states()["codex"] == "open"
    fake_platform.processes = set()  # sumiu: ainda dentro da tolerância
    assert detector.get_states()["codex"] == "open"
    detector._last_seen["codex"] -= 1000  # passou da tolerância
    assert detector.get_states()["codex"] == "closed"


def test_focused_window_counts_as_working(fake_platform, clean_detector):
    fake_platform.processes = {"cursor.exe"}
    fake_platform.foreground = CURSOR_PATH
    fake_platform.idle = 5
    assert detector.get_states()["cursor"] == "working"


def test_focus_ignored_when_user_is_away(fake_platform, clean_detector):
    fake_platform.processes = {"cursor.exe"}
    fake_platform.foreground = CURSOR_PATH
    fake_platform.idle = 10_000
    assert detector.get_states()["cursor"] == "open"


def test_focus_can_be_turned_off(fake_platform, clean_detector):
    settings.update(follow_focus=False)
    fake_platform.processes = {"cursor.exe"}
    fake_platform.foreground = CURSOR_PATH
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


def test_gemini_activity_reads_chats_and_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(detector, "HOME", tmp_path)
    assert detector.gemini_last_activity() == 0.0
    chats = tmp_path / ".gemini" / "tmp" / "abc123" / "chats"
    chats.mkdir(parents=True)
    session = chats / "session-2026-11-18T10-00-abc.json"
    session.write_text("{}", encoding="utf-8")
    os.utime(session, (1000, 1000))
    assert detector.gemini_last_activity() == 1000
    newer = chats / "session-novo.jsonl"  # formato das versões novas
    newer.write_text("", encoding="utf-8")
    os.utime(newer, (2000, 2000))
    assert detector.gemini_last_activity() == 2000
    logs = tmp_path / ".gemini" / "tmp" / "abc123" / "logs.json"
    logs.write_text("[]", encoding="utf-8")
    os.utime(logs, (3000, 3000))
    assert detector.gemini_last_activity() == 3000


def test_gemini_stays_open_after_recent_files_without_process(fake_platform, clean_detector):
    # o Gemini CLI roda no Node: sem processo próprio, os arquivos recentes dizem que está aberto
    clean_detector["gemini"] = time.time() - 600
    assert detector.get_states()["gemini"] == "open"
    clean_detector["gemini"] = time.time() - 5
    assert detector.get_states()["gemini"] == "working"


def test_gemini_closes_when_files_are_old(fake_platform, clean_detector):
    clean_detector["gemini"] = time.time() - 3 * 3600
    assert detector.get_states()["gemini"] == "closed"
