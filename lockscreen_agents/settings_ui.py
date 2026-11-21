"""Janela de configurações do Lockscreen Agents.

Tkinter puro (sem dependências novas), mas com todos os controles desenhados à mão:
formas arredondadas com anti-aliasing (Pillow), animações com easing a ~60 fps, prévia
ao vivo da tela de bloqueio e barra de título escura do Windows 11.
Tudo é salvo na hora em settings.json; a bandeja percebe a mudança sozinha.

Uso: python settings_ui.py            abre a janela
     python settings_ui.py --shot DIR salva uma imagem de cada página (para testes)
"""
import itertools
import json
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from pathlib import Path
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageTk

from . import autostart, launcher, platforms, settings, skins, templates
from .i18n import duration, t
from .logo import logo
from .render import ACCENT as TOOL_ACCENT
from .render import draw_claude, draw_codex, draw_cursor, draw_gemini, render

# ------------------------------------------------------------------ tema
BG = (14, 14, 17)
SIDE = (18, 18, 22)
CARD = (23, 23, 28)
CARD_HOVER = (29, 29, 35)
BORDER = (38, 38, 46)
BORDER_HOVER = (54, 54, 64)
TEXT = (236, 236, 240)
MUTED = (139, 139, 148)
DIM = (88, 88, 96)
OFF = (58, 58, 66)
ACC = (217, 119, 87)
ACC_HOVER = (233, 140, 108)
GREEN = (92, 201, 140)
RED = (226, 96, 96)

W, H = 960, 640            # tamanho da janela (px lógicos)
SIDE_W = 236
CX = SIDE_W + 44           # início do conteúdo
CW = W - CX - 44           # largura do conteúdo
CARD_H = 92
SS = 4                     # supersampling dos desenhos
S = 1.0                    # escala de DPI (definida ao abrir a janela)

LOG = settings.OUT_DIR / "settings_ui.log"
REPO_URL = "https://github.com/andrrc/Lockscreen-Agents"


def px(v):
    return int(round(v * S))


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def mix(a, b, k):
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def q(k, steps=10):
    """Quantiza 0..1 para reaproveitar imagens em cache."""
    return round(max(0.0, min(1.0, k)) * steps) / steps


def out_cubic(p):
    return 1 - (1 - p) ** 3


def out_quint(p):
    return 1 - (1 - p) ** 5


def in_out(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def log(msg):
    try:
        settings.OUT_DIR.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 100_000:
            LOG.write_text("", encoding="utf-8")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


# ------------------------------------------------------------------ desenho (Pillow -> Tk)
_cache = {}


def _photo(key, make):
    if key not in _cache:
        _cache[key] = ImageTk.PhotoImage(make())
    return _cache[key]


def rrect(w, h, r, fill, outline=None, bw=1):
    """Retângulo arredondado com anti-aliasing (w, h, r já em pixels reais)."""
    w, h = max(1, w), max(1, h)

    def make():
        edge = outline or fill
        big = Image.new("RGBA", (w * SS, h * SS), edge + (0,))
        d = ImageDraw.Draw(big)
        d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=r * SS, fill=edge + (255,))
        if outline:
            b = bw * SS
            d.rounded_rectangle([b, b, w * SS - 1 - b, h * SS - 1 - b],
                                radius=max(0, r - bw) * SS, fill=fill + (255,))
        return big.resize((w, h), Image.LANCZOS)

    return _photo(("rr", w, h, r, fill, outline, bw), make)


def circle(d, fill, ring=None, ring_w=2):
    def make():
        big = Image.new("RGBA", (d * SS, d * SS), (ring or fill) + (0,))
        dr = ImageDraw.Draw(big)
        dr.ellipse([0, 0, d * SS - 1, d * SS - 1], fill=(ring or fill) + (255,))
        if ring:
            b = ring_w * SS
            dr.ellipse([b, b, d * SS - 1 - b, d * SS - 1 - b], fill=fill + (255,))
        return big.resize((d, d), Image.LANCZOS)

    return _photo(("ci", d, fill, ring, ring_w), make)


def icon(name, size, color):
    def make():
        n = size * SS
        img = Image.new("RGBA", (n, n), color + (0,))
        d = ImageDraw.Draw(img)
        u, c, lw = n / 24, color + (255,), max(1, int(round(2 * n / 24)))

        def rr(x0, y0, x1, y1, r, fill=None, outline=None):
            d.rounded_rectangle([x0 * u, y0 * u, x1 * u, y1 * u], radius=r * u, fill=fill,
                                outline=outline, width=lw)

        def dot(x, y, r):
            d.ellipse([(x - r) * u, (y - r) * u, (x + r) * u, (y + r) * u], fill=c)

        if name == "grid":
            for a, b in ((3, 3), (13, 3), (3, 13), (13, 13)):
                rr(a, b, a + 8, b + 8, 2.4, fill=c)
        elif name == "chip":
            rr(6, 6, 18, 18, 2.6, outline=c)
            rr(10, 10, 14, 14, 1, fill=c)
            for p in (9.2, 14.8):
                rr(p - 0.9, 2.5, p + 0.9, 6, 0.6, fill=c)
                rr(p - 0.9, 18, p + 0.9, 21.5, 0.6, fill=c)
                rr(2.5, p - 0.9, 6, p + 0.9, 0.6, fill=c)
                rr(18, p - 0.9, 21.5, p + 0.9, 0.6, fill=c)
        elif name == "pulse":
            pts = [(2.5, 12), (7, 12), (10, 4.5), (14, 19.5), (17, 12), (21.5, 12)]
            d.line([(x * u, y * u) for x, y in pts], fill=c, width=lw, joint="curve")
            for x, y in (pts[0], pts[-1]):
                dot(x, y, lw / 2 / u)
        elif name == "monitor":
            rr(3, 4, 21, 16, 2.6, outline=c)
            d.line([(12 * u, 16 * u), (12 * u, 20 * u)], fill=c, width=lw)
            d.line([(8 * u, 20.4 * u), (16 * u, 20.4 * u)], fill=c, width=lw)
            dot(8, 20.4, lw / 2 / u)
            dot(16, 20.4, lw / 2 / u)
        elif name == "doc":
            rr(5, 3, 19, 21, 2.4, outline=c)
            for y in (9, 13, 17):
                d.line([(8.5 * u, y * u), (15.5 * u, y * u)], fill=c, width=lw)
        elif name == "window":
            rr(3, 4, 21, 20, 2.6, outline=c)
            d.line([(3 * u, 9.5 * u), (21 * u, 9.5 * u)], fill=c, width=lw)
            dot(6.5, 6.8, 0.9)
        elif name == "info":
            d.ellipse([3 * u, 3 * u, 21 * u, 21 * u], outline=c, width=lw)
            dot(12, 7.6, 1.3)
            d.line([(12 * u, 11 * u), (12 * u, 17 * u)], fill=c, width=lw)
        elif name == "lock":
            rr(5, 10.5, 19, 21, 2.5, outline=c)
            d.arc([8 * u, 3 * u, 16 * u, 15 * u], 180, 360, fill=c, width=lw)
            d.line([(8 * u, 9 * u), (8 * u, 10.5 * u)], fill=c, width=lw)
            d.line([(16 * u, 9 * u), (16 * u, 10.5 * u)], fill=c, width=lw)
            dot(12, 15.8, 1.3)
        elif name == "face":
            d.ellipse([3 * u, 3 * u, 21 * u, 21 * u], outline=c, width=lw)
            dot(8.8, 10, 1.3)
            dot(15.2, 10, 1.3)
            d.arc([7.5 * u, 8.5 * u, 16.5 * u, 17.5 * u], 25, 155, fill=c, width=lw)
        elif name == "layers":
            rr(4, 4, 16, 16, 2.6, outline=c)
            rr(8, 8, 20, 20, 2.6, fill=SIDE + (255,), outline=c)
        elif name == "sliders":
            for y, kx in ((8, 9), (16, 15)):
                d.line([(3 * u, y * u), (21 * u, y * u)], fill=c, width=lw)
                dot(3, y, lw / 2 / u)
                dot(21, y, lw / 2 / u)
                d.ellipse([(kx - 3.2) * u, (y - 3.2) * u, (kx + 3.2) * u, (y + 3.2) * u], fill=SIDE + (255,),
                          outline=c, width=lw)
        return img.resize((size, size), Image.LANCZOS)

    return _photo(("ic", name, size, color), make)


