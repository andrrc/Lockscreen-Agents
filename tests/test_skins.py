"""Visuais (skins) dos mascotes."""
from lockscreen_agents import i18n, render, settings, skins


def test_every_skin_has_a_name_in_both_languages():
    for tool, options in skins.SKINS.items():
        for opt in options:
            for lang in ("pt", "en"):
                assert f"skin.{tool}.{opt['id']}" in i18n.STRINGS[lang]


def test_every_tool_has_a_default_skin():
    assert set(skins.defaults()) == set(settings.TOOLS)
    for tool in settings.TOOLS:
        assert skins.default(tool) in skins.available_ids(tool)


def test_settings_accept_available_skin():
    assert settings.save({"skins": {"claude": "coffee"}})["skins"]["claude"] == "coffee"


def test_settings_reject_unknown_skin():
    cfg = settings.save({"skins": {"claude": "inexistente", "codex": "coffee"}})
    assert cfg["skins"] == skins.defaults()


def test_update_merges_skins():
    settings.update(skins={"claude": "coffee"})
    assert settings.load()["skins"] == {"claude": "coffee", "codex": "default", "cursor": "default"}


def test_coffee_cup_changes_the_drawing():
    wrench = render.draw_claude(224, tool=True, skin="wrench")
    coffee = render.draw_claude(224, tool=True, skin="coffee")
    assert wrench.tobytes() != coffee.tobytes()


def test_skin_only_shows_while_working():
    idle = render.draw_claude(224, tool=False, skin="coffee")
    assert idle.tobytes() == render.draw_claude(224, tool=False, skin="wrench").tobytes()


def test_lock_screen_uses_the_chosen_skin():
    status = {"claude": "working", "codex": "open", "cursor": "closed"}
    before = render.render(status)
    settings.update(skins={"claude": "coffee"})
    assert render.render(status).tobytes() != before.tobytes()
