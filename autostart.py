"""Início automático com o Windows: chave Run do registro + atalho na pasta Inicializar.

Dois caminhos de propósito: no logon de 16/11 o Windows ignorou a entrada do Run; com os dois,
o que funcionar sobe o app (o mutex do tray.py evita cópia dupla).
"""
import os
import subprocess
import sys
import winreg
from pathlib import Path

APP_NAME = "LockscreenAgents"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
INSTALLED_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME / "app"


def pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def app_dir():
    """Pasta do app instalado (ou a pasta atual, se estiver rodando direto do código-fonte)."""
    return INSTALLED_DIR if (INSTALLED_DIR / "tray.py").exists() else Path(__file__).resolve().parent


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


def enable(directory=None, python=None):
    directory = Path(directory or app_dir())
    python = Path(python or pythonw())
    tray = directory / "tray.py"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{python}" "{tray}"')
    lnk = startup_lnk()
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
          f"$s.TargetPath='{python}';$s.Arguments='\"{tray}\"';"
          f"$s.WorkingDirectory='{directory}';$s.WindowStyle=7;$s.Save()")
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
