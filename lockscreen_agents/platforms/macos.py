"""Implementação para macOS (RASCUNHO, ainda não testado em um Mac).

Este arquivo é o ponto de partida do port. Tudo que está marcado com TODO(macos) precisa ser
verificado em um Mac de verdade; o que vem sem marca é a ideia mais provável, mas também não foi
executado. Leia docs/MACOS.md antes de mexer.

Dependências extras (só macOS): nenhuma obrigatória. Se precisar de PyObjC, acrescente em
requirements-macos.txt.
"""
import os
import subprocess
import sys
from pathlib import Path

from .base import Platform

APP_NAME = "LockscreenAgents"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / "com.lockscreen-agents.app.plist"


def _run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout


class MacPlatform(Platform):
    name = "macos"

    # TODO(macos): conferir os nomes reais dos processos com `ps -axo comm=` (Claude Desktop,
    # Codex e Cursor). Os nomes abaixo são palpites em minúsculas.
    PROCESS_NAMES = {"claude": {"claude"}, "codex": {"codex"}, "cursor": {"cursor"}}
    FOCUS_MATCH = {
        "claude": ({"claude"}, ("claude.app",)),
        "codex": ({"codex"}, ("codex.app", "openai.codex")),
        "cursor": ({"cursor"}, ("cursor.app",)),
    }

    def data_dir(self):
        return Path.home() / "Library" / "Application Support" / APP_NAME

    # ---- leitura do sistema
    def running_processes(self):
        names = set()
        for line in _run("ps", "-axo", "comm=").splitlines():
            names.add(os.path.basename(line.strip()).lower())
        return names

    def foreground_app_path(self):
        # TODO(macos): pode pedir permissão de Automação/Acessibilidade na primeira vez.
        script = ('tell application "System Events" to get POSIX path of '
                  "(file of first application process whose frontmost is true)")
        return _run("osascript", "-e", script).strip().lower()

    def idle_seconds(self):
        # HIDIdleTime vem em nanossegundos.
        for line in _run("ioreg", "-c", "IOHIDSystem").splitlines():
            if "HIDIdleTime" in line:
                return int(line.split("=")[-1].strip()) / 1e9
        return 0.0

    def session_locked(self):
        # TODO(macos): detectar tela bloqueada (ex.: CGSessionCopyCurrentDictionary, chave
        # "CGSSessionScreenIsLocked", via PyObjC/Quartz).
        return False

    # ---- ações
    def set_lock_screen(self, image_path):
        # TODO(macos): o macOS não tem API pública para trocar só a imagem da tela de bloqueio;
        # ela costuma mostrar o papel de parede. Opções em docs/MACOS.md.
        raise NotImplementedError("set_lock_screen ainda não foi portado para o macOS (veja docs/MACOS.md)")

    def lock_session(self):
        # TODO(macos): `pmset displaysleepnow` apaga a tela; para bloquear de fato, verificar a
        # opção "pedir senha imediatamente" ou CGSession -suspend nas versões que ainda têm.
        subprocess.run(["pmset", "displaysleepnow"], check=False)

    def open_path(self, path):
        subprocess.run(["open", str(path)], check=False)

    def system_language(self):
        out = _run("defaults", "read", "-g", "AppleLanguages")
        return "pt" if "pt" in out.lower().split(",")[0] else "en"

    def single_instance(self, name):
        import fcntl
        lock = self.data_dir() / f"{name}.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(lock, "w")  # mantém aberto enquanto o app roda
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    # ---- início automático (LaunchAgent)
    def autostart_is_enabled(self):
        return LAUNCH_AGENT.exists()

    def autostart_enable(self, command, icon=None):
        args = "".join(f"<string>{a}</string>" for a in command)
        LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
        LAUNCH_AGENT.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>'
            "<key>Label</key><string>com.lockscreen-agents.app</string>"
            f"<key>ProgramArguments</key><array>{args}</array>"
            "<key>RunAtLoad</key><true/>"
            "</dict></plist>\n", encoding="utf-8")
        return True

    def autostart_disable(self):
        LAUNCH_AGENT.unlink(missing_ok=True)

    # ---- janelas
    def ui_scale(self, root):
        # O Tk do macOS já trabalha em pontos; 1.0 evita janelas minúsculas. TODO(macos): conferir
        # em tela Retina e ajustar fontes.
        return 1.0

    def show_message(self, title, text):
        script = f'display dialog "{text}" with title "{title}" buttons {{"OK"}}'
        subprocess.run(["osascript", "-e", script], check=False)

    def stop_app_processes(self, patterns):
        stopped = []
        for pat in patterns:
            if subprocess.run(["pkill", "-f", pat], check=False).returncode == 0:
                stopped.append(pat)
        return stopped

    def python_gui(self):
        return sys.executable
