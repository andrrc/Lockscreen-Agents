"""Configurações: validação, limites e gravação."""
import json

from lockscreen_agents import settings


def test_defaults_when_file_is_missing():
    cfg = settings.load()
    assert cfg["lang"] == "auto" and cfg["template"] == "mascots" and all(cfg["tools"].values())


def test_values_are_clamped():
    cfg = settings.save({"active_window": 5, "idle_min": 9999, "close_grace": "abc"})
    assert cfg["active_window"] == settings.LIMITS["active_window"][0]
    assert cfg["idle_min"] == settings.LIMITS["idle_min"][1]
    assert cfg["close_grace"] == settings.DEFAULTS["close_grace"]


def test_unavailable_template_falls_back():
    assert settings.save({"template": "minimal"})["template"] == "mascots"


def test_at_least_one_tool_stays_on():
    cfg = settings.save({"tools": {"claude": False, "codex": False, "cursor": False}})
    assert all(cfg["tools"].values())


def test_invalid_language_becomes_auto():
    assert settings.save({"lang": "xx"})["lang"] == "auto"


def test_update_merges_tools_and_persists():
    settings.update(tools={"cursor": False})
    cfg = json.loads(settings.SETTINGS.read_text(encoding="utf-8"))
    assert cfg["tools"] == {"claude": True, "codex": True, "cursor": False}


def test_corrupted_file_is_ignored():
    settings.SETTINGS.write_text("{ isto não é json", encoding="utf-8")
    assert settings.load() == settings._clean(None)


def test_reset_restores_defaults():
    settings.update(idle_min=30)
    assert settings.reset()["idle_min"] == settings.DEFAULTS["idle_min"]
