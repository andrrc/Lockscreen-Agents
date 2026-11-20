"""Modelo Placar e o histórico do dia que ele mostra."""
import json

from lockscreen_agents import history, render, scoreboard, settings, templates

ST = {"claude": "working", "codex": "open", "cursor": "closed", "gemini": "working"}


def test_history_adds_only_working_tools():
    history.add({"claude": "working", "codex": "open"}, 3)
    totals = history.add({"claude": "working", "codex": "working"}, 3)
    assert totals == {"claude": 6.0, "codex": 3.0}
    assert history.today() == totals


def test_history_ignores_long_gaps():
    assert history.add({"claude": "working"}, history.MAX_STEP + 1) == {}  # PC suspenso não conta
    assert history.add({"claude": "working"}, 0) == {}


def test_history_restarts_on_a_new_day():
    (settings.OUT_DIR / "history.json").write_text(json.dumps({"date": "2000-01-01", "seconds": {"claude": 99}}),
                                                   encoding="utf-8")
    assert history.today() == {}
    assert history.add({"claude": "working"}, 2) == {"claude": 2.0}


def test_history_survives_a_broken_file():
    (settings.OUT_DIR / "history.json").write_text("{nada", encoding="utf-8")
    assert history.today() == {}


def test_clock_format():
    assert scoreboard.clock(0) == "00:00"
    assert scoreboard.clock(3 * 3600 + 25 * 60 + 59) == "03:25"
    assert scoreboard.clock(500 * 3600) == "99:59"


def test_scoreboard_is_available_and_used_by_render():
    assert "scoreboard" in templates.available_ids()
    totals = {"claude": 600, "gemini": 60}
    board = scoreboard.render_board(ST, totals=totals)
    assert board.size == (1920, 1080)
    history.add({"claude": "working"}, 1)  # o render sem `totals` lê o histórico de hoje
    assert render.render(ST, template="scoreboard").size == (1920, 1080)


def test_board_changes_with_time_and_blink():
    a = scoreboard.render_board(ST, totals={"claude": 60})
    b = scoreboard.render_board(ST, totals={"claude": 120})
    off = scoreboard.render_board(ST, totals={"claude": 60}, colon=False)
    moved = scoreboard.render_board(ST, totals={"claude": 60}, phase=1)
    assert len({a.tobytes(), b.tobytes(), off.tobytes(), moved.tobytes()}) == 4


def test_disabled_tools_leave_the_board():
    four = scoreboard.render_board(ST, totals={})
    three = scoreboard.render_board({**ST, "cursor": "off"}, totals={})
    assert four.tobytes() != three.tobytes()
    assert scoreboard.layout(1920, 1080, 4)["w"] <= 1920
