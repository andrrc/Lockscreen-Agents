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
    # o Cursor ainda não tem visual de café
    cfg = settings.save({"skins": {"claude": "inexistente", "cursor": "coffee"}})
    assert cfg["skins"] == skins.defaults()


def test_update_merges_skins():
    settings.update(skins={"claude": "coffee"})
    assert settings.load()["skins"] == {"claude": "coffee", "codex": "default", "cursor": "default"}


def test_coffee_cup_changes_the_drawing():
    wrench = render.draw_claude(224, tool=True, skin="wrench")
    coffee = render.draw_claude(224, tool=True, skin="coffee")
    assert wrench.tobytes() != coffee.tobytes()


def test_codex_coffee_cup_changes_the_drawing():
    default = render.draw_codex(225, tool=True, skin="default")
    coffee = render.draw_codex(225, tool=True, skin="coffee")
    assert default.tobytes() != coffee.tobytes()
    idle = render.draw_codex(225, tool=False, skin="coffee")
    assert idle.tobytes() == default.tobytes()  # parado, sem xícara


def test_skin_only_shows_while_working():
    idle = render.draw_claude(224, tool=False, skin="coffee")
    assert idle.tobytes() == render.draw_claude(224, tool=False, skin="wrench").tobytes()


def test_lock_screen_uses_the_chosen_skin():
    status = {"claude": "working", "codex": "open", "cursor": "closed"}
    before = render.render(status)
    settings.update(skins={"claude": "coffee"})
    assert render.render(status).tobytes() != before.tobytes()
    working = {"claude": "open", "codex": "working", "cursor": "closed"}
    before = render.render(working)
    settings.update(skins={"codex": "coffee"})
    assert render.render(working).tobytes() != before.tobytes()


def test_santa_hat_changes_every_mascot_even_when_idle():
    makers = {
        "claude": lambda skin: render.draw_claude(224, tool=False, skin=skin),
        "codex": lambda skin: render.draw_codex(225, tool=False, skin=skin),
        "cursor": lambda skin: render.draw_cursor(224, active=False, skin=skin),
    }
    for tool, make in makers.items():
        hat = make("santa")
        assert hat.tobytes() != make(skins.default(tool)).tobytes()
        assert hat.height >= make(skins.default(tool)).height


def test_santa_hat_has_red_pixels():
    img = render.draw_cursor(300, active=True, skin="santa").convert("RGB")
    assert any(r > 180 and g < 80 and b < 80 for r, g, b in img.getdata())


def test_lock_screen_with_santa_hat_keeps_mascots_in_place():
    status = {"claude": "working", "codex": "working", "cursor": "working"}
    plain = render.render(status)
    settings.update(skins={"claude": "santa", "codex": "santa", "cursor": "santa"})
    hat = render.render(status)
    assert hat.tobytes() != plain.tobytes()
    # o texto embaixo dos mascotes (nomes e estados) não se mexe
    assert hat.crop((0, 700, 1920, 1080)).tobytes() == plain.crop((0, 700, 1920, 1080)).tobytes()


def test_claude_default_has_nothing_in_hand():
    assert skins.default("claude") == "default"
    nothing = render.draw_claude(224, tool=True)  # sem skin: o padrão
    assert nothing.tobytes() == render.draw_claude(224, tool=True, skin="default").tobytes()
    assert nothing.tobytes() != render.draw_claude(224, tool=True, skin="wrench").tobytes()
    # trabalhando ou não, o padrão é o mesmo desenho (não há acessório)
    assert nothing.tobytes() == render.draw_claude(224, tool=False).tobytes()


def test_claude_santa_has_no_wrench():
    hat = render.draw_claude(224, tool=True, skin="santa")
    assert hat.tobytes() == render.draw_claude(224, tool=False, skin="santa").tobytes()
