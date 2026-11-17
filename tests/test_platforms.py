"""Contrato das plataformas: todo sistema precisa implementar o que o app usa."""
import inspect
from pathlib import Path

import pytest

from lockscreen_agents.platforms import base
from lockscreen_agents.platforms.macos import MacPlatform


def _required_methods():
    """Métodos do contrato que não têm implementação padrão (levantam NotImplementedError)."""
    return [name for name, fn in inspect.getmembers(base.Platform, inspect.isfunction)
            if not name.startswith("_") and "raise NotImplementedError" in inspect.getsource(fn)]


def test_contract_is_not_empty():
    assert "idle_seconds" in _required_methods() and "set_lock_screen" in _required_methods()


def _missing(cls):
    return [m for m in _required_methods() if getattr(cls, m) is getattr(base.Platform, m)]


def test_macos_defines_every_method():
    assert _missing(MacPlatform) == []


def test_windows_defines_every_method():
    pytest.importorskip("winreg")  # só existe no Windows
    from lockscreen_agents.platforms.windows import WindowsPlatform
    assert _missing(WindowsPlatform) == []


def test_every_tool_has_process_names():
    for cls in (MacPlatform,):
        assert set(cls.PROCESS_NAMES) == {"claude", "codex", "cursor"}
        assert set(cls.FOCUS_MATCH) == {"claude", "codex", "cursor"}


def test_lock_screen_is_opt_in_only_where_it_touches_the_user_wallpaper():
    assert MacPlatform.LOCK_SCREEN_OPT_IN is True
    assert base.Platform.LOCK_SCREEN_OPT_IN is False
    assert base.Platform().restore_lock_screen() is False  # padrão: nada a desfazer
    assert base.Platform().has_pending_restore() is False


class _FakeDesktop:
    """Papel de parede em memória no lugar do osascript: os testes nunca mexem no seu de verdade."""

    def __init__(self, mac, current):
        self.current = list(current)  # um papel de parede por monitor
        mac._current_wallpapers = lambda: list(self.current)
        mac._set_wallpapers = self._set

    def _set(self, paths):
        # um item vale para todos os monitores; vários, um por monitor (como no osascript)
        self.current = [str(paths[0])] * len(self.current) if len(paths) == 1 else [str(p) for p in paths]


@pytest.fixture
def mac(tmp_path, monkeypatch):
    plat = MacPlatform()
    monkeypatch.setattr(plat, "data_dir", lambda: tmp_path)
    original = tmp_path.parent / "original.heic"
    original.write_text("x")
    plat.desktop = _FakeDesktop(plat, [str(original)])
    plat.original = str(original)
    return plat


def test_wallpaper_round_trip(mac, tmp_path):
    mac.set_lock_screen(tmp_path / "lock_0.png")
    assert mac.has_pending_restore() and mac.desktop.current == [str(tmp_path / "lock_0.png")]
    assert mac.restore_lock_screen() is True
    assert mac.desktop.current == [mac.original] and not mac.has_pending_restore()


def test_original_is_kept_across_several_swaps(mac, tmp_path):
    mac.set_lock_screen(tmp_path / "lock_0.png")
    mac.set_lock_screen(tmp_path / "lock_1.png")  # a segunda troca não pode guardar a imagem nossa
    mac.restore_lock_screen()
    assert mac.desktop.current == [mac.original]


def test_never_saves_our_own_image_as_the_original(mac, tmp_path):
    mac.desktop.current = [str(tmp_path / "lock_0.png")]  # sobrou de uma execução antiga, sem registro
    mac.set_lock_screen(tmp_path / "lock_1.png")
    assert not mac.has_pending_restore()
    assert mac.restore_lock_screen() is False  # sem original conhecido: não finge que restaurou


def test_restore_without_record_does_nothing(mac):
    assert mac.restore_lock_screen() is False and mac.desktop.current == [mac.original]


def test_restore_respects_a_wallpaper_the_user_chose_meanwhile(mac, tmp_path):
    mac.set_lock_screen(tmp_path / "lock_0.png")
    mac.desktop.current = ["/Users/x/new.jpg"]
    assert mac.restore_lock_screen() is False
    assert mac.desktop.current == ["/Users/x/new.jpg"] and not mac.has_pending_restore()


def test_restore_drops_the_record_when_the_original_file_is_gone(mac, tmp_path):
    mac.set_lock_screen(tmp_path / "lock_0.png")
    Path(mac.original).unlink()
    assert mac.restore_lock_screen() is False
    assert not mac.has_pending_restore()  # não fica tentando para sempre


def test_restore_fails_loudly_if_the_wallpaper_did_not_change(mac, tmp_path):
    mac.set_lock_screen(tmp_path / "lock_0.png")
    mac._set_wallpapers = lambda paths: None  # osascript "deu certo" mas nada mudou
    with pytest.raises(RuntimeError):
        mac.restore_lock_screen()
    assert mac.has_pending_restore()  # continua pendente para tentar de novo


