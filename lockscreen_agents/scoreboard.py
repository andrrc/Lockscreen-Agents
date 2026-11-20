"""Modelo "Placar": quanto tempo cada ferramenta ficou em uso hoje, num placar de estádio.

Cada ferramenta é um "time" com o mascote, o nome e o tempo (horas:minutos) em dígitos de sete
segmentos; os segmentos apagados continuam aparecendo bem fracos, como num placar de verdade.
Quem está em uso acende na cor da ferramenta, com os dois-pontos piscando; quem lidera o dia ganha
uma coroa. A moldura tem lâmpadas que correm (no protetor) enquanto alguma ferramenta está em uso.

Os tempos vêm de `history.today()`. Tudo é desenhado numa grade de unidades (`u` px), como a
pixel-art dos mascotes. A mesma função faz a imagem da tela de bloqueio e os quadros do protetor.
"""
from PIL import Image, ImageDraw, ImageTk

from . import history, settings
from .render import ACCENT, BG, H, W, _font, _gray, draw_claude, draw_codex, draw_cursor, draw_gemini, state_of

KEYS = ("claude", "codex", "cursor", "gemini")
TEAM = 30      # largura de cada time, em unidades
MARGIN = 3     # margem interna do placar
ROWS = 37      # altura do placar
PANEL = (9, 9, 11)
FRAME = (36, 36, 44)
DIVIDER = (24, 24, 30)
GHOST = (27, 27, 33)
BULB_ON = (255, 214, 128)
BULB_OFF = (58, 56, 52)
GOLD = (240, 196, 86)
TITLE = (118, 118, 128)
LIT = {"open": (150, 150, 158), "closed": (84, 84, 90)}
NAME = {"working": (235, 235, 235), "open": (130, 130, 136), "closed": (70, 70, 76)}
STATE = {"open": (90, 90, 96), "closed": (58, 58, 62)}
CROWN = ["G.G.G", "GGGGG", "GGGGG"]

# sete segmentos numa grade 5x9: a (topo), b, c (direita), d (base), e, f (esquerda), g (meio)
SEGMENTS = {"a": (1, 0, 3, 0), "b": (4, 1, 4, 3), "c": (4, 5, 4, 7), "d": (1, 8, 3, 8),
            "e": (0, 5, 0, 7), "f": (0, 1, 0, 3), "g": (1, 4, 3, 4)}
