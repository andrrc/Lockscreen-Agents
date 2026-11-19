"""Ícone na bandeja: monitora Claude Code, Codex, Cursor e Gemini CLI, atualiza a lock screen
e abre o protetor de tela animado quando o PC fica ocioso."""
import json
import os
import subprocess
import sys
import threading
import time
import traceback

import pystray

from . import detector, launcher, platforms, settings
from .detector import get_states
from .i18n import t
from .logo import mark
from .render import render

APP_NAME = settings.APP_NAME
OUT_DIR = settings.OUT_DIR
LOG = OUT_DIR / "log.txt"
POLL = 3  # segundos entre verificações
TOOLS = settings.TOOLS


def log(msg):
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 200_000:  # mantém o log pequeno
            LOG.write_text("", encoding="utf-8")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def single_instance():
    """Impede duas cópias rodando ao mesmo tempo."""
    return platforms.current().single_instance("LockscreenAgentsTray")


def idle_seconds():
    """Segundos desde o último teclado/mouse."""
    return platforms.current().idle_seconds()


def session_locked():
    """True se a tela está bloqueada (ou a sessão não é a ativa)."""
    return platforms.current().session_locked()


def write_status(states):
    """Grava o estado e os sinais da última leitura em status.json (a janela de configurações lê)."""
    try:
        tmp = OUT_DIR / "status.json.tmp"
        tmp.write_text(json.dumps({"updated": time.time(), "states": states, "signals": detector.LAST}),
                       encoding="utf-8")
        os.replace(tmp, OUT_DIR / "status.json")
    except OSError:
        pass


def make_icon(paused=False):
    return mark(64, paused)  # cadeado em pixel-art (cinza e apagado quando pausado)


