"""Contrato das plataformas: todo sistema precisa implementar o que o app usa."""
import inspect

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