DIGITS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg",
          "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def clock(seconds):
    """Segundos -> 'HH:MM' (no máximo 99:59)."""
    minutes = min(int(seconds // 60), 99 * 60 + 59)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def layout(w, h, n):
    """Geometria do placar para uma tela `w`x`h` com `n` times (px, relativo ao canto da tela)."""
    cols = n * TEAM + 2 * MARGIN
    u = max(2, int(min(w * 0.92 / cols, h / 90)))
    return {"u": u, "x0": (w - cols * u) // 2, "y0": int(h * 0.42), "w": cols * u, "h": ROWS * u}


def _boxer(d, ox, oy, u):
    def box(x0, y0, x1, y1, color):  # coordenadas inclusivas, em unidades
        d.rectangle([int(ox + x0 * u), int(oy + y0 * u), int(ox + (x1 + 1) * u) - 1, int(oy + (y1 + 1) * u) - 1],
                    fill=color)
    return box


def _digits(box, x, y, text, color, colon_on):
    """Desenha 'HH:MM' a partir de (x, y) em unidades. O zero à esquerda das horas fica apagado."""
    for i, ch in enumerate(text):
        if ch == ":":
            for dy in (2, 6):
                box(x, y + dy, x, y + dy, color if colon_on else GHOST)
            x += 2
            continue
        lit = "" if (i == 0 and ch == "0") else DIGITS[ch]
        for seg, (x0, y0, x1, y1) in SEGMENTS.items():
            box(x + x0, y + y0, x + x1, y + y1, color if seg in lit else GHOST)
        x += 6


def _mascot(key, st, size):
    skin = settings.get()["skins"][key]
    working = st == "working"
    if key == "claude":
        img = draw_claude(size, tool=working, skin=skin)
    elif key == "codex":
        img = draw_codex(size, tool=working, skin=skin)
    elif key == "gemini":
        img = draw_gemini(size, tool=working, skin=skin)
    else:
        img = draw_cursor(size, active=working, glow=0.6, skin=skin)
    if working:
        return img
    return _gray(img) if st == "open" else _gray(img, dim=0.25, alpha=0.5)


def render_board(status, size=(W, H), totals=None, colon=True, phase=0):
    """Imagem do placar. `totals` = {'claude': segundos, ...} (sem ele, lê o histórico de hoje);
    `colon` acende os dois-pontos de quem está em uso; `phase` (0..2) move as lâmpadas da moldura."""
    from .i18n import t
    totals = history.today() if totals is None else totals
    w, h = size
    img = Image.new("RGB", (w, h), BG)
    keys = [k for k in KEYS if state_of(status, k) != "off"]
    lay = layout(w, h, len(keys))
    u, ox, oy = lay["u"], lay["x0"], lay["y0"]
    d = ImageDraw.Draw(img)
    box = _boxer(d, ox, oy, u)
    cols = len(keys) * TEAM + 2 * MARGIN
    states = {k: state_of(status, k) for k in keys}
    any_working = any(st == "working" for st in states.values())
    # moldura com lâmpadas (acesas em sequência enquanto alguém trabalha) e o painel
    box(0, 0, cols - 1, ROWS - 1, FRAME)
    box(1, 1, cols - 2, ROWS - 2, PANEL)
    sbox = _boxer(d, ox, oy, u / 2)
    perimeter = [(x, 0) for x in range(1, cols * 2 - 1, 3)] + [(x, ROWS * 2 - 1) for x in range(1, cols * 2 - 1, 3)]
    perimeter += [(0, y) for y in range(4, ROWS * 2 - 3, 3)] + [(cols * 2 - 1, y) for y in range(4, ROWS * 2 - 3, 3)]
    for i, (x, y) in enumerate(perimeter):
        on = any_working and (i + phase) % 3 == 0
        sbox(x, y, x, y, BULB_ON if on else BULB_OFF)
    title = t("board.title").upper()
    tfont = _font(max(10, round(u * 1.7)))
    d.text((ox + lay["w"] / 2 - d.textlength(title, font=tfont) / 2, oy + 2.2 * u), title, fill=TITLE, font=tfont)
    box(MARGIN, 5, cols - 1 - MARGIN, 5, DIVIDER)
    leader = max(keys, key=lambda k: totals.get(k, 0), default=None)
    if leader and totals.get(leader, 0) < 60:
        leader = None  # ninguém passou de um minuto: sem coroa
    nfont, sfont = _font(max(10, round(u * 2.3))), _font(max(9, round(u * 1.7)))
    for i, key in enumerate(keys):
        st = states[key]
        tx = MARGIN + i * TEAM  # início do time, em unidades
        cx = ox + (tx + TEAM / 2) * u
        if i:
            box(tx, 8, tx, ROWS - 4, DIVIDER)
        pic = _mascot(key, st, 8 * u)
        img.paste(pic, (int(cx - pic.width / 2), int(oy + 16 * u - pic.height)), pic)
        if key == leader:
            for y, row in enumerate(CROWN):
                for x, ch in enumerate(row):
                    if ch != ".":
                        cb = _boxer(d, cx + 4.5 * u, oy + 8.5 * u, u * 0.8)
                        cb(x, y, x, y, GOLD)
        name = t("tool." + key)
        d.text((cx - d.textlength(name, font=nfont) / 2, oy + 17.2 * u), name, fill=NAME[st], font=nfont)
        color = ACCENT[key] if st == "working" else LIT[st]
        _digits(box, tx + 2.5, 22, clock(totals.get(key, 0)), color, colon or st != "working")
        state = t("state." + st)
        d.text((cx - d.textlength(state, font=sfont) / 2, oy + 32.4 * u), state,
               fill=ACCENT[key] if st == "working" else STATE[st], font=sfont)
    return img


class Scene:
    """O placar num monitor do protetor de tela (mesma interface do `saver.Scene`)."""

    def __init__(self, canvas, rect, origin):
        left, top, right, bottom = rect
        self.canvas = canvas
        self.x0, self.y0 = left - origin[0], top - origin[1]
        self.size = (right - left, bottom - top)
        self.keys = [k for k in KEYS if settings.get()["tools"].get(k, True)]
        self.status = {k: "open" for k in self.keys}
        self.totals = history.today()
        self.data_key = None
        self.cache = {}
        self.item = canvas.create_image(self.x0, self.y0, anchor="nw")

    def apply_status(self, status):
        self.status = {k: status.get(k, "open") for k in self.keys}
        self.totals = history.today()

    def tick(self, frame):
        minutes = {k: int(self.totals.get(k, 0) // 60) for k in self.keys}
        data = (tuple(sorted(self.status.items())), tuple(sorted(minutes.items())))
        if data != self.data_key:  # mudou estado ou minuto: os quadros antigos não servem mais
            self.data_key, self.cache = data, {}
        colon, phase = (frame // 15) % 2 == 0, (frame // 8) % 3
        k = (colon, phase)
        if k not in self.cache:
            img = render_board(self.status, self.size, self.totals, colon, phase)
            self.cache[k] = ImageTk.PhotoImage(img)
        self.canvas.itemconfig(self.item, image=self.cache[k])