class App:
    def __init__(self):
        self.paused = False
        self.cfg_key = None     # assinatura das configurações que mudam a imagem (ferramentas, idioma)
        self.status = {}
        self.last_key = None
        self.n = 0
        self.locked = False     # tela bloqueada na última leitura (só usado onde a imagem vale bloqueado)
        # Já trocamos o papel de parede (precisa restaurar). Começa pelo disco: se o app anterior
        # fechou ou caiu com a imagem nossa na tela, restaura assim que der.
        self.wallpaper_set = platforms.current().has_pending_restore()
        self.restore_lock = threading.Lock()  # menu e worker restauram de threads diferentes
        self.saver = None       # subprocess do protetor
        self.saver_auto = False  # aberto por ociosidade (True) ou teste manual (False)
        self.armed = True       # só reabre depois que o usuário voltar a usar o PC
        self.media_logged = False  # já avisamos no log que o protetor está adiado por causa de vídeo
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.icon = pystray.Icon(APP_NAME, make_icon(), "Lockscreen Agents", menu=self._menu())

    # ---- menu ----
    def _status_text(self, _item=None):
        if not self.status:
            return t("tray.waiting")
        sym = {"working": "●", "open": "○", "closed": "·"}  # em uso / aberto / fechado
        return "  ".join(f"{t('tool.' + k).split()[0]} {sym.get(self.status.get(k), '·')}"
                         for k in TOOLS if self.status.get(k) != "off")

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(self._status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _i: t("tray.settings"), self._open_settings, default=True),
            pystray.MenuItem(lambda _i: t("tray.pause"), self._toggle_pause, checked=lambda _i: self.paused),
            pystray.MenuItem(lambda _i: t("tray.refresh"), self._force),
            pystray.MenuItem(lambda _i: t("tray.restore"), self._restore_now,
                             visible=lambda _i: platforms.current().LOCK_SCREEN_OPT_IN),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _i: t("tray.test"), self._test_saver),
            pystray.MenuItem(lambda _i: t("tray.folder"), self._open_folder),
            pystray.MenuItem(lambda _i: t("tray.quit"), self._quit),
        )

    def _open_settings(self, _icon=None, _item=None):
        subprocess.Popen(launcher.command("settings"))  # a janela evita abrir duas vezes

    def _toggle_pause(self, icon, _item):
        self.paused = not self.paused
        icon.icon = make_icon(self.paused)
        if self.paused:
            self.restore()  # pausado não mexe mais no papel de parede: devolve o original agora
        log("pausado" if self.paused else "retomado")
        self.wake.set()

    def _test_saver(self, _icon, _item):
        if self.saver is None:
            self.start_saver(auto=False)

    def _force(self, _icon, _item):
        self.last_key = None
        self.wake.set()

    def _restore_now(self, _icon, _item):
        self.restore(force=True)
        self.last_key = None  # se ainda estiver bloqueado, a próxima leitura desenha de novo

    def _open_folder(self, _icon, _item):
        platforms.current().open_path(OUT_DIR)

    def _quit(self, icon, _item):
        self.stop.set()
        self.wake.set()
        if self.saver and self.saver.poll() is None:
            self.saver.terminate()
        self.restore()
        icon.stop()

    # ---- lock screen ----
    def apply(self, status):
        plat = platforms.current()
        if plat.LOCK_SCREEN_OPT_IN and not settings.get()["lock_wallpaper"]:
            return  # a plataforma só troca a imagem se o usuário ligar a opção
        if plat.LOCK_SCREEN_WHILE_LOCKED and not self.locked:
            return  # só troca com a tela bloqueada (ao desbloquear, restore() devolve o original)
        self.n += 1
        path = OUT_DIR / f"lock_{self.n % 2}.png"  # nome alternado: o Windows cacheia pelo caminho
        render(status).save(path)
        plat.set_lock_screen(path)
        self.wallpaper_set = True
        log(f"lock screen -> {status}")

    def restore(self, force=False):
        """Devolve o que a plataforma alterou (papel de parede no macOS). `force`: tenta mesmo
        sem lembrar de ter trocado (pedido manual)."""
        with self.restore_lock:
            if not (self.wallpaper_set or force):
                return
            try:
                done = platforms.current().restore_lock_screen()
            except Exception:  # noqa: BLE001
                log("erro ao restaurar: " + traceback.format_exc().replace("\n", " | "))
                return  # continua marcado: o worker tenta de novo
            self.wallpaper_set = False
            log("papel de parede restaurado" if done else "papel de parede: nada a restaurar")

    # ---- protetor de tela ----
    def start_saver(self, auto):
        self.saver = subprocess.Popen(launcher.command("saver", "/s"))
        self.saver_auto = auto
        log("protetor aberto (" + ("ociosidade" if auto else "teste") + ")")

    def saver_tick(self):
        if self.saver is not None:
            if self.saver.poll() is None:
                return  # ainda aberto
            log(f"protetor fechado (código {self.saver.returncode})")
            was_auto, self.saver = self.saver_auto, None
            self.armed = False  # só reabre depois que o usuário voltar a usar o PC
            if was_auto and settings.get()["lock_after"] and not session_locked():
                log("bloqueando o PC (opção ligada)")
                platforms.current().lock_session()
            return
        idle = idle_seconds()
        if idle < 10:
            self.armed = True
        cfg = settings.get()
        if (cfg["saver_on"] and self.armed and not self.paused
                and idle >= cfg["idle_min"] * 60 and not session_locked()):
            if cfg["saver_skip_media"] and platforms.current().display_sleep_blocked():
                if not self.media_logged:
                    log("protetor adiado: vídeo, chamada ou apresentação em andamento")
                    self.media_logged = True
                return
            self.media_logged = False
            self.start_saver(auto=True)

    # ---- trabalho em segundo plano ----
    def worker(self):
        while not self.stop.is_set():
            try:
                cfg = settings.get()
                if platforms.current().LOCK_SCREEN_WHILE_LOCKED:
                    locked = session_locked()
                    if locked != self.locked:
                        self.locked = locked
                        self.last_key = None  # bloqueou: desenha agora
                        if not locked:
                            self.restore()  # desbloqueou: devolve o papel de parede
                if self.wallpaper_set and (not cfg["lock_wallpaper"] or self.paused):
                    self.restore()  # o usuário desligou a opção (ou pausou)
                elif (self.wallpaper_set and platforms.current().LOCK_SCREEN_WHILE_LOCKED
                      and not self.locked):
                    self.restore()  # destrancado com a imagem nossa ainda na tela: tenta de novo
                key = (tuple(sorted(cfg["tools"].items())), cfg["lang"], tuple(sorted(cfg["skins"].items())),
                       cfg["lock_wallpaper"])
                if key != self.cfg_key:  # mudou ferramentas, idioma ou visual: redesenha a lock screen
                    self.cfg_key = key
                    self.last_key = None
                    self.icon.update_menu()
                if not self.paused:
                    status = get_states()
                    self.status = status
                    write_status(status)
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


def main():
    if not single_instance():
        log("já está aberto, esta cópia saiu")  # comum no logon: vários caminhos de início automático
        sys.exit(0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log("iniciado")
    App().run()
    log("encerrado")


if __name__ == "__main__":
    main()