def mascot(key, size, skin=None):
    """Mascote em RGBA (colorido) com o visual `skin` (padrão: o da ferramenta)."""
    skin = skin or skins.default(key)

    def make():
        img = {"claude": lambda: draw_claude(size * 2, tool=True, skin=skin),
               "codex": lambda: draw_codex(size * 2, skin=skin),
               "cursor": lambda: draw_cursor(size * 2, active=True, glow=0.4, skin=skin),
               "gemini": lambda: draw_gemini(size * 2, skin=skin)}[key]()
        w, h = img.width / 2, img.height / 2  # metade do tamanho desenhado (mais nítido)
        k = min(1.0, size * 1.1 / w, size * 1.1 / h)  # visuais largos (xícara) ou altos (chapéu) encolhem
        return img.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)

    return _photo(("mascot", key, size, skin), make)


# ------------------------------------------------------------------ animação
class Animator:
    """Um único relógio (~60 fps) que roda todas as animações ativas."""

    def __init__(self, root):
        self.root = root
        self.items = {}
        self.running = False

    def run(self, key, ms, fn, ease=out_cubic, delay=0, done=None):
        self.items[key] = {"t0": time.perf_counter() + delay / 1000, "dur": max(ms, 1) / 1000,
                           "fn": fn, "ease": ease, "done": done}
        if not self.running:
            self.running = True
            self.root.after(8, self._tick)

    def cancel(self, key):
        self.items.pop(key, None)

    def _tick(self):
        now = time.perf_counter()
        for key, a in list(self.items.items()):
            p = (now - a["t0"]) / a["dur"]
            if p < 0:
                continue
            try:
                a["fn"](a["ease"](min(1.0, p)))
                if p >= 1 and self.items.get(key) is a:
                    del self.items[key]
                    if a["done"]:
                        a["done"]()
            except tk.TclError:
                log("erro Tcl na animação: " + traceback.format_exc().replace("\n", " | "))
                self.items.pop(key, None)
            except Exception:  # noqa: BLE001
                log("erro na animação: " + traceback.format_exc().replace("\n", " | "))
                self.items.pop(key, None)
        if self.items:
            self.root.after(12, self._tick)
        else:
            self.running = False


# ------------------------------------------------------------------ estrutura
class Group:
    """Conjunto de itens do canvas que se move junto (um card, o cabeçalho...)."""

    def __init__(self, ui):
        self.ui = ui
        self.tag = f"g{next(ui.ids)}"
        self.ox = self.oy = 0
        self.visible = False
        self.targets, self.cards = [], []

    @property
    def c(self):
        return self.ui.c

    def _kw(self):
        return {"tags": (self.tag,), "state": "normal" if self.visible else "hidden"}

    def pos(self, x, y):
        return px(x) + self.ox, px(y) + self.oy

    def img(self, x, y, image, anchor="nw"):
        return self.c.create_image(*self.pos(x, y), image=image, anchor=anchor, **self._kw())

    def text(self, x, y, text, font, fill, anchor="nw", width=0):
        kw = {"width": px(width)} if width else {}
        return self.c.create_text(*self.pos(x, y), text=text, font=font, fill=hexc(fill), anchor=anchor,
                                  **kw, **self._kw())

    def show(self):
        if not self.visible:
            self.visible = True
            self.c.itemconfigure(self.tag, state="normal")

    def move_to(self, ox, oy):
        self.c.move(self.tag, ox - self.ox, oy - self.oy)
        self.ox, self.oy = ox, oy

    def target(self, x, y, w, h, obj, cursor="hand2"):
        tg = Target(self, px(x), px(y), px(x + w), px(y + h), obj, cursor)
        self.targets.append(tg)
        return tg

    def card(self, x, y, w, h):
        card = Card(self, x, y, w, h)
        self.cards.append(card)
        return card


class Target:
    def __init__(self, g, x0, y0, x1, y1, obj, cursor):
        self.g, self.rect, self.obj, self.cursor = g, (x0, y0, x1, y1), obj, cursor
        self.disabled = False

    def contains(self, x, y):
        if not self.g.visible or self.disabled:
            return False
        x0, y0, x1, y1 = self.rect
        return x0 + self.g.ox <= x < x1 + self.g.ox and y0 + self.g.oy <= y < y1 + self.g.oy


class Card:
    """Fundo arredondado de um card, com realce suave ao passar o mouse."""
    R = 14

    def __init__(self, g, x, y, w, h):
        self.g, self.t, self.active = g, 0.0, False  # active: borda de destaque (item selecionado)
        self.w, self.h = px(w), px(h)
        self.x0, self.y0 = px(x), px(y)
        self.item = g.img(x, y, self._image())

    def _image(self):
        k = q(self.t, 8)
        border = mix(ACC, ACC_HOVER, k) if self.active else mix(BORDER, BORDER_HOVER, k)
        return rrect(self.w, self.h, px(self.R), mix(CARD, CARD_HOVER, k), border, 2 if self.active else 1)

    def set(self, t):
        self.t = t
        self.g.c.itemconfigure(self.item, image=self._image())

    def contains(self, x, y):
        return (self.g.visible and self.x0 + self.g.ox <= x < self.x0 + self.w + self.g.ox
                and self.y0 + self.g.oy <= y < self.y0 + self.h + self.g.oy)


