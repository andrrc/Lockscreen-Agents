"""Instala o Lockscreen Agents numa pasta estável e liga o início automático com o Windows.

Uso:
    python install.py              instala, liga o autostart e inicia o app
    python install.py --uninstall  remove o autostart e encerra o app
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import autostart

APP_NAME = "LockscreenAgents"
BASE = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
APP_DIR = BASE / "app"
FILES = ["autostart.py", "detector.py", "i18n.py", "lockscreen.py", "logo.py", "render.py", "saver.py",
         "settings.py", "settings_ui.py", "templates.py", "tray.py"]


def pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    if not w.exists():
        raise SystemExit(f"pythonw.exe não encontrado ao lado de {exe}")
    return w


def stop_running():
    """Encerra instâncias anteriores (bandeja e janela de configurações)."""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\\.exe$' -and "
        "$_.CommandLine -match '(tray|settings_ui)\\.py' } | ForEach-Object "
        "{ Stop-Process -Id $_.ProcessId -Force; 'encerrado PID ' + $_.ProcessId }"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True).stdout.strip()
    if out:
        print(out)


def install():
    src = Path(__file__).resolve().parent
    stop_running()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(src / name, APP_DIR / name)
    print(f"Arquivos copiados para {APP_DIR}")

    # Dois caminhos (Run do registro + atalho em Inicializar): no logon de 16/11 o Windows ignorou
    # a entrada do Run; com os dois, o que funcionar sobe o app (o mutex evita cópia dupla).
    ok = autostart.enable(APP_DIR, pythonw())
    print("Início automático ligado (registro" + (" + pasta Inicializar)." if ok else ")."))

    subprocess.Popen([str(pythonw()), str(APP_DIR / "tray.py")], cwd=APP_DIR,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    time.sleep(1)
    print("App iniciado. Procure o ícone do cadeado perto do relógio; clique duas vezes para as configurações.")


def uninstall():
    stop_running()
    autostart.disable()
    print("Início automático removido.")
    print(f"Os arquivos continuam em {BASE} (apague a pasta se quiser).")


if __name__ == "__main__":
    uninstall() if "--uninstall" in sys.argv else install()
