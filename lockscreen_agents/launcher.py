"""Como o app chama a si mesmo (bandeja -> janela de configurações / protetor de tela).

Rodando do código-fonte, chama `python app.py --modo`. Empacotado em .exe (PyInstaller),
chama o próprio executável com `--modo`. Assim o mesmo código funciona nos dois casos.
"""
import sys
from pathlib import Path

from . import platforms

FROZEN = bool(getattr(sys, "frozen", False))


def command(mode=None, *extra, directory=None):
    """Lista de argumentos para iniciar o app. mode: None (bandeja), 'settings' ou 'saver'.
    `directory`: pasta com o app.py (só vale rodando do código-fonte; padrão = pasta do projeto)."""
    args = [f"--{mode}"] if mode else []
    args += list(extra)
    if FROZEN:
        return [sys.executable] + args
    script = Path(directory or Path(__file__).resolve().parent.parent) / "app.py"
    return [platforms.current().python_gui(), str(script)] + args