# ------------------------------------------------------------------ controles
class Switch:
    TW, TH, D, PAD = 46, 26, 20, 3

    def __init__(self, ui, g, x, y, value, on_toggle):
        self.ui, self.g, self.on_toggle = ui, g, on_toggle
        self.x, self.y, self.on, self.v = x, y, value, 1.0 if value else 0.0
        self.track = g.img(x, y, self._track())
        self.thumb = g.img(x, y, circle(px(self.D), (255, 255, 255)))
        self._place()
        g.target(x, y, self.TW, self.TH, self)

    def _track(self):
        k = q(self.v)
        return rrect(px(self.TW), px(self.TH), px(self.TH) // 2, mix(OFF, ACC, k), mix((70, 70, 80), ACC_HOVER, k))

    def _place(self, wiggle=0):
        tx = self.x + self.PAD + self.v * (self.TW - 2 * self.PAD - self.D) + wiggle
        self.g.c.coords(self.thumb, *self.g.pos(tx, self.y + (self.TH - self.D) / 2))
        self.g.c.itemconfigure(self.track, image=self._track())

    def set(self, on, animate=True):
        self.on = on
        a, b = self.v, 1.0 if on else 0.0
        if not animate:
            self.v = b
            return self._place()

        def step(e):
            self.v = a + (b - a) * e
            self._place()

        self.ui.anim.run(f"sw{id(self)}", 200, step)

    def press(self, _x, _y):
        new = not self.on
        if self.on_toggle(new) is False:  # recusado: sacode o botão
            self.ui.anim.run(f"sw{id(self)}", 320, lambda e: self._place(
                wiggle=3.2 * (1 - e) * __import__("math").sin(e * 22)))
            return
        self.set(new)

    def enter(self):
        pass

    def leave(self):
        pass


class Slider:
    TH, D, LABEL_W = 6, 18, 78

    def __init__(self, ui, g, x, y, w, lo, hi, step, value, fmt, on_change, enabled=True):
        self.ui, self.g = ui, g
        self.x, self.y, self.w = x, y, w
        self.lo, self.hi, self.step, self.fmt, self.on_change = lo, hi, step, fmt, on_change
        self.value, self.p, self.grow, self.dragging = value, (value - lo) / (hi - lo), 0.0, False
        self.enabled, self.en = enabled, 1.0 if enabled else 0.0
        self.track = g.img(x, y - self.TH / 2, rrect(px(w), px(self.TH), px(self.TH) // 2, (44, 44, 52)))
        self.fill = g.img(x, y - self.TH / 2, rrect(px(self.TH), px(self.TH), px(self.TH) // 2, ACC))
        self.thumb = g.img(x, y, circle(px(self.D), (255, 255, 255)))
        self.label = g.text(x + w + 16 + self.LABEL_W, y, fmt(value), ui.f["val"], ACC, anchor="e")
        self._draw()
        g.target(x - 10, y - 16, w + 20, 32, self)

    def _color(self):
        return mix((84, 84, 92), ACC, self.en)

    def _draw(self):
        d = px(self.D + 4 * self.grow)
        r = d / 2
        left = self.x + self.D / 2
        span = self.w - self.D
        cx = left + self.p * span
        fw = max(px(self.TH), px(cx - self.x))
        ring = mix((255, 255, 255), self._color(), 1.0) if self.grow > 0.05 else None
        self.g.c.itemconfigure(self.fill, image=rrect(fw, px(self.TH), px(self.TH) // 2, self._color()))
        self.g.c.itemconfigure(self.thumb, image=circle(d, mix((255, 255, 255), (214, 214, 220), 1 - self.en),
                                                        ring, 2) if ring else circle(
            d, mix((255, 255, 255), (214, 214, 220), 1 - self.en)))
        x0, y0 = self.g.pos(cx - r / S, self.y - r / S)
        self.g.c.coords(self.thumb, x0, y0)
        self.g.c.itemconfigure(self.label, fill=hexc(mix(DIM, ACC, self.en)))

    def set_enabled(self, on):
        self.enabled = on
        a, b = self.en, 1.0 if on else 0.0

        def step(e):
            self.en = a + (b - a) * e
            self._draw()

        self.ui.anim.run(f"sl_en{id(self)}", 220, step)

    def _from_x(self, mx, animate):
        left = px(self.x + self.D / 2) + self.g.ox
        span = px(self.w - self.D)
        p = max(0.0, min(1.0, (mx - left) / max(1, span)))
        v = int(round((self.lo + p * (self.hi - self.lo)) / self.step) * self.step)
        v = max(self.lo, min(self.hi, v))
        target = (v - self.lo) / (self.hi - self.lo)
        if v != self.value:
            self.value = v
            self.g.c.itemconfigure(self.label, text=self.fmt(v))
            self.on_change(v)
        if animate:
            a = self.p

            def step(e):
                self.p = a + (target - a) * e
                self._draw()

            self.ui.anim.run(f"sl{id(self)}", 160, step)
        else:
            self.ui.anim.cancel(f"sl{id(self)}")
            self.p = target
            self._draw()

    def _grow(self, to):
        a = self.grow

        def step(e):
            self.grow = a + (to - a) * e
            self._draw()

        self.ui.anim.run(f"slg{id(self)}", 140, step)

    def press(self, mx, my):
        if not self.enabled:
            return
        self.dragging = True
        self._grow(1.0)
        self._from_x(mx, animate=True)

    def drag(self, mx, my):
        if self.dragging:
            self._from_x(mx, animate=False)

    def release(self, mx, my):
        if self.dragging:
            self.dragging = False
            self._grow(0.0)

    def enter(self):
        if self.enabled and not self.dragging:
            self._grow(1.0)

    def leave(self):
        if not self.dragging:
            self._grow(0.0)


class Button:
    def __init__(self, ui, g, x, y, w, h, text, on_click, primary=False):
        self.ui, self.g, self.on_click, self.primary = ui, g, on_click, primary
        self.x, self.y, self.w, self.h, self.hv, self.pressed = x, y, w, h, 0.0, False
        self.color = None
        self.bg = g.img(x, y, self._image())
        self.txt = g.text(x + w / 2, y + h / 2, text, ui.f["btn"], (255, 255, 255) if primary else TEXT,
                          anchor="center")
        g.target(x, y, w, h, self)

    def _image(self):
        k = q(self.hv, 8)
        base = self.color or (ACC if self.primary else (38, 38, 46))
        hov = mix(base, (255, 255, 255), 0.10) if self.color else (ACC_HOVER if self.primary else (50, 50, 60))
        fill = mix(base, hov, k)
        if self.pressed:
            fill = mix(fill, (0, 0, 0), 0.18)
        return rrect(px(self.w), px(self.h), px(self.h) // 2 if self.h < 44 else px(12), fill,
                     None if self.primary or self.color else mix((52, 52, 62), (70, 70, 82), k))

    def _tween(self, to):
        a = self.hv

        def step(e):
            self.hv = a + (to - a) * e
            self.g.c.itemconfigure(self.bg, image=self._image())

        self.ui.anim.run(f"bt{id(self)}", 150, step)

    def set(self, text, color=None):
        self.color = color
        self.g.c.itemconfigure(self.txt, text=text,
                               fill=hexc((255, 255, 255) if (self.primary or color) else TEXT))
        self.g.c.itemconfigure(self.bg, image=self._image())

    def enter(self):
        self._tween(1.0)

    def leave(self):
        self.pressed = False
        self._tween(0.0)

    def press(self, _x, _y):
        self.pressed = True
        self.g.c.itemconfigure(self.bg, image=self._image())

    def release(self, mx, my):
        was = self.pressed
        self.pressed = False
        self.g.c.itemconfigure(self.bg, image=self._image())
        tg = [t_ for t_ in self.g.targets if t_.obj is self][0]
        if was and tg.contains(mx, my):
            self.on_click()


class Segmented:
    def __init__(self, ui, g, x, y, w, h, options, value, on_change):
        self.ui, self.g, self.options, self.on_change = ui, g, options, on_change
        self.x, self.y, self.w, self.h, self.pad = x, y, w, h, 3
        self.sw = (w - 2 * self.pad) / len(options)
        self.idx = [k for k, _ in options].index(value)
        self.pos = float(self.idx)
        g.img(x, y, rrect(px(w), px(h), px(h) // 2, (17, 17, 21), (40, 40, 48)))
        self.hl = g.img(x, y, rrect(px(self.sw), px(h - 2 * self.pad), px(h - 2 * self.pad) // 2, ACC))
        self.labels = []
        for i, (_, label) in enumerate(options):
            self.labels.append(g.text(x + self.pad + self.sw * (i + 0.5), y + h / 2, label, ui.f["btn"],
                                      (255, 255, 255) if i == self.idx else MUTED, anchor="center"))
        self._place()
        g.target(x, y, w, h, self)

    def _place(self):
        self.g.c.coords(self.hl, *self.g.pos(self.x + self.pad + self.pos * self.sw, self.y + self.pad))
        for i, item in enumerate(self.labels):
            near = max(0.0, 1 - abs(self.pos - i))
            self.g.c.itemconfigure(item, fill=hexc(mix(MUTED, (255, 255, 255), near)))

    def press(self, mx, _my):
        i = int((mx - self.g.ox - px(self.x + self.pad)) // max(1, px(self.sw)))
        i = max(0, min(len(self.options) - 1, i))
        if i == self.idx:
            return
        self.idx = i
        a = self.pos

        def step(e):
            self.pos = a + (i - a) * e
            self._place()

        self.ui.anim.run(f"sg{id(self)}", 260, step, ease=out_quint)
        self.on_change(self.options[i][0])

    def enter(self):
        pass

    def leave(self):
        pass


# ------------------------------------------------------------------ aplicativo
class Page:
    def __init__(self):
        self.groups, self.targets = [], []


class SettingsApp:
    PAGES = [("overview", "nav.overview", "grid"), ("templates", "nav.templates", "layers"),
             ("skins", "nav.skins", "face"), ("tools", "nav.tools", "chip"),
             ("detection", "nav.detection", "pulse"), ("saver", "nav.saver", "monitor"),
             ("general", "nav.general", "sliders"), ("how", "nav.how", "info")]

    def __init__(self, root):
        self.root = root
        self.ids = itertools.count()
        self.cfg = settings.load()
        self.anim = Animator(root)
        self.f = self._fonts()
        self.c = tk.Canvas(root, width=px(W), height=px(H), bg=hexc(BG), highlightthickness=0, bd=0)
        self.c.pack(fill="both", expand=True)
        self.page_idx, self.page = -1, None
        self.chrome_targets, self.hover, self.drag, self.hover_cards = [], None, None, []
        self.dirty, self.save_job, self.toast_job = {}, None, None
        self.states, self.preview_photo, self.preview_img = {}, None, None
        self.chips, self.live_dot, self.reset_job = {}, None, None
        self.q = queue.Queue()
        self.wake = threading.Event()
        self.alive = True
        self.build_chrome()
        self.show_page(0, animate=True)
        self.c.bind("<Motion>", self.on_motion)
        self.c.bind("<Leave>", lambda e: self.on_motion(None))
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_drag)
        self.c.bind("<ButtonRelease-1>", self.on_release)
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.after(150, self.poll)
        self.root.after(80, self.pulse)

    # ---- fontes
    def _fonts(self):
        fams = set(tkfont.families(self.root))
        sans = "Segoe UI Variable Text" if "Segoe UI Variable Text" in fams else "Segoe UI"
        semi = "Segoe UI Semibold" if "Segoe UI Semibold" in fams else sans
        mk = lambda fam, size, weight="normal": tkfont.Font(  # noqa: E731
            root=self.root, family=fam, size=-px(size), weight=weight)
        return {"title": mk(semi, 26), "sub": mk(sans, 13), "label": mk(semi, 15), "small": mk(sans, 12),
                "nav": mk(semi, 14), "brand": mk(semi, 15), "tiny": mk(sans, 11), "btn": mk(semi, 13),
                "val": mk(semi, 13), "chip": mk(semi, 14)}

    # ---- moldura fixa (barra lateral)
    def build_chrome(self):
        c = self.c
        c.delete("all")
        self.chrome_targets.clear()
        self.nav_items = []
        c.create_rectangle(0, 0, px(SIDE_W), px(H), fill=hexc(SIDE), outline="")
        c.create_line(px(SIDE_W), 0, px(SIDE_W), px(H), fill=hexc((28, 28, 34)))
        self.logo = ImageTk.PhotoImage(logo(px(36)))
        c.create_image(px(24), px(30), image=self.logo, anchor="nw")
        c.create_text(px(68), px(30), text=t("ui.title"), font=self.f["brand"], fill=hexc(TEXT), anchor="nw")
        c.create_text(px(68), px(52), text=t("ui.subtitle"), font=self.f["tiny"], fill=hexc(MUTED), anchor="nw")
        self.sel_y = 0.0
        self.sel_item = c.create_image(px(12), px(112), anchor="nw",
                                      image=rrect(px(SIDE_W - 24), px(42), px(10), (30, 30, 37)))
        self.sel_bar = c.create_image(px(12), px(112), anchor="nw",
                                     image=rrect(px(3), px(18), px(2), ACC))
        for i, (key, label, ic) in enumerate(self.PAGES):
            y = 112 + i * 48
            hov = c.create_image(px(12), px(y), anchor="nw", image=rrect(px(SIDE_W - 24), px(42), px(10), SIDE))
            ic_item = c.create_image(px(34), px(y + 10), anchor="nw", image=icon(ic, px(22), MUTED))
            tx = c.create_text(px(68), px(y + 21), text=t(label), font=self.f["nav"], fill=hexc(MUTED), anchor="w")
            item = {"key": key, "i": i, "y": y, "hov": hov, "ic": ic_item, "ic_name": ic, "tx": tx, "h": 0.0,
                    "sel": 0.0}
            self.nav_items.append(item)
            self.chrome_targets.append(Target(_ChromeGroup(), px(12), px(y), px(SIDE_W - 12), px(y + 42),
                                              NavHit(self, item), "hand2"))
        c.tag_raise(self.sel_item)
        c.create_text(px(24), px(H - 24), text=t("ui.footer"), font=self.f["tiny"], fill=hexc(DIM), anchor="sw",
                      width=px(SIDE_W - 44))
        for it in self.nav_items:
            for k in ("hov", "ic", "tx"):
                c.tag_raise(it[k])
        c.tag_raise(self.sel_bar)
        self._paint_nav()

    def _paint_nav(self):
        for it in self.nav_items:
            k = it["sel"]
            self.c.itemconfigure(it["tx"], fill=hexc(mix(MUTED, TEXT, max(k, it["h"] * 0.6))))
            self.c.itemconfigure(it["ic"], image=icon(it["ic_name"], px(22), mix(MUTED, ACC, q(k))))
            self.c.itemconfigure(it["hov"], image=rrect(px(SIDE_W - 24), px(42), px(10),
                                                       mix(SIDE, (26, 26, 32), q(it["h"] * (1 - k), 6))))

    def _move_sel(self, idx, animate=True):
        target = 112 + idx * 48
        a = self.sel_y or target

        def step(e):
            y = a + (target - a) * e
            self.sel_y = y
            self.c.coords(self.sel_item, px(12), px(y))
            self.c.coords(self.sel_bar, px(12 + 6), px(y + 12))
            for it in self.nav_items:
                near = max(0.0, 1 - abs(y - it["y"]) / 48)
                it["sel"] = near
            self._paint_nav()

        if animate:
            self.anim.run("nav_sel", 320, step, ease=out_quint)
        else:
            step(1.0)

    # ---- páginas
    def show_page(self, idx, animate=True):
        if idx == self.page_idx:
            return
        old = self.page
        if old:
            for g in old.groups:
                self.c.delete(g.tag)
        for key in [k for k in self.anim.items if k.startswith("pg_")]:
            self.anim.cancel(key)
        self.hover_cards = []
        self.page_idx = idx
        self.chips, self.live_dot = {}, None
        self.preview_item = None
        self.page = Page()
        getattr(self, "page_" + self.PAGES[idx][0])()
        self.hover = None
        self._move_sel(idx, animate)
        if self.PAGES[idx][0] == "overview":
            self.states_dirty = True
            self.wake.set()
        if self.PAGES[idx][0] == "how":
            self.wake.set()
            self.how_start()
        for n, g in enumerate(self.page.groups):
            self.page.targets.extend(g.targets)
            if animate:
                g.move_to(0, 26)

                def step(e, g=g):
                    g.show()
                    g.move_to(0, int(26 * (1 - e)))

                self.anim.run(f"pg_{id(g)}", 420, step, ease=out_quint, delay=n * 45)
            else:
                g.show()

    def new_group(self):
        g = Group(self)
        self.page.groups.append(g)
        return g

    def header(self, title_key, sub_key):
        g = self.new_group()
        g.text(CX, 32, t(title_key), self.f["title"], TEXT)
        g.text(CX, 74, t(sub_key), self.f["sub"], MUTED)
        return g

    def row(self, y, title, desc, h=CARD_H):
        g = self.new_group()
        g.card(CX, y, CW, h)
        g.text(CX + 22, y + 20, title, self.f["label"], TEXT)
        g.text(CX + 22, y + 45, desc, self.f["small"], MUTED, width=300)
        self.hover_cards.append(g.cards[0])
        return g

    # -- visão geral
    def page_overview(self):
        hg = self.header("ov.title", "ov.sub")
        Button(self, hg, CX + CW - 196, 34, 196, 40, t("ov.test"), self.test_saver, primary=True)
        g = self.new_group()
        card_h = 52 + 315 + 22
        g.card(CX, 112, CW, card_h)
        self.hover_cards.append(g.cards[0])
        g.text(CX + 22, 130, t("ov.preview"), self.f["label"], TEXT)
        self.live_dot = g.img(CX + CW - 92, 134, circle(px(8), GREEN), anchor="nw")
        g.text(CX + CW - 76, 131, t("ov.live"), self.f["small"], MUTED)
        pw, ph = 560, 315
        self.preview_size = (px(pw), px(ph))
        self.preview_photo = self._preview_photo(self.preview_img)  # guarda a referência (senão o Tk perde a imagem)
        self.preview_item = g.img(CX + (CW - pw) / 2, 164, self.preview_photo)
        # cartões de status
        cg = self.new_group()
        n = len(settings.TOOLS)
        cw = (CW - 12 * (n - 1)) / n
        for i, key in enumerate(settings.TOOLS):
            x, y = CX + i * (cw + 12), 112 + card_h + 14
            cg.card(x, y, cw, 64)
            dot = cg.img(x + 20, y + 26, circle(px(12), OFF))
            name = cg.text(x + 44, y + 14, t("tool." + key), self.f["chip"], TEXT)
            st = cg.text(x + 44, y + 36, "", self.f["small"], MUTED)
            self.chips[key] = {"dot": dot, "name": name, "st": st, "c": OFF, "g": cg}
        self.hover_cards.extend(cg.cards)
        self._paint_chips()

    def _preview_photo(self, img):
        if img is None:
            blank = Image.new("RGBA", self.preview_size, BG + (255,))
            return ImageTk.PhotoImage(blank)
        return ImageTk.PhotoImage(img)

    STATE_COLOR = {"open": (150, 150, 158), "closed": (74, 74, 82), "off": (52, 52, 58)}

    def _paint_chips(self):
        for key, ch in self.chips.items():
            st = self.states.get(key, "closed")
            target = TOOL_ACCENT.get(key, ACC) if st == "working" else self.STATE_COLOR.get(st, OFF)
            label = t("ov.off") if st == "off" else (t("state." + st) if st in ("working", "open", "closed") else "")
            self.c.itemconfigure(ch["st"], text=label,
                                 fill=hexc(target if st == "working" else (MUTED if st != "off" else DIM)))
            self.c.itemconfigure(ch["name"], fill=hexc(TEXT if st in ("working", "open") else
                                                       (MUTED if st == "closed" else DIM)))
            a = ch["c"]

            def step(e, ch=ch, a=a, target=target):
                ch["c"] = mix(a, target, e)
                self.c.itemconfigure(ch["dot"], image=circle(px(12), mix((0, 0, 0), ch["c"], 1) if False else
                                                             tuple(int(v) for v in ch["c"])))

            self.anim.run(f"chip_{key}", 380, step)

    # -- modelos
    def page_templates(self):
        hg = self.header("tpl.title", "tpl.sub")
        Button(self, hg, CX + CW - 176, 34, 176, 40, t("tpl.suggest"),
               lambda: webbrowser.open(REPO_URL + "/issues/new"))
        pw, ph, h = 120, 68, 88
        for i, tpl in enumerate(templates.TEMPLATES):
            key, ok = tpl["id"], tpl["available"]
            y = 120 + i * (h + 10)
            g = self.new_group()
            card = g.card(CX, y, CW, h)
            self.hover_cards.append(card)
            card.active = ok and key == self.cfg["template"]
            card.set(card.t)
            g.img(CX + 16, y + (h - ph) / 2, self._tpl_photo(key, ok, px(pw), px(ph)))
            tx = CX + 16 + pw + 20
            g.text(tx, y + 18, t(f"tpl.{key}.n"), self.f["label"], TEXT if ok else MUTED)
            g.text(tx, y + 43, t(f"tpl.{key}.d"), self.f["small"], MUTED if ok else DIM, width=270)
            label = t("tpl.active") if card.active else ("" if ok else t("tpl.soon"))
            if label:
                bw, bh = int(self.f["small"].measure(label) / S) + 30, 28
                bx, by = CX + CW - 22 - bw, y + (h - bh) / 2
                g.img(bx, by, rrect(px(bw), px(bh), px(bh) // 2, ACC if card.active else (30, 30, 37),
                                    None if card.active else (56, 56, 66)))
                g.text(bx + bw / 2, by + bh / 2, label, self.f["small"],
                       (255, 255, 255) if card.active else MUTED, anchor="center")
            g.target(CX, y, CW, h, TemplateHit(self, key, ok))

    def _tpl_photo(self, key, ok, w, h):
        cache = self.__dict__.setdefault("tpl_photos", {})
        if (key, w, h) not in cache:
            cache[(key, w, h)] = ImageTk.PhotoImage(template_preview(key, ok, w, h))
        return cache[(key, w, h)]

    # -- como funciona
    def page_how(self):
        self.header("how.title", "how.sub")
        cfg = self.cfg
        cw = (CW - 24) / 3
        blocks = [("doc", "how.files", {"win": duration(cfg["active_window"])}),
                  ("pulse", "how.proc", {"grace": duration(cfg["close_grace"])}),
                  ("window", "how.focus", {"hold": duration(cfg["focus_hold"])})]
        for i, (ic, key, kw) in enumerate(blocks):
            x, y = CX + i * (cw + 12), 118
            g = self.new_group()
            self.hover_cards.append(g.card(x, y, cw, 164))
            g.img(x + 18, y + 18, icon(ic, px(24), ACC))
            g.text(x + 54, y + 21, t(key + ".t"), self.f["label"], TEXT)
            desc = t("how.focus.off") if key == "how.focus" and not cfg["follow_focus"] else t(key + ".d", **kw)
            g.text(x + 18, y + 58, desc, self.f["small"], MUTED, width=cw - 36)
        # leitura ao vivo
        y0 = 118 + 164 + 12
        lg = self.new_group()
        live_h = 82 + 38 * len(settings.TOOLS)
        self.hover_cards.append(lg.card(CX, y0, CW, live_h))
        lg.text(CX + 22, y0 + 16, t("how.live"), self.f["label"], TEXT)
        self.live_dot = lg.img(CX + CW - 24 - 10, y0 + 21, circle(px(8), GREEN), anchor="ne")
        for label, dx in (("how.col.files", 170), ("how.col.proc", 300), ("how.col.focus", 410)):
            lg.text(CX + dx, y0 + 48, t(label), self.f["tiny"], DIM)
        self.how_rows = {}
        for i, key in enumerate(settings.TOOLS):
            y = y0 + 72 + i * 38
            lg.text(CX + 22, y, t("tool." + key), self.f["chip"], TEXT)
            row = {"cache": None}
            for col, dx in (("files", 170), ("proc", 300), ("focus", 410)):
                row[col] = lg.text(CX + dx, y + 2, "", self.f["small"], MUTED)
            row["pill"] = lg.img(CX + CW - 22 - 92, y - 3, rrect(px(92), px(26), px(13), (30, 30, 37), BORDER))
            row["pill_tx"] = lg.text(CX + CW - 22 - 46, y + 10, "", self.f["small"], MUTED, anchor="center")
            self.how_rows[key] = row
        pg = self.new_group()
        self.hover_cards.append(pg.card(CX, y0 + live_h + 12, CW, 66))
        pg.img(CX + 20, y0 + live_h + 12 + 21, icon("lock", px(24), GREEN))
        pg.text(CX + 58, y0 + live_h + 12 + 13, t("how.privacy"), self.f["small"], MUTED, width=CW - 80)

    def how_start(self):
        if getattr(self, "how_job", None):
            self.root.after_cancel(self.how_job)
        self.how_tick()

    def how_tick(self):
        self.how_job = None
        if not self.page or self.PAGES[self.page_idx][0] != "how":
            return
        try:
            self._paint_how(*self._read_signals())
        except tk.TclError:
            return
        self.how_job = self.root.after(1500, self.how_tick)

    def _read_signals(self):
        """Sinais mais recentes: do status.json da bandeja (inclui a janela em foco) ou, se ela
        não estiver respondendo, da leitura local desta janela (sem o foco, que seria a própria janela)."""
        try:
            data = json.loads((settings.OUT_DIR / "status.json").read_text(encoding="utf-8"))
            if time.time() - data["updated"] < 15:
                return data["signals"], True
        except (OSError, ValueError, KeyError):
            pass
        from . import detector
        return dict(detector.LAST), False

    def _ago(self, age):
        if age is None:
            return t("how.none")
        if age < 5:
            return t("how.now")
        return t("how.long") if age > 3600 else t("how.ago", t=duration(age))

    STATE_COLORS = {"open": (150, 150, 158), "closed": (96, 96, 104), "off": (70, 70, 78)}

    def _paint_how(self, sig, from_tray):
        tools = self.cfg["tools"]
        for key, row in self.how_rows.items():
            s = sig.get(key) or {}
            state = s.get("state", "closed") if tools.get(key, True) else "off"
            if state == "off":
                texts = ("—", "—", "—")
            else:
                proc = s.get("running")
                focus = (t("how.now") if s.get("focus_now") else self._ago(s.get("focus_age"))) if from_tray else "—"
                texts = (self._ago(s.get("file_age")),
                         "—" if proc is None else (t("how.open") if proc else t("how.notrunning")),
                         focus)
            if row["cache"] == (texts, state):
                continue
            row["cache"] = (texts, state)
            for col, tx in zip(("files", "proc", "focus"), texts):
                self.c.itemconfigure(row[col], text=tx, fill=hexc(MUTED if state != "off" else DIM))
            color = TOOL_ACCENT.get(key, ACC) if state == "working" else self.STATE_COLORS.get(state, MUTED)
            label = t("ov.off") if state == "off" else t("state." + state)
            self.c.itemconfigure(row["pill"], image=rrect(px(92), px(26), px(13), (30, 30, 37), color))
            self.c.itemconfigure(row["pill_tx"], text=label, fill=hexc(color))

    # -- personagens (visuais dos mascotes)
    def page_skins(self):
        self.header("skins.title", "skins.sub")
        # quatro visuais por linha, para as quatro ferramentas caberem na janela sem rolar
        gap, chh, rgap = 10, 58, 8
        cw = (CW - 44 - 3 * gap) / 4
        cols = max(1, (CW - 44 + gap) // (cw + gap))  # quantos visuais cabem numa linha; o resto desce
        y = 120
        for key in settings.TOOLS:
            options = [s_ for s_ in skins.SKINS[key] if s_["available"]]
            rows = -(-len(options) // cols)
            h = 44 + rows * chh + (rows - 1) * rgap + 12
            g = self.new_group()
            self.hover_cards.append(g.card(CX, y, CW, h))
            g.text(CX + 22, y + 18, t("tool." + key), self.f["label"], TEXT)
            current = self.cfg["skins"][key]
            for j, sk in enumerate(options):
                cx, cy = CX + 22 + (j % cols) * (cw + gap), y + 44 + (j // cols) * (chh + rgap)
                chip = g.card(cx, cy, cw, chh)
                self.hover_cards.append(chip)
                chip.active = sk["id"] == current
                chip.set(chip.t)
                spr = mascot(key, px(44), sk["id"])
                g.img(cx + 10, cy + (chh - spr.height() / S) / 2, spr)
                g.text(cx + 10 + 50, cy + chh / 2, t(f"skin.{key}.{sk['id']}"), self.f["small"],
                       TEXT if chip.active else MUTED, anchor="w", width=cw - 10 - 50 - 6)
                g.target(cx, cy, cw, chh, SkinHit(self, key, sk["id"]))
            y += h + gap

    # -- ferramentas
    def page_tools(self):
        self.header("tools.title", "tools.sub")
        for i, key in enumerate(settings.TOOLS):
            y = 120 + i * (CARD_H + 12)
            g = self.row(y, t("tool." + key), t(f"tools.{key}.desc"))
            m = mascot(key, px(50), self.cfg["skins"][key])
            g.img(CX + CW - 22 - 46 - 18 - 56, y + CARD_H / 2 - m.height() / 2 / S, m)
            Switch(self, g, CX + CW - 22 - 46, y + (CARD_H - 26) / 2, self.cfg["tools"][key],
                   lambda v, k=key: self.set_tool(k, v))

    # -- detecção
    def page_detection(self):
        self.header("det.title", "det.sub")
        specs = [("active_window", "det.active", 30, 900, 10, duration),
                 ("follow_focus", "det.follow", None, None, None, None),
                 ("focus_hold", "det.hold", 0, 600, 10, duration),
                 ("close_grace", "det.grace", 5, 120, 5, duration)]
        self.sliders = {}
        for i, (key, tk_, lo, hi, step, fmt) in enumerate(specs):
            y = 120 + i * (CARD_H + 12)
            g = self.row(y, t(tk_ + ".t"), t(tk_ + ".d"))
            if lo is None:
                Switch(self, g, CX + CW - 22 - 46, y + (CARD_H - 26) / 2, self.cfg[key],
                       lambda v, k=key: self.set_value(k, v))
            else:
                sl = Slider(self, g, CX + CW - 22 - 78 - 16 - 170, y + CARD_H / 2, 170, lo, hi, step,
                            self.cfg[key], fmt, lambda v, k=key: self.set_value(k, v),
                            enabled=(self.cfg["follow_focus"] if key == "focus_hold" else True))
                self.sliders[key] = sl

    # -- protetor
    def page_saver(self):
        self.header("sv.title", "sv.sub")
        self.sv = {}
        g = self.row(120, t("sv.on.t"), t("sv.on.d"))
        Switch(self, g, CX + CW - 22 - 46, 120 + (CARD_H - 26) / 2, self.cfg["saver_on"], self.toggle_saver)
        g = self.row(120 + CARD_H + 12, t("sv.idle.t"), t("sv.idle.d"))
        y = 120 + CARD_H + 12
        self.sv["idle"] = Slider(self, g, CX + CW - 22 - 78 - 16 - 170, y + CARD_H / 2, 170, 1, 60, 1,
                                 self.cfg["idle_min"], lambda v: t("unit.min", n=v),
                                 lambda v: self.set_value("idle_min", v), enabled=self.cfg["saver_on"])
        y = 120 + 2 * (CARD_H + 12)
        g = self.row(y, t("sv.media.t"), t("sv.media.d"))
        self.sv["media"] = Switch(self, g, CX + CW - 22 - 46, y + (CARD_H - 26) / 2,
                                  self.cfg["saver_skip_media"], lambda v: self.set_value("saver_skip_media", v))
        y = 120 + 3 * (CARD_H + 12)
        g = self.row(y, t("sv.lock.t"), t("sv.lock.d"))
        self.sv["lock"] = Switch(self, g, CX + CW - 22 - 46, y + (CARD_H - 26) / 2, self.cfg["lock_after"],
                                 lambda v: self.set_value("lock_after", v))
        tg = self.new_group()
        Button(self, tg, CX, y + CARD_H + 20, 150, 40, t("sv.test"), self.test_saver, primary=True)

    # -- geral
    def page_general(self):
        self.header("gen.title", "gen.sub")
        y = 120
        g = self.row(y, t("gen.lang.t"), t("gen.lang.d"))
        opts = [("auto", t("gen.lang.auto")), ("pt", t("gen.lang.pt")), ("en", t("gen.lang.en"))]
        Segmented(self, g, CX + CW - 22 - 280, y + (CARD_H - 38) / 2, 280, 38, opts, self.cfg["lang"],
                  self.set_lang)
        y += CARD_H + 12
        g = self.row(y, t("gen.start.t"), t("gen.start.d"))
        Switch(self, g, CX + CW - 22 - 46, y + (CARD_H - 26) / 2, autostart.is_enabled(), self.set_autostart)
        y += CARD_H + 12
        if platforms.current().LOCK_SCREEN_OPT_IN:  # macOS: a lock screen mostra o papel de parede
            g = self.row(y, t("gen.wall.t"), t("gen.wall.d"))
            Switch(self, g, CX + CW - 22 - 46, y + (CARD_H - 26) / 2, self.cfg["lock_wallpaper"],
                   lambda v: self.set_value("lock_wallpaper", v))
            y += CARD_H + 12
        g = self.row(y, t("gen.folder.t"), t("gen.folder.d"))
        Button(self, g, CX + CW - 22 - 110, y + (CARD_H - 38) / 2, 110, 38, t("gen.folder.b"),
               lambda: platforms.current().open_path(settings.OUT_DIR))
        y += CARD_H + 12
        g = self.row(y, t("gen.reset.t"), t("gen.reset.d"))
        self.reset_btn = Button(self, g, CX + CW - 22 - 130, y + (CARD_H - 38) / 2, 130, 38, t("gen.reset.b"),
                                self.reset_click)

    # ---- ações
    def commit(self, **changes):
        self.dirty.update(changes)
        if self.save_job:
            self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(220, self._flush)

    def _flush(self):
        self.save_job = None
        changes, self.dirty = self.dirty, {}
        try:
            self.cfg = settings.update(**changes)
            self.toast(t("ui.saved"))
        except OSError:
            log("não consegui salvar: " + traceback.format_exc().replace("\n", " | "))
        self.wake.set()

    def set_value(self, key, value):
        self.cfg[key] = value
        self.commit(**{key: value})
        if key == "follow_focus" and "focus_hold" in getattr(self, "sliders", {}):
            self.sliders["focus_hold"].set_enabled(value)

    def set_tool(self, key, on):
        tools = dict(self.cfg["tools"])
        tools[key] = on
        if not any(tools.values()):
            self.toast(t("tools.min"), warn=True)
            return False
        self.cfg["tools"] = tools
        self.commit(tools=tools)
        self.states_dirty = True
        return True

    def set_skin(self, tool, skin_id):
        chosen = dict(self.cfg["skins"])
        chosen[tool] = skin_id
        self.cfg["skins"] = chosen
        self.commit(skins=chosen)
        self.states_dirty = True
        _tpl_cache.clear()  # as miniaturas dos modelos usam o visual escolhido
        self.__dict__.get("tpl_photos", {}).clear()
        self.relang()  # redesenha a página com o visual marcado

    def toggle_saver(self, on):
        self.set_value("saver_on", on)
        self.sv["idle"].set_enabled(on)

    def set_autostart(self, on):
        try:
            autostart.enable() if on else autostart.disable()
        except Exception:  # noqa: BLE001
            log("autostart: " + traceback.format_exc().replace("\n", " | "))
            return False
        self.toast(t("ui.saved"))

    def set_lang(self, lang):
        self.cfg["lang"] = lang
        self.commit(lang=lang)
        self.root.after(260, self.relang)

    def relang(self):
        self.root.title(t("ui.title"))
        keep = self.page_idx
        self.anim.items.clear()
        self.page_idx = -1
        self.build_chrome()
        self.show_page(keep, animate=False)
        self._move_sel(keep, animate=False)

    def reset_click(self):
        if self.reset_job is None:
            self.reset_btn.set(t("gen.reset.c"), RED)
            self.reset_job = self.root.after(3000, self._reset_cancel)
            return
        self.root.after_cancel(self.reset_job)
        self.reset_job = None
        self.cfg = settings.reset()
        self.wake.set()
        self.toast(t("ui.saved"))
        self.relang()

    def _reset_cancel(self):
        self.reset_job = None
        try:
            self.reset_btn.set(t("gen.reset.b"))
        except tk.TclError:
            pass

    def test_saver(self):
        subprocess.Popen(launcher.command("saver", "/s"))

    # ---- aviso (toast)
    def toast(self, text, warn=False, info=False):
        c = self.c
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        c.delete("toast")
        mw = self.f["btn"].measure(text) + px(52)
        w, h = mw, px(38)
        x = px(W) - px(36) - w
        y_end = px(H) - px(30) - h
        col = RED if warn else (ACC if info else GREEN)
        bg = c.create_image(x, px(H) + px(10), image=rrect(w, h, h // 2, (30, 30, 37), (56, 56, 66)),
                            anchor="nw", tags="toast")
        dot = c.create_image(x + px(16), px(H) + px(10) + (h - px(10)) // 2, image=circle(px(10), col),
                             anchor="nw", tags="toast")
        tx = c.create_text(x + px(36), px(H) + px(10) + h // 2, text=text, font=self.f["btn"], fill=hexc(TEXT),
                           anchor="w", tags="toast")
        a = px(H) + px(10)

        def step(e):
            dy = (a + (y_end - a) * e) - a
            for item in (bg, dot, tx):
                cx, cy = c.coords(item)
                base = {bg: a, dot: a + (h - px(10)) // 2, tx: a + h // 2}[item]
                c.coords(item, cx, base + dy)

        self.anim.run("toast", 380, step, ease=out_quint)
        self.toast_job = self.root.after(1900, lambda: self._toast_out(bg, dot, tx, y_end, a, h))

    def _toast_out(self, bg, dot, tx, y_end, a, h):
        c = self.c

        def step(e):
            dy = (y_end - a) + (a - y_end) * e
            try:
                for item, base in ((bg, a), (dot, a + (h - px(10)) // 2), (tx, a + h // 2)):
                    cx, cy = c.coords(item)
                    c.coords(item, cx, base + dy)
            except tk.TclError:
                pass

        self.anim.run("toast", 300, step, ease=in_out, done=lambda: c.delete("toast"))
        self.toast_job = None

    # ---- eventos do mouse
    def _hit(self, x, y):
        for tg in reversed(self.chrome_targets + self.page.targets):
            if tg.contains(x, y):
                return tg
        return None

    def on_motion(self, e):
        x, y = (e.x, e.y) if e else (-1, -1)
        if self.drag:
            return
        tg = self._hit(x, y)
        if tg is not self.hover:
            if self.hover:
                self.hover.obj.leave()
            self.hover = tg
            if tg:
                tg.obj.enter()
            self.c.configure(cursor=tg.cursor if tg else "")
        for card in self.hover_cards:
            inside = card.contains(x, y)
            to = 1.0 if inside else 0.0
            if abs(card.t - to) > 0.01 and self.anim.items.get(f"cd{id(card)}") is None or \
                    (inside and card.t < 0.99) or (not inside and card.t > 0.01):
                self._card_to(card, to)

    def _card_to(self, card, to):
        if getattr(card, "goal", None) == to:
            return
        card.goal = to
        a = card.t
        self.anim.run(f"cd{id(card)}", 180, lambda e: card.set(a + (to - a) * e))

    def on_press(self, e):
        tg = self._hit(e.x, e.y)
        if tg:
            self.drag = tg
            tg.obj.press(e.x, e.y)

    def on_drag(self, e):
        if self.drag and hasattr(self.drag.obj, "drag"):
            self.drag.obj.drag(e.x, e.y)

    def on_release(self, e):
        tg, self.drag = self.drag, None
        if tg and hasattr(tg.obj, "release"):
            tg.obj.release(e.x, e.y)
        self.on_motion(e)

    # ---- atualização ao vivo
    def worker(self):
        from .detector import get_states
        last, last_tools = None, None
        while self.alive:
            try:
                if self.PAGES[self.page_idx][0] in ("overview", "how") or last is None:
                    st = get_states()
                    tools = (tuple(sorted(settings.get()["tools"].items())),
                             tuple(sorted(settings.get()["skins"].items())))
                    if st != last or tools != last_tools or getattr(self, "states_dirty", False) \
                            or getattr(self, "lang_seen", None) != settings.get()["lang"]:
                        self.states_dirty = False
                        self.lang_seen = settings.get()["lang"]
                        img = render(st).resize(getattr(self, "preview_size", (560, 315)), Image.LANCZOS)
                        img = img.convert("RGBA")
                        mask = Image.new("L", (img.width * 3, img.height * 3), 0)
                        ImageDraw.Draw(mask).rounded_rectangle([0, 0, mask.width - 1, mask.height - 1],
                                                               radius=px(10) * 3, fill=255)
                        img.putalpha(mask.resize(img.size, Image.LANCZOS))
                        self.q.put((st, img))
                        last, last_tools = st, tools
            except Exception:  # noqa: BLE001
                log("worker: " + traceback.format_exc().replace("\n", " | "))
            self.wake.wait(3)
            self.wake.clear()

    def poll(self):
        try:
            while True:
                st, img = self.q.get_nowait()
                self.states = st
                if self.page and self.PAGES[self.page_idx][0] == "overview" and self.preview_item:
                    self._paint_chips()
                    self._crossfade(img)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        if self.alive:
            self.root.after(120, self.poll)

    def _crossfade(self, new):
        old = self.preview_img
        self.preview_img = new
        if old is None or old.size != new.size:
            self.preview_photo = ImageTk.PhotoImage(new)
            self.c.itemconfigure(self.preview_item, image=self.preview_photo)
            return

        def step(e):
            self.preview_photo = ImageTk.PhotoImage(Image.blend(old, new, e))
            self.c.itemconfigure(self.preview_item, image=self.preview_photo)

        self.anim.run("preview", 360, step, ease=in_out)

    def pulse(self):
        if not self.alive:
            return
        try:
            if self.live_dot and self.PAGES[self.page_idx][0] in ("overview", "how"):
                k = (1 + __import__("math").sin(time.perf_counter() * 3)) / 2
                self.c.itemconfigure(self.live_dot, image=circle(px(8), mix((40, 90, 62), GREEN, q(k, 8))))
        except tk.TclError:
            return
        self.root.after(70, self.pulse)


class SkinHit:
    """Clique em um visual de mascote."""

    def __init__(self, app, tool, skin_id):
        self.app, self.tool, self.skin_id = app, tool, skin_id

    def enter(self):
        pass

    def leave(self):
        pass

    def press(self, _x, _y):
        if self.app.cfg["skins"][self.tool] != self.skin_id:
            self.app.set_skin(self.tool, self.skin_id)


class TemplateHit:
    """Clique em um modelo: seleciona se ja existe, senao avisa que esta em breve."""

    def __init__(self, app, key, available):
        self.app, self.key, self.available = app, key, available

    def enter(self):
        pass

    def leave(self):
        pass

    def press(self, _x, _y):
        if not self.available:
            self.app.toast(t("tpl.soon_toast"), info=True)
        elif self.key != self.app.cfg["template"]:
            self.app.set_value("template", self.key)
            self.app.relang()  # redesenha a pagina com o novo modelo marcado


_tpl_cache = {}


def concept_preview(kind, w, h):
    """Desenhos de conceito dos modelos futuros (miniatura 16:9). Para um modelo novo, acrescente um ramo."""
    ss = 2
    W2, H2 = w * ss, h * ss
    img = Image.new("RGB", (W2, H2), BG)
    d = ImageDraw.Draw(img)
    cols = [ACC, TOOL_ACCENT["codex"], TOOL_ACCENT["cursor"]]
    if kind == "minimal":
        for i, c in enumerate(cols):
            cx, cy, r = W2 * (0.25 + 0.25 * i), H2 * 0.44, H2 * 0.085
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
            d.rounded_rectangle([cx - W2 * 0.07, H2 * 0.64, cx + W2 * 0.07, H2 * 0.67], radius=H2 * 0.02,
                                fill=(70, 70, 80))
    elif kind == "terminal":
        widths = [0.50, 0.34, 0.58, 0.28, 0.0]
        for i, wd in enumerate(widths):
            y = H2 * (0.17 + i * 0.15)
            x = W2 * 0.10
            d.line([(x, y - H2 * 0.03), (x + W2 * 0.03, y), (x, y + H2 * 0.03)], fill=cols[0], width=max(2, ss))
            if wd:
                d.rounded_rectangle([x + W2 * 0.07, y - H2 * 0.025, x + W2 * (0.07 + wd), y + H2 * 0.025],
                                    radius=H2 * 0.02, fill=cols[0] if i == 0 else (84, 84, 96))
            else:
                d.rectangle([x + W2 * 0.07, y - H2 * 0.04, x + W2 * 0.10, y + H2 * 0.04], fill=cols[0])
    elif kind == "panel":
        for i, (c, fill) in enumerate(zip(cols, (0.78, 0.44, 0.22))):
            y = H2 * (0.26 + i * 0.22)
            d.rounded_rectangle([W2 * 0.08, y - H2 * 0.025, W2 * 0.14, y + H2 * 0.025], radius=H2 * 0.02, fill=c)
            d.rounded_rectangle([W2 * 0.20, y - H2 * 0.04, W2 * 0.90, y + H2 * 0.04], radius=H2 * 0.04,
                                fill=(36, 36, 44))
            d.rounded_rectangle([W2 * 0.20, y - H2 * 0.04, W2 * (0.20 + 0.70 * fill), y + H2 * 0.04],
                                radius=H2 * 0.04, fill=c)
    return img.resize((w, h), Image.LANCZOS)


def template_preview(key, available, w, h):
    """Miniatura do modelo, com cantos arredondados (esmaecida se ainda nao existe)."""
    if (key, available, w, h) not in _tpl_cache:
        if key == "mascots":
            full = render({k: "working" for k in settings.TOOLS}, template="mascots")
            img = full.crop((240, 160, 1680, 970)).resize((w, h), Image.LANCZOS)  # recorte 16:9 nos mascotes
        elif key == "office":  # uma mesa em uso (luz acesa) ao lado de uma ociosa (em espera)
            full = render({"claude": "working", "codex": "open", "cursor": "closed", "gemini": "working"},
                          template="office")
            img = full.crop((40, 370, 1000, 910)).resize((w, h), Image.LANCZOS)  # as duas primeiras mesas
        elif key == "scoreboard":  # tempos de exemplo, para a miniatura não depender do dia
            from .scoreboard import render_board
            full = render_board({"claude": "working", "codex": "open", "cursor": "closed", "gemini": "working"},
                                totals={"claude": 12300, "codex": 2820, "cursor": 0, "gemini": 5400})
            img = full.crop((200, 225, 1720, 1080)).resize((w, h), Image.LANCZOS)
        else:
            img = concept_preview(key, w, h)
        if not available:
            img = Image.blend(img, Image.new("RGB", img.size, BG), 0.45)
        img = img.convert("RGBA")
        mask = Image.new("L", (w * 3, h * 3), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * 3 - 1, h * 3 - 1], radius=px(8) * 3, fill=255)
        img.putalpha(mask.resize((w, h), Image.LANCZOS))
        _tpl_cache[(key, available, w, h)] = img
    return _tpl_cache[(key, available, w, h)]


class _ChromeGroup:
    """Grupo 'falso' para os alvos da barra lateral (sempre visível, sem deslocamento)."""
    visible, ox, oy = True, 0, 0


class NavHit:
    def __init__(self, app, item):
        self.app, self.item = app, item

    def _hov(self, to):
        a = self.item["h"]

        def step(e):
            self.item["h"] = a + (to - a) * e
            self.app._paint_nav()

        self.app.anim.run(f"nv{self.item['i']}", 160, step)

    def enter(self):
        self._hov(1.0)

    def leave(self):
        self._hov(0.0)

    def press(self, _x, _y):
        self.app.show_page(self.item["i"])


# ------------------------------------------------------------------ janela
def already_open():
    """True se outra janela de configurações já está aberta (e a traz para a frente)."""
    plat = platforms.current()
    if plat.single_instance("LockscreenAgentsSettings"):
        return False
    plat.focus_window(t("ui.title"))
    return True


def main():
    global S
    shots = None
    if "--shot" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shot") + 1])
        shots.mkdir(parents=True, exist_ok=True)
    elif already_open():
        return
    plat = platforms.current()
    plat.init_ui_process("LockscreenAgents.Settings")
    root = tk.Tk()
    S = plat.ui_scale(root)
    root.title(t("ui.title"))
    root.configure(bg=hexc(BG))
    root.resizable(False, False)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = px(W), px(H)
    root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - px(20))}")
    try:
        root._icons = [ImageTk.PhotoImage(logo(n)) for n in (256, 64, 32)]  # guarda a referência
        root.iconphoto(True, *root._icons)
    except Exception:  # noqa: BLE001
        pass
    root.attributes("-alpha", 0.0)
    root.report_callback_exception = lambda *a: log("erro: " + "".join(traceback.format_exception(*a)))
    root.update_idletasks()
    plat.style_window(root, BG, TEXT, BG)
    app = SettingsApp(root)

    def fade(to, done=None):
        a = float(root.attributes("-alpha"))
        app.anim.run("fade", 220, lambda e: root.attributes("-alpha", a + (to - a) * e), done=done)

    def close():
        app.alive = False
        fade(0.0, root.destroy)

    root.protocol("WM_DELETE_WINDOW", close)
    fade(1.0)
    if shots:
        root.geometry(f"+{max(0, (sw - w) // 2)}+0")  # longe da barra de tarefas (evita pegar miniaturas dela)
        root.attributes("-topmost", True)
        root.after(900, lambda: shoot(root, app, shots, 0))
    root.mainloop()


def shoot(root, app, folder, i):
    """Modo de teste: tira uma foto da janela de cada página e fecha."""
    if i >= len(app.PAGES):
        app.alive = False
        root.destroy()
        return
    app.show_page(i)
    root.after(2600 if i == 0 else 1400, lambda: _grab(root, app, folder, i))


def _grab(root, app, folder, i):
    from PIL import ImageGrab
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(
        folder / f"{i}-{app.PAGES[i][0]}.png")
    shoot(root, app, folder, i + 1)


if __name__ == "__main__":
    main()
