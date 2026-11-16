"""Screensaver animado (.scr): mascotes do Claude Code, Codex e Cursor.

Quem está ativo anda (colorido); quem está ocioso fica parado em cinza.
Argumentos do Windows: /s (exibir), /c (configurar), /p <hwnd> (miniatura).
Extra para testes: --seconds N (fecha sozinho depois de N segundos).
"""
import math
import random
import sys
import time
import tkinter as tk
import traceback

from PIL import ImageTk

from . import platforms, settings
from .detector import get_states
from .i18n import t
from .render import ACCENT, BG, _gray, draw_claude, draw_codex, draw_cursor

FPS = 30
FRAME_MS = 1000 // FPS
STATUS_EVERY = 90  # quadros entre leituras de atividade (~3 s)
GRACE = 0.7        # segundos ignorando movimento do mouse logo ao abrir
MOVE_THRESHOLD = 12

# chave, rótulo, função de desenho, anda?
SPECS = [
    ("claude", "Claude Code",
     lambda size, step, blink: draw_claude(size, step=step, blink=blink, skin=settings.get()["skins"]["claude"]),
     True),
    ("codex", "Codex",
     lambda size, step, blink: draw_codex(size, step=step, blink=blink, skin=settings.get()["skins"]["codex"]),
     True),
    ("cursor", "Cursor",
     lambda size, step, blink: draw_cursor(size, skin=settings.get()["skins"]["cursor"]), False),
]


LOG = settings.OUT_DIR / "saver.log"


