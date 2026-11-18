"""Gera a imagem da lock screen: ferramenta ativa em cor, as outras em preto e branco."""
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from . import platforms

W, H = 1920, 1080
BG = (14, 14, 16)
CLAUDE_ORANGE = (204, 122, 94)  # laranja chapado, sem sombreado (igual à referência)
EYE = (0, 0, 0)
STEEL = (186, 194, 206)  # chave inglesa
STEEL_DARK = (70, 74, 84)
# Xícara de café em pixel-art (estilo contorno escuro + sombra azulada). K contorno, W louça,
# S sombra, B café, L brilho do café, "." vazio. Cada letra é um "pixel" bem menor que a célula do mascote.
CUP_ART = [
    "...KKKKKK.....",
    "..KWWWWWWK....",
    ".KWWBBBBWWK...",
    ".KWBLBBBBWKKK.",
    ".KWWBBBBWWKWWK",
    ".KWWWWWWWSKW.K",
    ".KWWWWWWWSKW.K",
    ".KWWWWWWSSKKK.",
    "..KWWWWSSK....",
    "...KKKKKK.....",
]
CUP_COLORS = {"K": (54, 46, 56), "W": (250, 250, 252), "S": (200, 210, 230), "B": (92, 54, 34),
              "L": (146, 100, 68)}
STEAM = (214, 222, 234)
CODEX_BLUE = (66, 103, 214)
CODEX_SCREEN = (24, 28, 56)
CODEX_GLYPH = (160, 228, 244)
CODEX_CHEST = (214, 222, 244)
CODEX_ARM = (96, 134, 240)
# Gemini: degradê de cima para baixo (azul → roxo → rosado), uma cor por linha da estrela
GEMINI_STOPS = ((71, 150, 227), (145, 119, 199), (202, 102, 115))
GEMINI_SPARK = (226, 232, 255)
ACCENT = {"claude": CLAUDE_ORANGE, "codex": (122, 160, 255), "cursor": (230, 230, 235),
          "gemini": (164, 136, 238)}

# Chapéu de Natal (visual "santa"). R vermelho, D vermelho escuro, L brilho, W pompom e barra, V sombra branca.
HAT_ART = [
    "..........RRRRR.......",
    "........RRRRRRRRR.....",
    ".......RRRRRRRRRRR.WW.",
    "......LRRRRRRRRRRRWWWW",
    ".....LRRRRRRRRRRRRWWWW",
    "....LRRRRRRRRRRRRRDVV.",
    "...LRRRRRRRRRRRRRRDD..",
    "..WWWWWWWWWWWWWWWWWWW.",
    ".WWWWWWWWWWWWWWWWWWWWW",
    ".VVVVVVVVVVVVVVVVVVVVV",
]
HAT_COLORS = {"R": (212, 36, 46), "D": (160, 24, 36), "L": (238, 78, 82),
              "W": (250, 250, 252), "V": (212, 220, 234)}
HAT_W = 22  # colunas da arte


def _with_pixel_hat(img, cx, bottom_y, sub):
    """Põe o chapéu de Natal em pixel-art no mascote `img`, centralizado em `cx` e com a base da barra
    em `bottom_y` (px da imagem). `sub` é o tamanho de um "pixel" do chapéu. Se o chapéu passar do topo,
    a imagem ganha uma margem em cima (o mascote desce junto, então a base continua no mesmo lugar)."""
    hat_w, hat_h = HAT_W * sub, len(HAT_ART) * sub
    left, top = int(cx - hat_w / 2), int(bottom_y - hat_h)
    pad_l, pad_t = max(0, -left), max(0, -top)
    pad_r = max(0, left + hat_w - img.width)
    out = Image.new("RGBA", (img.width + pad_l + pad_r, img.height + pad_t), (0, 0, 0, 0))
    out.paste(img, (pad_l, pad_t), img)
    d = ImageDraw.Draw(out)
    for y, row in enumerate(HAT_ART):
        for x, ch in enumerate(row):
            if ch != ".":
                x0, y0 = left + pad_l + x * sub, top + pad_t + y * sub
                d.rectangle([x0, y0, x0 + sub - 1, y0 + sub - 1], fill=HAT_COLORS[ch])
    return out


