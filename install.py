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
import winreg
from pathlib import Path

APP_NAME = "LockscreenAgents"
BASE = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
APP_DIR = BASE / "app"
FILES = ["detector.py", "lockscreen.py", "render.py", "saver.py", "tray.py"]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_lnk():
    return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / "Startup" / f"{APP_NAME}.lnk")


def pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    if not w.exists():
        raise SystemExit(f"pythonw.exe não encontrado ao lado de {exe}")
    return w


def stop_running():
    """Encerra instâncias anteriores do tray.py."""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\\.exe$' -and "
        "$_.CommandLine -match 'tray\\.py' } | ForEach-Object "
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

    cmd = f'"{pythonw()}" "{APP_DIR / "tray.py"}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
    print("Início automático ligado (HKCU\\...\\Run).")

    # Segundo caminho: atalho na pasta Inicializar. No logon de 16/11 o Windows ignorou a
    # entrada do Run; com os dois, o que funcionar sobe o app (o mutex evita cópia dupla).
    lnk = startup_lnk()
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
          f"$s.TargetPath='{pythonw()}';$s.Arguments='\"{APP_DIR / 'tray.py'}\"';"
          f"$s.WorkingDirectory='{APP_DIR}';$s.WindowStyle=7;$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    print(f"Atalho de inicialização: {lnk}" if lnk.exists() else "Não consegui criar o atalho de inicialização.")

    subprocess.Popen([str(pythonw()), str(APP_DIR / "tray.py")], cwd=APP_DIR,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    time.sleep(1)
    print("App iniciado. Procure o ícone do mascote perto do relógio.")


def uninstall():
    stop_running()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
        print("Início automático removido.")
    except FileNotFoundError:
        print("Início automático já estava desligado.")
    startup_lnk().unlink(missing_ok=True)
    print(f"Os arquivos continuam em {BASE} (apague a pasta se quiser).")


if __name__ == "__main__":
    uninstall() if "--uninstall" in sys.argv else install()
