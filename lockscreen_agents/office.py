"""Modelo "Escritório": cada mascote sentado na sua mesa, com monitor, cadeira e luminária.

Em uso, a luminária acende (com a luz na cor da ferramenta), o monitor mostra código rolando e o
mascote digita. Ocioso, a luz apaga, o monitor fica em espera e o café solta fumaça na mesa.
Fechado, a mesa fica escura e a cadeira vazia.

Tudo é desenhado numa grade de "unidades" (`u` px), igual à pixel-art dos mascotes. A mesa tem 44
unidades de largura; a coordenada y 0 é o tampo da mesa (negativo = para cima). As mesmas funções
servem para a imagem da tela de bloqueio (`render_office`) e para o protetor de tela (`Scene`).
"""
import math
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk

from . import settings
from .render import ACCENT, H, W, _font, _gray, draw_claude, draw_codex, draw_cursor, draw_gemini, state_of

KEYS = ("claude", "codex", "cursor", "gemini")
COLS = 44          # largura de uma mesa, em unidades
MASCOT_X = 11      # centro do mascote na mesa
FRONT_TOP = -11    # a camada da frente (mesa, monitor, planta) vai de y -11 a 11
FLOOR = 12         # o chão começa 12 unidades abaixo do tampo

WALL = (19, 19, 23)
FLOOR_C = (12, 12, 14)
BASEBOARD = (30, 30, 36)
WOOD_TOP = (124, 88, 62)
WOOD = (92, 64, 46)
WOOD_DARK = (62, 43, 32)
METAL = (58, 60, 70)
CHAIR = (40, 42, 52)
CHAIR_TOP = (60, 62, 74)
LAMP = (48, 50, 58)
BULB_ON = (255, 238, 204)
BULB_OFF = (70, 70, 76)
CORD = (34, 34, 40)
MON_FRAME = (36, 38, 46)
SCREEN_ON = (14, 18, 28)
SCREEN_IDLE = (20, 22, 28)
SCREEN_OFF = (8, 8, 10)
CODE_GRAY = (78, 84, 100)
CODE_LIGHT = (188, 194, 208)
LED_ON = (96, 206, 128)
LED_OFF = (40, 40, 44)
MUG = (218, 224, 236)
MUG_SHADE = (176, 186, 206)
COFFEE = (92, 54, 34)
STEAM = (150, 156, 170)
POT = (134, 78, 56)
POT_DARK = (102, 58, 42)
LEAF = (52, 104, 70)
LEAF_LIGHT = (76, 136, 92)

# Linhas de "código" do monitor: (recuo, comprimento, cor) em meias unidades. 'a' = cor da ferramenta.
CODE = [(0, 9, "a"), (2, 14, "g"), (2, 10, "w"), (4, 12, "g"), (4, 7, "a"), (2, 16, "g"),
        (0, 5, "w"), (0, 11, "a"), (2, 8, "g"), (2, 13, "w")]
CODE_PHASES = len(CODE)
IDLE_PHASES = 8
LIGHT = {"working": 1.0, "open": 0.72, "closed": 0.5}  # quanto a mesa fica iluminada em cada estado


