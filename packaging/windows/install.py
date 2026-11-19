"""Instala o Lockscreen Agents (a partir do código-fonte) numa pasta estável e liga o início
automático com o Windows. Quem usa o instalador .exe não precisa disto.

Uso (na raiz do projeto):
    python packaging/windows/install.py              instala, liga o autostart e inicia o app
    python packaging/windows/install.py --uninstall  remove o autostart e encerra o app
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if sys.platform != "win32":
    raise SystemExit("Este instalador é só para Windows. Para macOS veja docs/MACOS.md.")

from lockscreen_agents import autostart, launcher, platforms, settings  # noqa: E402

BASE = settings.OUT_DIR
APP_DIR = BASE / "app"
# arquivos soltos das versões antigas (antes do pacote lockscreen_agents/)
LEGACY = ["autostart.py", "detector.py", "i18n.py", "launcher.py", "lockscreen.py", "logo.py", "render.py",
          "saver.py", "settings.py", "settings_ui.py", "templates.py", "tray.py", "version.py", "logo.ico"]


def stop_running():
    """Encerra instâncias anteriores (bandeja, janela de configurações e protetor)."""
    for line in platforms.current().stop_app_processes([r"app\.py"]):
        print(line)


def install():
    stop_running()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    for name in LEGACY:
        (APP_DIR / name).unlink(missing_ok=True)
    shutil.copy2(ROOT / "app.py", APP_DIR / "app.py")
    dst = APP_DIR / "lockscreen_agents"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "lockscreen_agents", dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"Arquivos copiados para {APP_DIR}")

    # Três caminhos (tarefa agendada no logon, Run do registro e atalho em Inicializar): o Windows
    # ignorou o Run e a pasta Inicializar em vários logons; o mutex evita cópia dupla.
    ok = autostart.enable(APP_DIR)
    print("Início automático ligado (tarefa agendada, registro e pasta Inicializar)." if ok
          else "Início automático ligado só pelo registro (falhou a tarefa agendada e o atalho).")

    subprocess.Popen(launcher.command(directory=APP_DIR), cwd=APP_DIR,
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
