"""Gera a imagem da lock screen: ferramenta ativa em cor, as outras em preto e branco."""
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from . import platforms

W, H = 1920, 1080
BG = (14, 14, 16)
CLAUDE_ORANGE = (204, 122, 94)  # laranja chapado, sem sombreado (igual à referência)
EYE = (0, 0, 0)
STEEL = (186, 194, 206)  # chave inglesa
STEEL_DARK = (70, 74, 84)
CODEX_BLUE = (66, 103, 214)
CODEX_SCREEN = (24, 28, 56)
CODEX_GLYPH = (160, 228, 244)
CODEX_CHEST = (214, 222, 244)
CODEX_ARM = (96, 134, 240)
ACCENT = {"claude": CLAUDE_ORANGE, "codex": (122, 160, 255), "cursor": (230, 230, 235)}


def draw_claude(size=300, step=None, blink=False, tool=True):
    """Clawd, o mascote do Claude Code, em pixel art chapada.

    Grade de 14x10 células. O mascote (medido na imagem de referência):
      corpo 8x6, bracinhos 2x2 nas laterais, olhos 1x1 e quatro pernas 1x2.
    `step` alterna braços e pernas (caminhada); `blink` achata os olhos;
    `tool` põe uma chave inglesa na mão esquerda (lado esquerdo da imagem) = trabalhando.
    """
    cols, rows = 14, 10
    ox, oy = 1, 2  # margem à esquerda (chave inglesa) e em cima
    px = max(1, size // cols)
    img = Image.new("RGBA", (cols * px, rows * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1, color, left=ox, top=oy):  # coords inclusivas, em células
        d.rectangle([(x0 + left) * px, (y0 + top) * px,
                     (x1 + 1 + left) * px - 1, (y1 + 1 + top) * px - 1], fill=color)

    walking = step is not None
    ay_l, ay_r = ((2, 3) if step % 2 else (3, 2)) if walking else (2, 2)

    # chave inglesa (desenhada ANTES do braço, para a mão ficar na frente do cabo)
    if tool:
        dy = ay_l - 2  # acompanha o braço esquerdo
        box(0, 1 + dy, 0, 1 + dy, STEEL, 0, 0)       # mandíbula esquerda
        box(2, 1 + dy, 2, 1 + dy, STEEL, 0, 0)       # mandíbula direita
        box(0, 2 + dy, 2, 3 + dy, STEEL, 0, 0)       # cabeça (bloco grosso, boca aberta em cima)
        box(1, 4 + dy, 1, 7 + dy, STEEL, 0, 0)       # cabo
        box(0, 8 + dy, 2, 8 + dy, STEEL, 0, 0)       # ponta arredondada do cabo
        box(1, 8 + dy, 1, 8 + dy, STEEL_DARK, 0, 0)  # furinho na ponta

    # corpo
    box(2, 0, 9, 5, CLAUDE_ORANGE)
    # bracinhos (o esquerdo segura a chave)
    box(0, ay_l, 1, ay_l + 1, CLAUDE_ORANGE)
    box(10, ay_r, 11, ay_r + 1, CLAUDE_ORANGE)
    # olhos (piscando = faixa fina na parte de baixo da célula)
    for ex in (3, 8):
        if blink:
            d.rectangle([(ex + ox) * px, int((1.6 + oy) * px),
                         (ex + ox + 1) * px - 1, int((2 + oy) * px) - 1], fill=EYE)
        else:
            box(ex, 1, ex, 1, EYE)
    # pernas: pares alternados levantam (ficam com 1 célula) a cada passo
    for i, x in enumerate((2, 4, 7, 9)):
        up = walking and (i % 2) == (step % 2)
        box(x, 6, x, 6 if up else 7, CLAUDE_ORANGE)
    return img


def draw_codex(size=300, step=None, blink=False):
    """Mascote do Codex em pixel art: cabeça de nuvem com tela de terminal (>_),
    corpinho com um >_ no peito, bracinhos e pezinhos.

    Grade de 14x15 células. `step` alterna braços e pés (caminhada);
    `blink` apaga o cursor `_` da tela (cursor piscando = trabalhando).
    """
    cols, rows = 14, 15
    px = max(1, size // rows)
    img = Image.new("RGBA", (cols * px, rows * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1, color):  # coordenadas inclusivas, em células
        d.rectangle([x0 * px, y0 * px, (x1 + 1) * px - 1, (y1 + 1) * px - 1], fill=color)

    walking = step is not None

    # cabeça de nuvem: intervalos (x0, x1) preenchidos em cada linha
    head = [
        [(3, 4), (6, 7), (9, 10)],  # três "bolhas" no topo
        [(1, 12)],
        [(0, 13)],
        [(0, 13)],
        [(1, 12)],                  # reentrâncias laterais (nuvem)
        [(0, 13)],
        [(0, 13)],
        [(1, 12)],
        [(2, 11)],
        [(3, 10)],
    ]
    for y, spans in enumerate(head):
        for x0, x1 in spans:
            box(x0, y, x1, y, CODEX_BLUE)

    # tela do terminal
    box(2, 3, 11, 7, CODEX_SCREEN)
    for x, y in ((4, 4), (5, 5), (4, 6)):        # >
        box(x, y, x, y, CODEX_GLYPH)
    if not blink:
        box(8, 6, 9, 6, CODEX_GLYPH)              # _ (cursor)

    # corpinho com >_ no peito
    box(4, 10, 9, 12, CODEX_BLUE)
    box(5, 11, 5, 11, CODEX_CHEST)
    box(7, 11, 8, 11, CODEX_CHEST)

    # bracinhos
    ay_l, ay_r = ((10, 11) if step % 2 else (11, 10)) if walking else (10, 10)
    box(3, ay_l, 3, ay_l + 1, CODEX_ARM)
    box(10, ay_r, 10, ay_r + 1, CODEX_ARM)

    # pezinhos (um levanta a cada passo)
    for i, x in enumerate((4, 8)):
        up = walking and (i % 2) == (step % 2)
        box(x, 13, x + 1, 13 if up else 14, CODEX_BLUE)
    return img


def _cursor_simple(size):
    """Cursor ocioso: o cubo simples, de três faces."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    top = [(0.50 * s, 0.06 * s), (0.92 * s, 0.30 * s), (0.50 * s, 0.50 * s), (0.08 * s, 0.30 * s)]
    left = [(0.08 * s, 0.30 * s), (0.50 * s, 0.50 * s), (0.50 * s, 0.96 * s), (0.08 * s, 0.72 * s)]
    right = [(0.92 * s, 0.30 * s), (0.50 * s, 0.50 * s), (0.50 * s, 0.96 * s), (0.92 * s, 0.72 * s)]
    d.polygon(top, fill=(245, 245, 245))
    d.polygon(left, fill=(150, 150, 150))
    d.polygon(right, fill=(200, 200, 200))
    return img


# Logo do Cursor medido na imagem de referência (400x400): hexágono com um cubo "aberto".
_CUR = {
    "T": (200, 62), "UR": (327, 131), "LR": (327, 270),
    "B": (200, 340), "LL": (73, 270), "UL": (73, 131),
    "Q": (200, 214), "M": (268, 238),
}


def _grad_fill(canvas, pts, c0, c1, direction):
    """Preenche o polígono `pts` com um gradiente c0→c1 ('v' = cima→baixo, 'h' = esquerda→direita)."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = int(min(xs)), int(min(ys))
    x1, y1 = int(max(xs)) + 1, int(max(ys)) + 1
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    g = Image.linear_gradient("L")  # preto em cima → branco embaixo
    if direction == "h":
        g = g.rotate(90)            # preto à esquerda → branco à direita
    g = g.resize((w, h))
    fill = Image.composite(Image.new("RGBA", (w, h), c1 + (255,)),
                           Image.new("RGBA", (w, h), c0 + (255,)), g)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    canvas.paste(fill, (x0, y0), mask.crop((x0, y0, x1, y1)))


def _cursor_detailed(size, glow):
    """Cursor ativo: o cubo do logo, com facetas em degradê e um brilho que pulsa (glow 0..1)."""
    S = 3  # supersampling para bordas suaves
    big = size * S
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    f = big * 0.80 / 278  # escala do logo (altura do hexágono = 278)
    ox, oy = big / 2 - 200 * f, big / 2 - 201 * f
    P = {k: (ox + x * f, oy + y * f) for k, (x, y) in _CUR.items()}

    if glow > 0:  # halo branco suave atrás do cubo
        halo = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        hexa = [P[k] for k in ("T", "UR", "LR", "B", "LL", "UL")]
        ImageDraw.Draw(halo).polygon(hexa, fill=(255, 255, 255, int(110 * glow)))
        halo = halo.filter(ImageFilter.GaussianBlur(big * 0.045))
        img = Image.alpha_composite(img, halo)

    # tampa superior (escura) e as faces do "cubo aberto"
    _grad_fill(img, [P["T"], P["UR"], P["UL"]], (92, 92, 96), (30, 30, 34), "h")
    _grad_fill(img, [P["UR"], P["LR"], P["B"], P["M"]], (34, 34, 38), (118, 118, 122), "v")
    _grad_fill(img, [P["UL"], P["Q"], P["LL"]], (48, 48, 52), (112, 112, 116), "v")
    _grad_fill(img, [P["LL"], P["Q"], P["B"]], (150, 150, 154), (226, 226, 230), "h")
    _grad_fill(img, [P["UR"], P["M"], P["B"], P["Q"]], (244, 244, 246), (208, 208, 212), "h")
    _grad_fill(img, [P["UL"], P["UR"], P["Q"]], (255, 255, 255), (234, 234, 238), "v")  # facete branca
    return img.resize((size, size), Image.LANCZOS)


def draw_cursor(size=300, active=False, glow=0.0):
    """Mascote do Cursor: cubo simples quando ocioso; cubo detalhado do logo quando ativo."""
    return _cursor_detailed(size, glow) if active else _cursor_simple(size)


def _gray(img, dim=0.55, alpha=0.8):
    a = img.split()[3]
    g = ImageEnhance.Color(img.convert("RGB")).enhance(0.0)
    g = ImageEnhance.Brightness(g).enhance(dim)
    g.putalpha(a.point(lambda v: int(v * alpha)))
    return g


def state_of(status, key):
    """Normaliza o estado: 'working' | 'open' | 'closed' (aceita também True/False)."""
    st = status.get(key, "open")
    if st is True:
        return "working"
    if st is False:
        return "open"
    return st


def _font(size):
    for name in platforms.current().FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(status, step=None, size=(W, H)):
    """status: {'claude': 'working'|'open'|'closed'|'off', ...} (aceita também True/False).
    Ferramentas 'off' (desligadas nas configurações) não aparecem e o resto se recentraliza."""
    from .i18n import t
    w, h = size
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    logo = 300
    gap = 140
    keys = [k for k in ("claude", "codex", "cursor") if state_of(status, k) != "off"]
    total = len(keys) * logo + (len(keys) - 1) * gap
    x0 = (w - total) // 2
    y0 = (h - logo) // 2 - 40
    makers = {
        "claude": lambda: draw_claude(logo, step, tool=state_of(status, "claude") == "working"),
        "codex": lambda: draw_codex(logo, step),
        "cursor": lambda: draw_cursor(logo, active=state_of(status, "cursor") == "working", glow=0.6),
    }
    for i, key in enumerate(keys):
        label, logo_img = t("tool." + key), makers[key]()
        x = x0 + i * (logo + gap)
        st = state_of(status, key)
        active = st == "working"
        if st == "working":
            pic = logo_img
        elif st == "open":
            pic = _gray(logo_img)
        else:  # fechado: bem apagado
            pic = _gray(logo_img, dim=0.25, alpha=0.5)
        # centraliza o logo (o caranguejo não é quadrado)
        px = x + (logo - pic.width) // 2
        py = y0 + (logo - pic.height) // 2
        # tira o caranguejo pro chão quando ativo (leve "saltinho" conforme o frame)
        if active and key == "claude":
            py -= 14 if step and step % 2 else 0
        img.paste(pic, (px, py), pic)
        font = _font(34)
        color = (235, 235, 235) if active else ((95, 95, 100) if st == "open" else (52, 52, 56))
        tw = d.textlength(label, font=font)
        d.text((x + (logo - tw) / 2, y0 + logo + 40), label, fill=color, font=font)
        state = t("state." + st) if st in ("working", "open", "closed") else t("state.open")
        sfont = _font(24)
        sw = d.textlength(state, font=sfont)
        d.text((x + (logo - sw) / 2, y0 + logo + 90), state,
               fill=ACCENT.get(key, CLAUDE_ORANGE) if active else ((70, 70, 75) if st == "open" else (45, 45, 48)),
               font=sfont)
    return img


if __name__ == "__main__":
    import sys
    render({"claude": True, "codex": False, "cursor": False}).save("preview.png")
    print("preview.png gerado", file=sys.stderr)