def _log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def hexcolor(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def set_dpi_aware():
    platforms.current().init_ui_process("LockscreenAgents.Saver")


class Actor:
    def __init__(self, scene, idx, count, spec):
        self.scene = scene
        self.key, self.label, self.draw, self.walks = spec
        self.label = t("tool." + self.key)
        c = scene.canvas
        lane_w = scene.w / count
        self.lane_l = scene.x0 + idx * lane_w
        self.lane_r = self.lane_l + lane_w
        self.cx = (self.lane_l + self.lane_r) / 2
        self.dir = random.choice((-1, 1))
        self.speed = scene.w * 0.0016 * random.uniform(0.85, 1.15)
        self.active = False
        self.closed = False  # ferramenta fechada: desenhada bem apagada
        self.cache = {}
        rest = self.sprite(False, None, False, False)
        self.half = rest.width() / 2
        self.shadow = c.create_oval(0, 0, 1, 1, fill="#1a1a1e", outline="")
        self.item = c.create_image(self.cx, scene.ground, anchor="s", image=rest)
        fs = -max(14, int(scene.h * 0.032))
        self.name_t = c.create_text((self.lane_l + self.lane_r) / 2, scene.ground + scene.h * 0.07,
                                    text=self.label, font=("Segoe UI", fs), fill="#5f5f64")
        self.state_t = c.create_text((self.lane_l + self.lane_r) / 2, scene.ground + scene.h * 0.115,
                                     text=t("state.open"), font=("Segoe UI", int(fs * 0.75)), fill="#46464b")

    def sprite(self, color, step, flip, blink):
        k = (color, step, flip, blink, self.closed)
        if k not in self.cache:
            if self.key == "cursor":  # ativo: cubo detalhado (step = nível do brilho, 0..5)
                img = draw_cursor(self.scene.size, active=color, glow=(step or 0) / 5,
                                   skin=settings.get()["skins"]["cursor"])
            else:
                img = self.draw(self.scene.size, step, blink)
            if flip:
                img = img.transpose(0)  # FLIP_LEFT_RIGHT
            if not color:
                img = _gray(img, dim=0.25, alpha=0.5) if self.closed else _gray(img)
            self.cache[k] = ImageTk.PhotoImage(img)
        return self.cache[k]

    def set_state(self, state):
        """state: 'working' (anda, colorido), 'open' (parado, cinza) ou 'closed' (bem apagado)."""
        active = state == "working"
        self.active = active
        self.closed = state == "closed"
        c = self.scene.canvas
        name_fill = "#ebebeb" if active else ("#5f5f64" if state == "open" else "#343438")
        idle_fill = "#46464b" if state == "open" else "#2d2d30"
        c.itemconfig(self.name_t, fill=name_fill)
        c.itemconfig(self.state_t,
                     text=t("state." + state) if state in ("working", "open", "closed") else "",
                     fill=hexcolor(ACCENT.get(self.key, (200, 200, 200))) if active else idle_fill)

    def tick(self, frame):
        c, s = self.scene.canvas, self.scene
        y = s.ground
        w = self.half * 2
        if self.active and self.walks:
            self.cx += self.dir * self.speed
            lo, hi = self.lane_l + self.half + 20, self.lane_r - self.half - 20
            if self.cx >= hi:
                self.cx, self.dir = hi, -1
            elif self.cx <= lo:
                self.cx, self.dir = lo, 1
            step = (frame // 7) % 2
            y -= max(2, s.size // 60) * step  # balanço a cada passo
            if self.key == "codex":
                blink = (frame // 15) % 2 == 1  # cursor piscando
            else:
                blink = (frame + hash(self.key)) % 170 in range(160, 166)
            img = self.sprite(True, step, self.dir < 0, blink)
        elif self.active:  # Cursor: flutua e o brilho pulsa
            wave = (math.sin(frame * 0.07) + 1) / 2
            y -= wave * s.size * 0.06
            img = self.sprite(True, int(wave * 5 + 0.5), False, False)
        else:
            img = self.sprite(False, None, False, False)
        c.itemconfig(self.item, image=img)
        c.coords(self.item, self.cx, y)
        lift = (s.ground - y) / max(1, s.size * 0.1)
        sw = w * (0.8 - 0.12 * min(1, lift))
        c.coords(self.shadow, self.cx - sw / 2, s.ground - 6, self.cx + sw / 2, s.ground + 8)


class Scene:
    def __init__(self, canvas, rect, origin):
        left, top, right, bottom = rect
        self.canvas = canvas
        self.x0, self.y0 = left - origin[0], top - origin[1]
        self.w, self.h = right - left, bottom - top
        self.size = int(min(self.w / 3 * 0.6, self.h * 0.42))
        self.ground = self.y0 + int(self.h * 0.60)
        canvas.create_line(self.x0, self.ground + 4, self.x0 + self.w, self.ground + 4, fill="#1d1d22")
        tools = settings.get()["tools"]
        specs = [sp for sp in SPECS if tools.get(sp[0], True)]
        self.actors = [Actor(self, i, len(specs), spec) for i, spec in enumerate(specs)]

    def apply_status(self, status):
        for a in self.actors:
            a.set_state(status.get(a.key, "open"))

    def tick(self, frame):
        for a in self.actors:
            a.tick(frame)


def run_saver(seconds=None):
    set_dpi_aware()
    root = tk.Tk()
    mons = platforms.current().monitors(root)
    vx = min(m[0] for m in mons)
    vy = min(m[1] for m in mons)
    vw = max(m[2] for m in mons) - vx
    vh = max(m[3] for m in mons) - vy

    def on_error(exc, val, tb):  # qualquer erro: registra e fecha (nunca deixa a tela presa)
        _log("erro: " + "".join(traceback.format_exception(exc, val, tb)))
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass

    root.report_callback_exception = on_error
    _log(f"iniciado /s seconds={seconds} frozen={getattr(sys, 'frozen', False)}")
    platforms.current().make_fullscreen(root, (vx, vy, vx + vw, vy + vh))
    root.configure(bg=hexcolor(BG), cursor="none")
    canvas = tk.Canvas(root, width=vw, height=vh, bg=hexcolor(BG), highlightthickness=0, cursor="none")
    canvas.pack(fill="both", expand=True)

    scenes = [Scene(canvas, m, (vx, vy)) for m in mons]
    state = {"frame": 0}
    started = time.time()
    start_pos = root.winfo_pointerxy()

    def refresh_status():
        try:
            status = get_states()
        except Exception:  # noqa: BLE001
            status = {}
        for s in scenes:
            s.apply_status(status)

    def loop():
        f = state["frame"]
        if f % STATUS_EVERY == 0:
            refresh_status()
        for s in scenes:
            s.tick(f)
        state["frame"] = f + 1
        if seconds is not None and time.time() - started > seconds:
            root.destroy()
            return
        root.after(FRAME_MS, loop)

    def quit_(_e=None):
        if time.time() - started > GRACE:
            root.destroy()

    def on_motion(_e):
        if time.time() - started < GRACE:
            return
        x, y = root.winfo_pointerxy()
        if abs(x - start_pos[0]) + abs(y - start_pos[1]) > MOVE_THRESHOLD:
            root.destroy()

    for ev in ("<Key>", "<ButtonPress>", "<MouseWheel>"):
        root.bind_all(ev, quit_)
    root.bind_all("<Motion>", on_motion)
    root.focus_force()
    loop()
    root.mainloop()


def main():
    args = [a.lower() for a in sys.argv[1:]]
    seconds = None
    if "--seconds" in args:
        seconds = float(args[args.index("--seconds") + 1])
    first = args[0] if args else "/s"
    if first.startswith("/p") or first.startswith("-p"):
        return  # miniatura nas configurações: não faz nada
    if first.startswith("/c") or first.startswith("-c"):
        platforms.current().show_message(
            "Lockscreen Agents",
            "Lockscreen Agents: sem opções de configuração.\n"
            "Quem está ativo (Claude Code, Codex, Cursor) anda; os ociosos ficam parados em cinza.")
        return
    run_saver(seconds)


if __name__ == "__main__":
    main()
