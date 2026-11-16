"""Textos (português/inglês) e modelos: nada pode ficar sem tradução."""
import re

from lockscreen_agents import i18n, settings, templates


def test_both_languages_have_the_same_keys():
    pt, en = set(i18n.STRINGS["pt"]), set(i18n.STRINGS["en"])
    assert pt == en, f"faltam em en: {sorted(pt - en)} | faltam em pt: {sorted(en - pt)}"


def test_placeholders_match_between_languages():
    for key, pt_text in i18n.STRINGS["pt"].items():
        en_text = i18n.STRINGS["en"][key]
        assert set(re.findall(r"\{(\w+)\}", pt_text)) == set(re.findall(r"\{(\w+)\}", en_text)), key


def test_language_follows_settings():
    settings.update(lang="en")
    assert i18n.t("state.working") == "in use"
    settings.update(lang="pt")
    assert i18n.t("state.working") == "em uso"


def test_duration_formats():
    settings.update(lang="pt")
    assert i18n.duration(45) == "45 s"
    assert i18n.duration(180) == "3 min"
    assert i18n.duration(150) == "2 min 30 s"


def test_every_template_has_name_and_description():
    for tpl in templates.TEMPLATES:
        for lang in ("pt", "en"):
            assert f"tpl.{tpl['id']}.n" in i18n.STRINGS[lang]
            assert f"tpl.{tpl['id']}.d" in i18n.STRINGS[lang]


def test_default_template_is_available():
    assert templates.DEFAULT in templates.available_ids()
