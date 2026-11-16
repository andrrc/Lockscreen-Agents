"""Ícone na bandeja: monitora Claude Code, Codex e Cursor, atualiza a lock screen
e abre o protetor de tela animado quando o PC fica ocioso."""
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import pystray
from PIL import Image

from detector import get_states
from lockscreen import set_lockscreen
from render import draw_claude, render

APP_NAME = "LockscreenAgents"
OUT_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
LOG = OUT_DIR / "log.txt"
SETTINGS = OUT_DIR / "settings.json"
POLL = 3  # segundos entre verificações
NAMES = {"claude": "Claude", "codex": "Codex", "cursor": "Cursor"}
IDLE_CHOICES = (1, 2, 5, 10, 15)  # minutos
DEFAULTS = {"saver_on": True, "idle_min": 5, "lock_after": False}


def log(msg):
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 200_000:  # mantém o log pequeno
            LOG.write_text("", encoding="utf-8")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def load_settings():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_settings(cfg):
    try:
        SETTINGS.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        log("não consegui salvar settings.json")


_mutex = None


def single_instance():
    """Impede duas cópias rodando ao mesmo tempo."""
    global _mutex
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\LockscreenAgentsTray")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds():
    """Segundos desde o último teclado/mouse."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    k32 = ctypes.windll.kernel32
    k32.GetTickCount.restype = ctypes.c_uint
    return ((k32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


def session_locked():
    """True se a área de trabalho de entrada não é a do usuário (tela bloqueada, UAC...)."""
    u = ctypes.windll.user32
    u.OpenInputDesktop.restype = ctypes.c_void_p
    u.CloseDesktop.argtypes = [ctypes.c_void_p]
    h = u.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not h:
        return True
    u.CloseDesktop(h)
    return False


def make_icon(paused=False):
    canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    crab = draw_claude(60, tool=False)
    if paused:
        crab = crab.convert("LA").convert("RGBA")
    canvas.paste(crab, ((64 - crab.width) // 2, (64 - crab.height) // 2), crab)
    return canvas


class App:
    def __init__(self):
        self.cfg = load_settings()
        self.paused = False
        self.status = {}
        self.last_key = None
        self.n = 0
        self.saver = None       # subprocess do protetor
        self.saver_auto = False  # aberto por ociosidade (True) ou teste manual (False)
        self.armed = True       # só reabre depois que o usuário voltar a usar o PC
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.icon = pystray.Icon(APP_NAME, make_icon(), "Lockscreen Agents", menu=self._menu())

    # ---- menu ----
    def _status_text(self, _item=None):
        if not self.status:
            return "Aguardando..."
        sym = {"working": "●", "open": "○", "closed": "·"}  # trabalhando / aberto / fechado
        return "  ".join(f"{NAMES[k]} {sym.get(self.status.get(k), '·')}" for k in NAMES)

    def _idle_item(self, minutes):
        def pick(_icon, _item):
            self.cfg["idle_min"] = minutes
            save_settings(self.cfg)
            log(f"protetor: ativar após {minutes} min")

        return pystray.MenuItem(
            f"{minutes} minuto" + ("s" if minutes > 1 else ""), pick,
            checked=lambda _i: self.cfg["idle_min"] == minutes, radio=True)

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pausar", self._toggle_pause, checked=lambda _i: self.paused),
            pystray.MenuItem("Atualizar lock screen agora", self._force),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Protetor de tela animado", self._toggle_saver,
                             checked=lambda _i: self.cfg["saver_on"]),
            pystray.MenuItem("Ativar após", pystray.Menu(*[self._idle_item(m) for m in IDLE_CHOICES])),
            pystray.MenuItem("Bloquear o PC ao fechar o protetor", self._toggle_lock_after,
                             checked=lambda _i: self.cfg["lock_after"]),
            pystray.MenuItem("Testar protetor agora", self._test_saver),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir pasta do app", self._open_folder),
            pystray.MenuItem("Sair", self._quit),
        )

    def _toggle_pause(self, icon, _item):
        self.paused = not self.paused
        icon.icon = make_icon(self.paused)
        log("pausado" if self.paused else "retomado")
        self.wake.set()

    def _toggle_saver(self, _icon, _item):
        self.cfg["saver_on"] = not self.cfg["saver_on"]
        save_settings(self.cfg)
        log(f"protetor {'ligado' if self.cfg['saver_on'] else 'desligado'}")

    def _toggle_lock_after(self, _icon, _item):
        self.cfg["lock_after"] = not self.cfg["lock_after"]
        save_settings(self.cfg)
        log(f"bloquear ao fechar protetor: {self.cfg['lock_after']}")

    def _test_saver(self, _icon, _item):
        if self.saver is None:
            self.start_saver(auto=False)

    def _force(self, _icon, _item):
        self.last_key = None
        self.wake.set()

    def _open_folder(self, _icon, _item):
        os.startfile(OUT_DIR)

    def _quit(self, icon, _item):
        self.stop.set()
        self.wake.set()
        if self.saver and self.saver.poll() is None:
            self.saver.terminate()
        icon.stop()

    # ---- lock screen ----
    def apply(self, status):
        self.n += 1
        path = OUT_DIR / f"lock_{self.n % 2}.png"  # nome alternado: o Windows cacheia pelo caminho
        render(status).save(path)
        set_lockscreen(path)
        log(f"lock screen -> {status}")

    # ---- protetor de tela ----
    def start_saver(self, auto):
        script = Path(__file__).with_name("saver.py")
        if not script.exists():
            log("saver.py não encontrado")
            return
        self.saver = subprocess.Popen([sys.executable, str(script), "/s"], cwd=str(script.parent))
        self.saver_auto = auto
        log("protetor aberto (" + ("ociosidade" if auto else "teste") + ")")

    def saver_tick(self):
        if self.saver is not None:
            if self.saver.poll() is None:
                return  # ainda aberto
            log(f"protetor fechado (código {self.saver.returncode})")
            was_auto, self.saver = self.saver_auto, None
            self.armed = False  # só reabre depois que o usuário voltar a usar o PC
            if was_auto and self.cfg["lock_after"] and not session_locked():
                log("bloqueando o PC (opção ligada)")
                ctypes.windll.user32.LockWorkStation()
            return
        idle = idle_seconds()
        if idle < 10:
            self.armed = True
        if (self.cfg["saver_on"] and self.armed and not self.paused
                and idle >= self.cfg["idle_min"] * 60 and not session_locked()):
            self.start_saver(auto=True)

    # ---- trabalho em segundo plano ----
    def worker(self):
        while not self.stop.is_set():
            try:
                if not self.paused:
                    status = get_states()
                    self.status = status
                    self.icon.title = "Lockscreen Agents — " + self._status_text()
                    self.icon.update_menu()
                    key = tuple(sorted(status.items()))
                    if key != self.last_key:
                        self.apply(status)
                        self.last_key = key
                self.saver_tick()
            except Exception:  # noqa: BLE001
                log("erro: " + traceback.format_exc().replace("\n", " | "))
                self.last_key = None  # tenta de novo no próximo ciclo
            self.wake.wait(POLL)
            self.wake.clear()

    def run(self):
        threading.Thread(target=self.worker, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    if not single_instance():
        sys.exit(0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log("iniciado")
    App().run()
    log("encerrado")
