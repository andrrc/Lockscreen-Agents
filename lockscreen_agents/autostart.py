"""Início automático com o sistema. A implementação de cada sistema está em platforms/."""
from pathlib import Path

from . import launcher, platforms, settings

INSTALLED_DIR = settings.OUT_DIR / "app"
PROJECT_DIR = Path(__file__).resolve().parent.parent


def app_dir():
    """Pasta do app instalado (ou a do projeto, se estiver rodando direto do código-fonte)."""
    return INSTALLED_DIR if (INSTALLED_DIR / "app.py").exists() else PROJECT_DIR


def is_enabled():
    return platforms.current().autostart_is_enabled()


def enable(directory=None):
    """Liga o início automático. Empacotado em .exe, aponta para o próprio executável; do
    código-fonte, para o app.py instalado em `directory` (padrão: pasta do app instalado)."""
    cmd = launcher.command(directory=directory or app_dir())
    if launcher.FROZEN:
        icon = f"{cmd[0]},0"  # ícone embutido no executável
    else:
        icon = None
        try:  # ícone da logo no atalho
            from . import logo
            settings.OUT_DIR.mkdir(parents=True, exist_ok=True)
            ico = settings.OUT_DIR / "logo.ico"
            logo.save_ico(ico)
            icon = str(ico)
        except Exception:  # noqa: BLE001
            pass
    return platforms.current().autostart_enable(cmd, icon)


def disable():
    platforms.current().autostart_disable()
