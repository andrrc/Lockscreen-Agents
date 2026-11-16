"""Escolhe a implementação do sistema operacional atual.

    from .platforms import current
    current().idle_seconds()

Para portar para outro sistema, veja base.py e docs/MACOS.md.
"""
import sys
from pathlib import Path

from .base import Platform

_instance = None


class _Unsupported(Platform):
    """Sistema ainda sem port: deixa importar o app (para testes e CI), mas nada funciona."""
    name = "unsupported"

    def data_dir(self):
        return Path.home() / ".lockscreen-agents"


def current() -> Platform:
    global _instance
    if _instance is None:
        if sys.platform == "win32":
            from .windows import WindowsPlatform
            _instance = WindowsPlatform()
        elif sys.platform == "darwin":
            from .macos import MacPlatform
            _instance = MacPlatform()
        else:
            _instance = _Unsupported()
    return _instance


def use(platform: Platform) -> None:
    """Troca a implementação (usado nos testes, com um sistema falso)."""
    global _instance
    _instance = platform
