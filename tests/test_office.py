"""Modelo Escritório: imagem da tela de bloqueio e peças animadas do protetor."""
from lockscreen_agents import office, render, settings, templates

ALL = {"claude": "working", "codex": "open", "cursor": "closed", "gemini": "working"}


def test_office_is_available_and_saved():
    assert "office" in templates.available_ids()
    assert settings.save({"template": "office"})["template"] == "office"


def test_render_uses_the_chosen_template():
    office_img = render.render(ALL, template="office")
    mascots_img = render.render(ALL, template="mascots")
    assert office_img.size == mascots_img.size == (1920, 1080)
    assert office_img.tobytes() != mascots_img.tobytes()
    settings.save({"template": "office"})
    assert render.render(ALL).tobytes() == office_img.tobytes()  # sem `template`, segue as configurações


def test_disabled_tools_get_no_desk():
    four = office.render_office(ALL)
    three = office.render_office({**ALL, "cursor": "off"})
    assert four.tobytes() != three.tobytes()
    assert office.layout(1920, 1080, 4)["slot"] * 4 <= 1920


def test_each_state_looks_different():
    u = office.layout(1920, 1080, 4)["u"]
    fronts = {st: office.desk_front("claude", st, u).tobytes() for st in ("working", "open", "closed")}
    assert len(set(fronts.values())) == 3
    assert office.mascot("claude", "closed", u) is None  # fechado: cadeira vazia
    assert office.mascot("claude", "working", u) is not None


def test_monitor_animates_while_working():
    u = office.layout(1920, 1080, 4)["u"]
    frames = {office.desk_front("codex", "working", u, phase).tobytes() for phase in range(office.CODE_PHASES)}
    assert len(frames) > 1
