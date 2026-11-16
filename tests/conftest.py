"""Preparação dos testes: configurações isoladas e um sistema operacional falso."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lockscreen_agents import detector, platforms, settings  # noqa: E402
from lockscreen_agents.platforms.base import Platform  # noqa: E402


class FakePlatform(Platform):
    """Sistema falso: os testes controlam processos, janela em foco e tempo parado."""
    name = "fake"
    PROCESS_NAMES = {"claude": {"claude.exe"}, "codex": {"codex.exe"}, "cursor": {"cursor.exe"}}
    FOCUS_MATCH = {"claude": ({"claude.exe"}, ()), "codex": ({"codex.exe"}, ()), "cursor": ({"cursor.exe"}, ())}

    def __init__(self, data_dir):
        self._dir = Path(data_dir)
        self.processes = set()
        self.foreground = ""
        self.idle = 0.0

    def data_dir(self):
        return self._dir

    def running_processes(self):
        return set(self.processes)

    def foreground_app_path(self):
        return self.foreground

    def idle_seconds(self):
        return self.idle


def _reset_settings_cache():
    settings._cache.update(cfg=None, mtime=None, at=0.0)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Cada teste usa um settings.json próprio (nunca mexe nas suas configurações de verdade)."""
    monkeypatch.setattr(settings, "OUT_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS", tmp_path / "settings.json")
    _reset_settings_cache()
    yield
    _reset_settings_cache()


@pytest.fixture
def fake_platform(tmp_path):
    previous = platforms._instance
    fake = FakePlatform(tmp_path)
    platforms.use(fake)
    yield fake
    platforms.use(previous)


@pytest.fixture
def clean_detector(monkeypatch):
    """Zera a memória do detector e deixa os testes escolherem a 'última atividade' em arquivos."""
    detector._last_seen.clear()
    detector._last_fg.clear()
    detector.LAST.clear()
    activity = {"claude": 0.0, "codex": 0.0, "cursor": 0.0}
    monkeypatch.setattr(detector, "SOURCES", {k: (lambda k=k: activity[k]) for k in activity})
    return activity