def _mix(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def _dim(c, f):
    return _mix(WALL, c, f)


def layout(w, h, n):
    """Geometria da sala para uma tela `w`x`h` com `n` mesas (px, relativo ao canto da tela)."""
    u = max(2, int(min(w * 0.94 / max(1, n) / COLS, h / 90)))
    slot = COLS * u
    desk = int(h * 0.62)
    return {"u": u, "slot": slot, "x0": (w - n * slot) // 2, "desk": desk, "floor": desk + FLOOR * u}


def _boxer(d, ox, oy, u):
    """Retângulos em unidades (inclusivos), com (ox, oy) = canto esquerdo do tampo da mesa."""
    def box(x0, y0, x1, y1, color):
        d.rectangle([int(ox + x0 * u), int(oy + y0 * u), int(ox + (x1 + 1) * u) - 1, int(oy + (y1 + 1) * u) - 1],
                    fill=color)
    return box


def paint_room(img, lay, top=0):
    """Parede, rodapé e chão (a imagem já vem pintada com a cor da parede)."""
    d = ImageDraw.Draw(img)
    floor = top + lay["floor"]
    d.rectangle([0, floor, img.width, img.height], fill=FLOOR_C)
    d.rectangle([0, floor, img.width, floor + max(2, lay["u"] // 2)], fill=BASEBOARD)


def paint_back(img, ox, desk, u, key, st):
    """O que fica atrás do mascote: luz da luminária, a luminária e a cadeira. `desk` = y do tampo (px)."""
    if st == "working":  # cone de luz na cor da ferramenta, com bordas suaves
        x0, y0 = int(ox), max(0, int(desk - 24 * u))
        x1, y1 = int(ox + COLS * u), min(img.height, int(desk + FLOOR * u))
        region = img.crop((x0, y0, x1, y1)).convert("RGBA")
        cone = Image.new("RGBA", region.size, (0, 0, 0, 0))
        top = desk - 21 * u - y0
        ImageDraw.Draw(cone).polygon(
            [(18 * u, top), (26 * u, top), (COLS * u, desk + FLOOR * u - y0), (0, desk + FLOOR * u - y0)],
            fill=ACCENT[key] + (38,))
        cone = cone.filter(ImageFilter.GaussianBlur(u * 1.4))
        img.paste(Image.alpha_composite(region, cone).convert("RGB"), (x0, y0))
    d = ImageDraw.Draw(img)
    box = _boxer(d, ox, desk, u)
    f = LIGHT.get(st, LIGHT["open"])
    # luminária pendurada no teto
    cw = max(2, u // 4)
    cx = ox + 22 * u
    d.rectangle([cx - cw // 2, 0, cx + cw - cw // 2 - 1, desk - 24 * u], fill=CORD)
    box(20, -24, 23, -24, _dim(LAMP, f))
    box(19, -23, 24, -23, _dim(LAMP, f))
    box(18, -22, 25, -22, _dim(LAMP, f))
    box(21, -21, 22, -21, BULB_ON if st == "working" else _dim(BULB_OFF, f))
    # cadeira: encosto (aparece por cima do mascote baixinho) e, embaixo da mesa, o pé com rodinhas
    box(5, -9, 17, -2, _dim(CHAIR, f))
    box(5, -9, 17, -9, _dim(CHAIR_TOP, f))
    box(10, 2, 12, 9, _dim(METAL, f))
    box(6, 9, 16, 9, _dim(METAL, f))
    for x in (6, 11, 16):
        box(x, 10, x, 10, _dim(CHAIR, f))


def _screen(box, sbox, key, st, phase, blink):
    """Conteúdo do monitor (tela de x 24..35, y -9..-5 em unidades; 24x10 em meias unidades)."""
    accent = ACCENT[key]
    if st == "working":
        box(24, -9, 35, -5, SCREEN_ON)
        colors = {"a": accent, "g": CODE_GRAY, "w": CODE_LIGHT}
        for i in range(4):
            indent, length, c = CODE[(phase + i) % len(CODE)]
            row = -18 + 1 + i * 2  # linhas 1, 3, 5, 7 da tela
            if i == 3:  # a última linha está sendo digitada: cresce a cada fase
                length = max(1, length * (1 + phase % 3) // 3)
            sbox(48 + 1 + indent, row, 48 + indent + length, row, colors[c])
            if i == 3 and not blink:
                sbox(48 + 2 + indent + length, row - 1, 48 + 2 + indent + length, row, CODE_LIGHT)
    elif st == "open":  # em espera: um pontinho passeando devagar pela tela
        box(24, -9, 35, -5, SCREEN_IDLE)
        a = 2 * math.pi * phase / IDLE_PHASES
        x, y = 48 + 11 + round(math.cos(a) * 7), -18 + 4 + round(math.sin(a) * 2.5)
        sbox(x, y, x + 1, y + 1, _mix(SCREEN_IDLE, accent, 0.45))
    else:
        box(24, -9, 35, -5, SCREEN_OFF)
        sbox(49, -17, 50, -17, (26, 26, 30))  # reflexo na tela apagada


def desk_front(key, st, u, phase=0, blink=False):
    """Mesa, monitor, xícara e planta (RGBA, 44 x 23 unidades; o topo fica em y FRONT_TOP)."""
    img = Image.new("RGBA", (COLS * u, (FLOOR - FRONT_TOP) * u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    oy = -FRONT_TOP * u
    box = _boxer(d, 0, oy, u)
    sbox = _boxer(d, 0, oy, u / 2)  # meias unidades, para detalhes finos
    # tampo, perna e gaveteiro
    box(1, 0, 42, 0, WOOD_TOP)
    box(1, 1, 42, 1, WOOD)
    box(2, 2, 3, 11, WOOD_DARK)
    box(33, 2, 41, 11, WOOD)
    for y in (5, 8):
        box(33, y, 41, y, WOOD_DARK)
    for y in (3, 6, 9):
        box(36, y, 38, y, METAL)
    # monitor
    box(27, -1, 32, -1, METAL)
    box(29, -3, 30, -2, METAL)
    box(23, -10, 36, -4, MON_FRAME)
    _screen(box, sbox, key, st, phase, blink)
    sbox(70, -8, 70, -8, LED_OFF if st == "closed" else LED_ON)
    # xícara de café (some quando a ferramenta está fechada); ociosa, ela solta fumaça
    if st != "closed":
        box(19, -3, 21, -1, MUG)
        sbox(42, -2, 42, -1, MUG_SHADE)
        sbox(39, -6, 42, -6, COFFEE)
        sbox(44, -5, 44, -3, MUG)
        sbox(45, -5, 45, -3, MUG)
        if st == "open":
            sway = 1 if phase % 2 else 0
            for i, dy in enumerate((-8, -10, -12)):
                sbox(40 + sway + (i % 2), dy, 40 + sway + (i % 2), dy, STEAM)
    # planta no canto da mesa
    sbox(77, -3, 83, -3, POT_DARK)
    sbox(78, -2, 82, -1, POT)
    for x0, y0, x1, y1, c in ((79, -9, 80, -4, LEAF), (76, -8, 78, -5, LEAF_LIGHT), (81, -10, 83, -6, LEAF_LIGHT),
                              (82, -6, 84, -4, LEAF), (77, -5, 79, -4, LEAF)):
        sbox(x0, y0, x1, y1, c)
    f = LIGHT.get(st, LIGHT["open"])
    if f < 1:  # luz apagada: a mesa fica na penumbra
        alpha = img.split()[3]
        img = ImageEnhance.Brightness(img.convert("RGB")).enhance(f)
        img.putalpha(alpha)
    return img


def mascot(key, st, u, step=None, blink=False, glow=0.6):
    """O mascote sentado (colorido em uso, cinza ocioso). Fechado = cadeira vazia (None)."""
    if st == "closed":
        return None
    skin = settings.get()["skins"][key]
    size, working = 15 * u, st == "working"
    if key == "claude":
        img = draw_claude(size, step, blink, tool=working, skin=skin)
    elif key == "codex":
        img = draw_codex(size, step, blink, tool=working, skin=skin)
    elif key == "gemini":
        img = draw_gemini(size, step, blink, tool=working, skin=skin)
    else:
        img = draw_cursor(size, active=working, glow=glow, skin=skin)
    return img if working else _gray(img)


def _label_colors(key, st):
    name = (235, 235, 235) if st == "working" else ((95, 95, 100) if st == "open" else (52, 52, 56))
    state = ACCENT[key] if st == "working" else ((70, 70, 75) if st == "open" else (45, 45, 48))
    return name, state


def render_office(status, size=(W, H)):
    """Imagem da tela de bloqueio no modelo Escritório. Ferramentas 'off' não ganham mesa."""
    from .i18n import t
    w, h = size
    img = Image.new("RGB", (w, h), WALL)
    keys = [k for k in KEYS if state_of(status, k) != "off"]
    lay = layout(w, h, len(keys))
    u, desk = lay["u"], lay["desk"]
    paint_room(img, lay)
    d = ImageDraw.Draw(img)
    font, sfont = _font(round(h * 0.031)), _font(round(h * 0.022))
    for i, key in enumerate(keys):
        st = state_of(status, key)
        ox = lay["x0"] + i * lay["slot"]
        paint_back(img, ox, desk, u, key, st)
        pic = mascot(key, st, u)
        if pic:  # as pernas ficam atrás do tampo: a base do desenho fica 2 unidades abaixo dele
            img.paste(pic, (int(ox + MASCOT_X * u - pic.width / 2), desk + 2 * u - pic.height), pic)
        front = desk_front(key, st, u)
        img.paste(front, (ox, desk + FRONT_TOP * u), front)
        name_c, state_c = _label_colors(key, st)
        cx = ox + lay["slot"] / 2
        label = t("tool." + key)
        d.text((cx - d.textlength(label, font=font) / 2, lay["floor"] + h * 0.03), label, fill=name_c, font=font)
        state = t("state." + st) if st in ("working", "open", "closed") else t("state.open")
        d.text((cx - d.textlength(state, font=sfont) / 2, lay["floor"] + h * 0.075), state, fill=state_c,
               font=sfont)
    return img


# ------------------------------------------------------------------ protetor de tela (Tkinter)
def _hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


class Desk:
    """Uma mesa animada no protetor de tela: fundo (luz e cadeira), mascote e frente (mesa e monitor)."""

    def __init__(self, scene, idx, key):
        from .i18n import t
        self.scene, self.key = scene, key
        c, lay = scene.canvas, scene.lay
        u = lay["u"]
        self.ox = scene.x0 + lay["x0"] + idx * lay["slot"]
        self.desk = scene.y0 + lay["desk"]
        self.st = None
        self.cache = {}
        self.phase = random.uniform(0, 96)
        self.next_blink = random.randint(40, 160)
        self.blink_until = -1
        self.back = c.create_image(self.ox, scene.y0, anchor="nw")
        self.item = c.create_image(self.ox + MASCOT_X * u, self.desk + 2 * u, anchor="s")
        self.front = c.create_image(self.ox, self.desk + FRONT_TOP * u, anchor="nw")
        cx = self.ox + lay["slot"] / 2
        floor = scene.y0 + lay["floor"]
        fs = -max(14, int(scene.h * 0.031))
        self.name_t = c.create_text(cx, floor + scene.h * 0.05, text=t("tool." + key), font=("Segoe UI", fs))
        self.state_t = c.create_text(cx, floor + scene.h * 0.09, font=("Segoe UI", int(fs * 0.72)))

    def _photo(self, k, make):
        if k not in self.cache:
            img = make()
            self.cache[k] = ImageTk.PhotoImage(img) if img is not None else None
        return self.cache[k]

    def _back_image(self, st):
        lay = self.scene.lay
        img = Image.new("RGB", (lay["slot"], lay["floor"]), WALL)
        paint_back(img, 0, lay["desk"], lay["u"], self.key, st)
        return img

    def set_state(self, st):
        from .i18n import t
        st = st if st in ("working", "open", "closed") else "open"
        if st == self.st:
            return
        self.st = st
        c = self.scene.canvas
        c.itemconfig(self.back, image=self._photo(("back", st), lambda: self._back_image(st)))
        name_c, state_c = _label_colors(self.key, st)
        c.itemconfig(self.name_t, fill=_hex(name_c))
        c.itemconfig(self.state_t, text=t("state." + st), fill=_hex(state_c))

    def tick(self, frame):
        if self.st is None:
            return
        c, u, st, key = self.scene.canvas, self.scene.lay["u"], self.st, self.key
        if st == "working":
            phase, blink = (frame // 24) % CODE_PHASES, (frame // 15) % 2 == 1
        else:
            phase, blink = (frame // 30) % IDLE_PHASES, False
        c.itemconfig(self.front, image=self._photo(("front", st, phase, blink),
                                                   lambda: desk_front(key, st, u, phase, blink)))
        lift, step, eyes, glow = 0, None, False, 0
        if st == "working":
            if key == "cursor":  # o cubo pulsa o brilho
                glow = int((math.sin(frame * 0.07) + 1) / 2 * 5 + 0.5)
            else:
                step = (frame // 5) % 2  # bracinhos sobem e descem: digitando
                eyes = (frame // 15) % 2 == 1 if key == "codex" else (frame + hash(key)) % 170 in range(160, 166)
        elif st == "open":  # respira devagar e pisca de vez em quando
            breath = (math.sin((frame + self.phase) * 2 * math.pi / 120) + 1) / 2
            lift = breath * u * 0.35
            if key != "cursor":
                if frame >= self.next_blink:
                    self.blink_until = frame + 5
                    self.next_blink = frame + random.randint(90, 220)
                eyes = frame < self.blink_until
        img = self._photo(("mascot", st, step, eyes, glow),
                          lambda: mascot(key, st, u, step, eyes, glow=glow / 5))
        if img is None:
            c.itemconfig(self.item, state="hidden")
        else:
            c.itemconfig(self.item, image=img, state="normal")
            c.coords(self.item, self.ox + MASCOT_X * u, self.desk + 2 * u - lift)


class Scene:
    """A sala inteira num monitor (mesma interface do `saver.Scene`: apply_status e tick)."""

    def __init__(self, canvas, rect, origin):
        left, top, right, bottom = rect
        self.canvas = canvas
        self.x0, self.y0 = left - origin[0], top - origin[1]
        self.w, self.h = right - left, bottom - top
        tools = settings.get()["tools"]
        keys = [k for k in KEYS if tools.get(k, True)]
        self.lay = lay = layout(self.w, self.h, len(keys))
        floor = self.y0 + lay["floor"]
        canvas.create_rectangle(self.x0, self.y0, self.x0 + self.w, self.y0 + self.h, fill=_hex(WALL), outline="")
        canvas.create_rectangle(self.x0, floor, self.x0 + self.w, self.y0 + self.h, fill=_hex(FLOOR_C), outline="")
        canvas.create_rectangle(self.x0, floor, self.x0 + self.w, floor + max(2, lay["u"] // 2),
                                fill=_hex(BASEBOARD), outline="")
        self.desks = [Desk(self, i, k) for i, k in enumerate(keys)]

    def apply_status(self, status):
        for d in self.desks:
            d.set_state(status.get(d.key, "open"))

    def tick(self, frame):
        for d in self.desks:
            d.tick(frame)
