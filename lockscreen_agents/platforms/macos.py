"""Implementação para macOS (funciona pelo código-fonte; ainda sem empacotamento em .app).

Tudo que está marcado com TODO(macos) ainda precisa ser verificado em um Mac de verdade. A coluna
Status de docs/MACOS.md diz o que já foi executado lá e o que só tem teste com saída simulada.
Leia docs/MACOS.md antes de mexer.

Dependências extras (só macOS): nenhuma obrigatória. Se precisar de PyObjC, acrescente em
requirements-macos.txt.
"""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .base import Platform

APP_NAME = "LockscreenAgents"
ORIGINAL_WALLPAPER = "original_wallpaper.txt"
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / "com.lockscreen-agents.app.plist"


def _run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout


def _applescript_text(value):
    """Texto seguro para ficar entre aspas dentro de um script AppleScript."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _osascript(script, timeout=10):
    """Roda o script e devolve a saída. Levanta RuntimeError se o osascript falhar (permissão
    negada, aplicativo sem resposta...), em vez de devolver um texto vazio que parece sucesso."""
    done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError("osascript: " + done.stderr.strip())
    return done.stdout


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

    FONTS = ("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc")

    # Sem API pública para trocar só a imagem da tela de bloqueio: ela mostra o papel de parede.
    # Por isso só mexemos nele se o usuário ligar "lock_wallpaper" (e guardamos o original).
    LOCK_SCREEN_OPT_IN = True
    LOCK_SCREEN_WHILE_LOCKED = True

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
        """O ioreg lista as sessões em IOConsoleUsers; a chave CGSSessionScreenIsLocked só existe
        enquanto a tela está bloqueada. Sem nenhuma sessão no console (troca de usuário), vale
        como bloqueado."""
        try:
            root = plistlib.loads(subprocess.run(["ioreg", "-n", "Root", "-d1", "-a"], capture_output=True,
                                                 timeout=10).stdout)
        except Exception:  # noqa: BLE001
            return False  # sem saber, não troca o papel de parede
        users = root.get("IOConsoleUsers") or []
        if not any(u.get("kCGSSessionOnConsoleKey") for u in users):
            return True
        return any(u.get("CGSSessionScreenIsLocked") for u in users)

    def display_sleep_blocked(self):
        """Navegadores e players seguram a asserção PreventUserIdleDisplaySleep enquanto tocam
        vídeo (chamadas e apresentações também); o próprio protetor do macOS a respeita."""
        try:
            out = _run("pmset", "-g", "assertions")
        except Exception:  # noqa: BLE001
            return False  # sem saber, o protetor abre normalmente
        for line in out.splitlines():
            name, _, count = line.strip().partition(" ")
            if name in ("PreventUserIdleDisplaySleep", "NoDisplaySleepAssertion") and count.strip() == "1":
                return True
        return False

    # ---- ações
    def _current_wallpapers(self):
        """Papel de parede de cada área de trabalho (uma por monitor/Space), na ordem do System
        Events. Se essa leitura não funcionar, cai no Finder, que só informa a principal (uma
        lista de um item: a troca então vale para todas, como antes). Levanta RuntimeError se
        nenhuma das duas leituras der um resultado: sem saber o original, não se troca nada."""
        script = ('tell application "System Events"\n'
                  'set out to ""\n'
                  "repeat with d in every desktop\n"
                  "set p to picture of d\n"
                  "if class of p is not text then set p to POSIX path of p\n"
                  "set out to out & p & linefeed\n"
                  "end repeat\n"
                  "return out\n"
                  "end tell")
        try:
            paths = [line.strip() for line in _osascript(script).splitlines() if line.strip()]
        except (RuntimeError, subprocess.TimeoutExpired):
            paths = []
        if not paths:
            script = 'tell application "Finder" to get POSIX path of (desktop picture as alias)'
            paths = [_osascript(script).strip()]
        if not all(paths):
            raise RuntimeError("não foi possível ler o papel de parede atual")
        return paths

    def _set_wallpapers(self, paths):
        """Uma imagem para todas as áreas de trabalho (`paths` com um item) ou uma por área."""
        if len(paths) == 1:
            script = ('tell application "System Events" to tell every desktop to set picture to '
                      f'POSIX file "{_applescript_text(paths[0])}"')
        else:
            sets = "\n".join(f'set picture of desktop {i} to POSIX file "{_applescript_text(p)}"'
                             for i, p in enumerate(paths, 1))
            script = f'tell application "System Events"\n{sets}\nend tell'
        _osascript(script, timeout=15)

    def _is_ours(self, path):
        """True se `path` é uma das imagens que o app gerou (ficam na pasta de dados)."""
        return bool(path) and Path(path).parent == self.data_dir()

    def has_pending_restore(self):
        return (self.data_dir() / ORIGINAL_WALLPAPER).exists()

    def set_lock_screen(self, image_path):
        """Troca o papel de parede (a tela de bloqueio do macOS mostra ele). Guarda o original
        (um caminho por linha, um por área de trabalho) uma vez só, para restore_lock_screen
        devolver; nunca guarda uma imagem nossa. Se não der para ler o atual, levanta erro e não
        troca nada: trocar sem ter o original guardado perderia o papel de parede do usuário."""
        saved = self.data_dir() / ORIGINAL_WALLPAPER
        if not saved.exists():
            current = self._current_wallpapers()
            if not any(self._is_ours(p) for p in current):
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_text("\n".join(current), encoding="utf-8")
        self._set_wallpapers([os.path.abspath(image_path)])

    def restore_lock_screen(self):
        """Devolve o papel de parede original. True se devolveu; False se não havia o que fazer
        (nada guardado, o usuário já trocou por outro, ou o arquivo original sumiu). Só levanta
        erro quando o osascript falha, para o chamador tentar de novo."""
        saved = self.data_dir() / ORIGINAL_WALLPAPER
        if not saved.exists():
            return False
        originals = [line.strip() for line in saved.read_text(encoding="utf-8").splitlines() if line.strip()]
        if (not originals or any(self._is_ours(p) for p in originals)
                or not all(Path(p).exists() for p in originals)):
            saved.unlink()  # registro inútil: tentar de novo nunca vai funcionar
            return False
        current = self._current_wallpapers()
        if not all(self._is_ours(p) for p in current):
            saved.unlink()  # o usuário escolheu outro papel de parede enquanto isso: respeita
            return False
        if len(originals) != len(current):
            originals = originals[:1]  # monitores conectados/desconectados: devolve o principal em todas
        self._set_wallpapers(originals)
        if any(self._is_ours(p) for p in self._current_wallpapers()):
            raise RuntimeError("o papel de parede continua o do app depois de restaurar")
        saved.unlink()
        return True

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
        LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
        # plistlib escapa &, < e > nos caminhos (montar o XML na mão quebrava com "R&D")
        LAUNCH_AGENT.write_bytes(plistlib.dumps({
            "Label": "com.lockscreen-agents.app",
            "ProgramArguments": [str(a) for a in command],
            "RunAtLoad": True,
        }))
        return True

    def autostart_disable(self):
        LAUNCH_AGENT.unlink(missing_ok=True)

    # ---- janelas
    def ui_scale(self, root):
        # O Tk do macOS já trabalha em pontos; 1.0 evita janelas minúsculas. TODO(macos): conferir
        # em tela Retina e ajustar fontes.
        return 1.0

    def make_fullscreen(self, root, rect):
        # Com o Tk do macOS, overrideredirect + geometry vira uma janela comum; -fullscreen cobre
        # a tela inteira (menu e Dock incluídos). Cobre só a tela principal.
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)

    def show_message(self, title, text):
        script = (f'display dialog "{_applescript_text(text)}" with title "{_applescript_text(title)}" '
                  'buttons {"OK"}')
        subprocess.run(["osascript", "-e", script], check=False)

    def stop_app_processes(self, patterns):
        stopped = []
        for pat in patterns:
            if subprocess.run(["pkill", "-f", pat], check=False).returncode == 0:
                stopped.append(pat)
        return stopped

    def python_gui(self):
        return sys.executable
