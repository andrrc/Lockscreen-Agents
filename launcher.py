"""Como o app chama a si mesmo (bandeja -> janela de configurações / protetor de tela).

Rodando do código-fonte, chama `pythonw app.py --modo`. Empacotado em .exe (PyInstaller),
chama o próprio executável com `--modo`. Assim o mesmo código funciona nos dois casos.
"""
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def pythonw():
    """pythonw.exe (sem janela de console) ao lado do Python atual, se existir."""
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def command(mode=None, *extra, directory=None):
    """Lista de argumentos para iniciar o app. mode: None (bandeja), 'settings' ou 'saver'.
    `directory`: pasta com o app.py (só vale rodando do código-fonte; padrão = esta pasta)."""
    args = [f"--{mode}"] if mode else []
    args += list(extra)
    if FROZEN:
        return [sys.executable] + args
    script = Path(directory or Path(__file__).resolve().parent) / "app.py"
    return [str(pythonw()), str(script)] + args
