"""Desenho da tela de bloqueio."""
from lockscreen_agents import render


def test_render_size_and_states():
    img = render.render({"claude": "working", "codex": "open", "cursor": "closed"})
    assert img.size == (1920, 1080)


def test_render_skips_disabled_tools():
    all_on = render.render({"claude": "working", "codex": "working", "cursor": "working"})
    two = render.render({"claude": "working", "codex": "working", "cursor": "off"})
    assert two.size == all_on.size
    assert two.tobytes() != all_on.tobytes()  # com um mascote a menos o desenho muda


def test_render_accepts_legacy_booleans():
    assert render.render({"claude": True, "codex": False, "cursor": False}).size == (1920, 1080)