def test_does_not_touch_the_wallpaper_if_the_current_one_cannot_be_read(mac, tmp_path):
    def denied():
        raise RuntimeError("osascript: not authorized")
    mac._current_wallpapers = denied
    with pytest.raises(RuntimeError):
        mac.set_lock_screen(tmp_path / "lock_0.png")
    assert mac.desktop.current == [mac.original] and not mac.has_pending_restore()


def test_each_monitor_gets_its_own_wallpaper_back(mac, tmp_path):
    second = tmp_path.parent / "second.heic"
    second.write_text("y")
    mac.desktop.current = [mac.original, str(second)]
    mac.set_lock_screen(tmp_path / "lock_0.png")
    assert mac.desktop.current == [str(tmp_path / "lock_0.png")] * 2
    assert mac.restore_lock_screen() is True
    assert mac.desktop.current == [mac.original, str(second)]


def test_restore_with_a_different_monitor_count_uses_the_main_wallpaper(mac, tmp_path):
    second = tmp_path.parent / "second.heic"
    second.write_text("y")
    mac.desktop.current = [mac.original, str(second)]
    mac.set_lock_screen(tmp_path / "lock_0.png")
    mac.desktop.current = [str(tmp_path / "lock_0.png")]  # um monitor foi desconectado
    assert mac.restore_lock_screen() is True
    assert mac.desktop.current == [mac.original]


def test_current_wallpapers_falls_back_to_finder(monkeypatch):
    from lockscreen_agents.platforms import macos
    calls = []

    def fake(script, timeout=10):
        calls.append(script)
        if "System Events" in script:
            raise RuntimeError("osascript: not authorized")
        return "/Users/x/a.heic\n"
    monkeypatch.setattr(macos, "_osascript", fake)
    assert MacPlatform()._current_wallpapers() == ["/Users/x/a.heic"] and len(calls) == 2


def test_current_wallpapers_raises_when_nothing_can_be_read(monkeypatch):
    from lockscreen_agents.platforms import macos
    monkeypatch.setattr(macos, "_osascript", lambda script, timeout=10: "\n")
    with pytest.raises(RuntimeError):
        MacPlatform()._current_wallpapers()


def test_osascript_failure_is_an_error_not_an_empty_answer(monkeypatch):
    from types import SimpleNamespace

    from lockscreen_agents.platforms import macos
    monkeypatch.setattr(macos.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="não autorizado"))
    with pytest.raises(RuntimeError):
        macos._osascript("x")


def test_autostart_plist_is_valid_with_special_characters_in_the_path(tmp_path, monkeypatch):
    import plistlib

    from lockscreen_agents.platforms import macos
    monkeypatch.setattr(macos, "LAUNCH_AGENT", tmp_path / "t.plist")
    cmd = ["/usr/bin/python3", "/Users/x/R&D <beta>/app.py", "--tray"]
    assert MacPlatform().autostart_enable(cmd) is True
    data = plistlib.loads((tmp_path / "t.plist").read_bytes())
    assert data["ProgramArguments"] == cmd and data["RunAtLoad"] is True


def test_applescript_text_escapes_quotes_and_backslashes():
    from lockscreen_agents.platforms.macos import _applescript_text
    assert _applescript_text('a "b" \\c') == 'a \\"b\\" \\\\c'


PMSET_PLAYING = """Assertion status system-wide:
   UserIsActive                   1
   PreventUserIdleDisplaySleep    1
   PreventUserIdleSystemSleep     1
"""
PMSET_IDLE = PMSET_PLAYING.replace("PreventUserIdleDisplaySleep    1", "PreventUserIdleDisplaySleep    0")
# caffeinate -i (só impede o sistema de dormir) não deve contar como vídeo
PMSET_SYSTEM_ONLY = PMSET_IDLE + "   NoIdleSleepAssertion           1\n"


@pytest.mark.parametrize("output,blocked", [(PMSET_PLAYING, True), (PMSET_IDLE, False),
                                             (PMSET_SYSTEM_ONLY, False), ("", False)])
def test_macos_detects_video_through_the_display_assertion(monkeypatch, output, blocked):
    from lockscreen_agents.platforms import macos
    monkeypatch.setattr(macos, "_run", lambda *a: output)
    assert MacPlatform().display_sleep_blocked() is blocked


def test_macos_pmset_failure_does_not_block_the_saver(monkeypatch):
    from lockscreen_agents.platforms import macos

    def boom(*a):
        raise OSError("sem pmset")
    monkeypatch.setattr(macos, "_run", boom)
    assert MacPlatform().display_sleep_blocked() is False


def test_default_platform_never_blocks_the_saver():
    assert base.Platform().display_sleep_blocked() is False