def _draw_cup(d, hand_x, hand_cy, sub, wiggle):
    """Xícara de café em pixel-art. A alça fica na altura da mão (`hand_cy`) e encosta no braço
    (`hand_x`, borda esquerda dele). `sub` é o tamanho de um "pixel" da xícara; `wiggle` (-1 ou 1)
    é o lado para onde o vapor se inclina."""
    x0 = hand_x + sub - len(CUP_ART[0]) * sub
    y0 = int(hand_cy - 5.5 * sub)
    for y, row in enumerate(CUP_ART):
        for x, ch in enumerate(row):
            if ch != ".":
                d.rectangle([x0 + x * sub, y0 + y * sub, x0 + (x + 1) * sub - 1, y0 + (y + 1) * sub - 1],
                            fill=CUP_COLORS[ch])
    cx = x0 + 5 * sub
    for dx, dyy in ((0, -2), (wiggle, -4), (0, -6)):  # vapor
        d.rectangle([cx + dx * sub, y0 + dyy * sub, cx + (dx + 1) * sub - 1, y0 + (dyy + 1) * sub - 1],
                    fill=STEAM)


def draw_claude(size=300, step=None, blink=False, tool=True, skin="default"):
    """Clawd, o mascote do Claude Code, em pixel art chapada.

    Grade de 14x10 células. O mascote (medido na imagem de referência):
      corpo 8x6, bracinhos 2x2 nas laterais, olhos 1x1 e quatro pernas 1x2.
    `step` alterna braços e pernas (caminhada); `blink` achata os olhos;
    `tool` põe um acessório na mão esquerda (lado esquerdo da imagem) = trabalhando.
    `skin` escolhe o visual: "default" (nada na mão), "wrench" (chave inglesa), "coffee" (xícara de café,
    com vapor) ou "santa" (chapéu de Natal, que aparece também quando ocioso).
    """
    coffee = tool and skin == "coffee"
    rows = 11 if coffee else 10  # a xícara com vapor pede uma linha a mais em cima
    cols = 20 if coffee else 14  # a xícara ocupa seis colunas a mais à esquerda
    ox, oy = (7 if coffee else 1), (3 if coffee else 2)  # margem à esquerda (chave inglesa / xícara) e em cima
    px = max(1, size // 14)  # o tamanho da célula não muda com o visual
    img = Image.new("RGBA", (cols * px, rows * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1, color, left=ox, top=oy):  # coords inclusivas, em células
        d.rectangle([(x0 + left) * px, (y0 + top) * px,
                     (x1 + 1 + left) * px - 1, (y1 + 1 + top) * px - 1], fill=color)

    walking = step is not None
    ay_l, ay_r = ((2, 3) if step % 2 else (3, 2)) if walking else (2, 2)

    # acessório (desenhado ANTES do braço, para a mão ficar na frente dele)
    if tool and skin == "wrench":
        dy = ay_l - 2  # acompanha o braço esquerdo
        box(0, 1 + dy, 0, 1 + dy, STEEL, 0, 0)       # mandíbula esquerda
        box(2, 1 + dy, 2, 1 + dy, STEEL, 0, 0)       # mandíbula direita
        box(0, 2 + dy, 2, 3 + dy, STEEL, 0, 0)       # cabeça (bloco grosso, boca aberta em cima)
        box(1, 4 + dy, 1, 7 + dy, STEEL, 0, 0)       # cabo
        box(0, 8 + dy, 2, 8 + dy, STEEL, 0, 0)       # ponta arredondada do cabo
        box(1, 8 + dy, 1, 8 + dy, STEEL_DARK, 0, 0)  # furinho na ponta

    if coffee:  # xícara na mão esquerda: o bracinho (desenhado depois) segura a alça
        _draw_cup(d, ox * px, (ay_l + oy + 1) * px, max(1, px // 2), 1 if (walking and step % 2) else -1)

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
    if skin == "santa":  # o corpo vai das células 2 a 9 (+ margem ox) e começa na linha oy
        img = _with_pixel_hat(img, cx=7 * px, bottom_y=int((oy + 0.6) * px), sub=max(1, px // 2))
    return img


def draw_codex(size=300, step=None, blink=False, tool=True, skin="default"):
    """Mascote do Codex em pixel art: cabeça de nuvem com tela de terminal (>_),
    corpinho com um >_ no peito, bracinhos e pezinhos.

    Grade de 14x15 células. `step` alterna braços e pés (caminhada);
    `blink` apaga o cursor `_` da tela (cursor piscando = trabalhando).
    `skin` "coffee" põe uma xícara de café na mão esquerda (só com `tool`, ou seja, trabalhando);
    "santa" põe um chapéu de Natal (também quando ocioso).
    """
    rows = 15
    coffee = tool and skin == "coffee"
    ox = 4 if coffee else 0  # a xícara ocupa quatro colunas a mais à esquerda
    cols = 14 + ox
    px = max(1, size // rows)
    img = Image.new("RGBA", (cols * px, rows * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1, color):  # coordenadas inclusivas, em células
        d.rectangle([(x0 + ox) * px, y0 * px, (x1 + 1 + ox) * px - 1, (y1 + 1) * px - 1], fill=color)

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
    if coffee:  # xícara na mão esquerda, na frente da nuvem; o bracinho (depois) segura a alça
        _draw_cup(d, (3 + ox) * px, (ay_l + 1) * px, max(1, px // 2), 1 if (walking and step % 2) else -1)
    box(3, ay_l, 3, ay_l + 1, CODEX_ARM)
    box(10, ay_r, 10, ay_r + 1, CODEX_ARM)

    # pezinhos (um levanta a cada passo)
    for i, x in enumerate((4, 8)):
        up = walking and (i % 2) == (step % 2)
        box(x, 13, x + 1, 13 if up else 14, CODEX_BLUE)
    if skin == "santa":  # a barra cobre as três "bolhas" do topo da nuvem
        img = _with_pixel_hat(img, cx=7 * px, bottom_y=int(px * 1.35), sub=max(1, int(px * 0.55)))
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


def draw_cursor(size=300, active=False, glow=0.0, skin="default"):
    """Mascote do Cursor: cubo simples quando ocioso; cubo detalhado do logo quando ativo.
    `skin` "santa" põe um chapéu de Natal em pixel-art."""
    cube = _cursor_detailed(size, glow) if active else _cursor_simple(size)
    if skin == "santa":  # o chapéu (mesma pixel-art dos outros) assenta no topo do cubo
        cube = _with_pixel_hat(cube, cx=size / 2, bottom_y=int(size * 0.27), sub=max(1, round(size * 0.027)))
    return cube


def _gemini_color(y, rows):
    """Cor da linha `y` (0..rows-1) no degradê do Gemini."""
    t_ = y / max(1, rows - 1) * (len(GEMINI_STOPS) - 1)
    i = min(int(t_), len(GEMINI_STOPS) - 2)
    f = t_ - i
    a, b = GEMINI_STOPS[i], GEMINI_STOPS[i + 1]
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


def draw_gemini(size=300, step=None, blink=False, tool=True, skin="default"):
    """Mascote do Gemini CLI em pixel art: uma estrela de quatro pontas em degradê, com olhos,
    as pontas laterais fazendo de bracinhos e duas perninhas.

    Grade de 15x13 células. `step` alterna braços e pernas (caminhada); `blink` achata os olhos;
    `tool` acende uma faísca no canto de cima (trabalhando). `skin` "santa" põe um chapéu de Natal.
    """
    rows, cols = 13, 15
    px = max(1, size // cols)
    img = Image.new("RGBA", (cols * px, rows * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1, color):  # coordenadas inclusivas, em células
        d.rectangle([x0 * px, y0 * px, (x1 + 1) * px - 1, (y1 + 1) * px - 1], fill=color)

    walking = step is not None
    # estrela: intervalo (x0, x1) preenchido em cada linha; as linhas 6 a 8 são as mais largas.
    # A ponta de baixo fica curta para as duas perninhas aparecerem sozinhas.
    star = [(7, 7), (7, 7), (6, 8), (6, 8), (5, 9), (4, 10), (2, 12), (2, 12), (2, 12),
            (4, 10), (5, 9), (6, 8)]
    for y, (x0, x1) in enumerate(star):
        box(x0, y, x1, y, _gemini_color(y, rows))
    # pontas laterais = bracinhos (sobem e descem uma linha a cada passo)
    ay_l, ay_r = ((6, 8) if step % 2 else (8, 6)) if walking else (7, 7)
    box(0, ay_l, 1, ay_l, _gemini_color(ay_l, rows))
    box(13, ay_r, 14, ay_r, _gemini_color(ay_r, rows))
    # olhos (piscando = só a linha de baixo)
    for ex in (5, 9):
        box(ex, 7 if blink else 6, ex, 7, EYE)
    # perninhas: uma levanta a cada passo
    for i, x in enumerate((5, 9)):
        up = walking and (i % 2) == (step % 2)
        box(x, 11, x, 11 if up else 12, _gemini_color(11, rows))
    if tool:  # faísca de quatro pontas no canto de cima à direita (pisca com o passo)
        box(12, 1, 12, 1, GEMINI_SPARK)
        if not walking or step % 2 == 0:
            box(12, 0, 12, 2, GEMINI_SPARK)
            box(11, 1, 13, 1, GEMINI_SPARK)
    if skin == "santa":  # a barra do chapéu assenta perto da ponta de cima
        img = _with_pixel_hat(img, cx=7.5 * px, bottom_y=int(px * 2.6), sub=max(1, int(px * 0.5)))
    return img


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
    from . import settings, skins
    from .i18n import t
    w, h = size
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    logo = 300
    keys = [k for k in ("claude", "codex", "cursor", "gemini") if state_of(status, k) != "off"]
    gap = 140 if len(keys) <= 3 else 90  # quatro mascotes: espaço menor para caber em 1920
    total = len(keys) * logo + (len(keys) - 1) * gap
    x0 = (w - total) // 2
    y0 = (h - logo) // 2 - 40
    cfg_skins = settings.get()["skins"]
    makers = {
        "claude": lambda sk: draw_claude(logo, step, tool=state_of(status, "claude") == "working", skin=sk),
        "codex": lambda sk: draw_codex(logo, step, tool=state_of(status, "codex") == "working", skin=sk),
        "cursor": lambda sk: draw_cursor(logo, active=state_of(status, "cursor") == "working", glow=0.6, skin=sk),
        "gemini": lambda sk: draw_gemini(logo, step, tool=state_of(status, "gemini") == "working", skin=sk),
    }
    for i, key in enumerate(keys):
        skin = cfg_skins[key]
        label, logo_img = t("tool." + key), makers[key](skin)
        # o chapéu cresce a imagem para cima: o mascote fica onde estava e o chapéu sobra por cima
        hat_extra = logo_img.height - makers[key](skins.default(key)).height if skin == "santa" else 0
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
        py = y0 + (logo - (pic.height - hat_extra)) // 2 - hat_extra
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
    render({"claude": True, "codex": False, "cursor": False, "gemini": False}).save("preview.png")
    print("preview.png gerado", file=sys.stderr)
