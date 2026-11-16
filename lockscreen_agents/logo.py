"""Logo do Lockscreen Agents: um cadeado em pixel-art cujo corpo tem as cores das três
ferramentas (laranja, azul e branco). Usada no ícone da bandeja, na janela e no README.

    logo(size)               ícone com fundo arredondado escuro (janela, README, atalhos)
    mark(size, paused=False) só o cadeado, sem fundo, para a bandeja (paused = cinza)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ORANGE, BLUE, WHITE = (217, 119, 87), (66, 108, 222), (236, 236, 240)
PALETTE = {"o": ORANGE, "b": BLUE, "w": WHITE, "g": (206, 206, 214), "k": (18, 18, 26)}

LOCK = [
    "....gggggggg....",
    "...gg......gg...",
    "..gg........gg..",
    "..gg........gg..",
    "..gg........gg..",
    "..gg........gg..",
    "oooooobbbbwwwwww",
    "oooooobbbbwwwwww",
    "oooooobbbbwwwwww",
    "ooooobbkkbbwwwww",
    "ooooobkkkkbwwwww",
    "oooooobkkbbwwwww",
    "oooooobbkkbwwwww",
    "oooooobbkkbwwwww",
    "oooooobbbbwwwwww",
    "oooooobbbbwwwwww",
]


def _pixels(cell):
    h, w = len(LOCK), len(LOCK[0])
    img = Image.new("RGBA", (w * cell, h * cell), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y, row in enumerate(LOCK):
        for x, ch in enumerate(row):
            if ch != ".":
                d.rectangle([x * cell, y * cell, (x + 1) * cell - 1, (y + 1) * cell - 1], fill=PALETTE[ch])
    return img


def _shadow(img, offset):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 70), (0, 0), img.split()[3])
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, offset))
    out.alpha_composite(img)
    return out


def _tile(size):
    """Quadrado arredondado escuro com degradê e uma borda fina."""
    big = size * 4
    grad = Image.new("RGB", (1, 2))
    grad.putpixel((0, 0), (30, 30, 38))
    grad.putpixel((0, 1), (15, 15, 19))
    grad = grad.resize((big, big), Image.BILINEAR)
    mask = Image.new("L", (big, big), 0)
    r = int(big * 0.225)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=r, fill=255)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    ImageDraw.Draw(img).rounded_rectangle([big * 0.012] * 2 + [big * 0.988] * 2, radius=r * 0.97,
                                          outline=(255, 255, 255, 26), width=max(2, big // 170))
    return img.resize((size, size), Image.LANCZOS)


def logo(size=512):
    if size < 128:  # tamanhos pequenos: desenha grande e reduz (a célula de 1 px ficaria minúscula)
        return logo(512).resize((size, size), Image.LANCZOS)
    img = _tile(size)
    cell = max(1, int(size * 0.042))
    lock = _shadow(_pixels(cell), max(1, int(cell * 0.6)))
    img.alpha_composite(lock, ((size - lock.width) // 2, (size - lock.height) // 2))
    return img


def mark(size=64, paused=False):
    """Cadeado sem fundo para a bandeja, com contorno escuro (legível em barra clara ou escura).
    Células de tamanho inteiro mantêm o pixel-art nítido. `size` é o lado final."""
    cell = max(1, size // 18)  # 16 células do desenho + 1 de contorno em cada lado
    lock = _pixels(cell)
    if paused:
        lock = lock.convert("LA").convert("RGBA")
        lock.putalpha(lock.split()[3].point(lambda a: int(a * 0.6)))
    pad = cell
    edge = Image.new("RGBA", (lock.width + 2 * pad, lock.height + 2 * pad), (0, 0, 0, 0))
    grown = Image.new("L", edge.size, 0)
    grown.paste(lock.split()[3], (pad, pad))
    grown = grown.filter(ImageFilter.MaxFilter(2 * cell + 1))
    edge.paste((22, 22, 28, 235 if not paused else 140), (0, 0), grown)
    edge.alpha_composite(lock, (pad, pad))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(edge, ((size - edge.width) // 2, (size - edge.height) // 2))
    return canvas


def save_ico(path):
    """Grava um .ico com vários tamanhos (usado nos atalhos)."""
    base = logo(256)
    base.save(Path(path), format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                               (256, 256)])
