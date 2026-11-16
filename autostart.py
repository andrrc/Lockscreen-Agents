"""Início automático com o Windows: chave Run do registro + atalho na pasta Inicializar.

Dois caminhos de propósito: no logon de 16/11 o Windows ignorou a entrada do Run; com os dois,
o que funcionar sobe o app (o mutex do tray.py evita cópia dupla).
"""
import os
import subprocess
import winreg
from pathlib import Path

import launcher
import settings

APP_NAME = "LockscreenAgents"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
INSTALLED_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME / "app"


def app_dir():
    """Pasta do app instalado (ou a pasta atual, se estiver rodando direto do código-fonte)."""
    return INSTALLED_DIR if (INSTALLED_DIR / "app.py").exists() else Path(__file__).resolve().parent


def startup_lnk():
    return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / "Startup" / f"{APP_NAME}.lnk")


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return startup_lnk().exists()


def _quote(arg):
    return f'"{arg}"'


def enable(directory=None):
    """Liga o início automático. Empacotado em .exe, aponta para o próprio executável; do
    código-fonte, para o app.py instalado em `directory` (padrão: pasta do app instalado)."""
    cmd = launcher.command(directory=directory or app_dir())
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, " ".join(_quote(a) for a in cmd))
    icon = f"$s.IconLocation='{cmd[0]},0';" if launcher.FROZEN else ""
    if not launcher.FROZEN:
        try:  # ícone da logo no atalho
            import logo
            ico = settings.OUT_DIR / "logo.ico"
            settings.OUT_DIR.mkdir(parents=True, exist_ok=True)
            logo.save_ico(ico)
            icon = f"$s.IconLocation='{ico}';"
        except Exception:  # noqa: BLE001
            pass
    lnk = startup_lnk()
    args = " ".join(_quote(a) for a in cmd[1:])
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
          f"$s.TargetPath='{cmd[0]}';$s.Arguments='{args}';{icon}"
          f"$s.WorkingDirectory='{Path(cmd[0]).parent}';$s.WindowStyle=7;$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                   creationflags=0x08000000)  # CREATE_NO_WINDOW
    return lnk.exists()


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
    except FileNotFoundError:
        pass
    startup_lnk().unlink(missing_ok=True)
