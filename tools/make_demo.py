"""Gera as imagens do README (pasta docs/): lock screen em vários estados e GIFs dos mascotes."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lockscreen_agents.render import BG, draw_claude, draw_codex, render  # noqa: E402

W, H = 900, 300


def frames(draw, size, blink_at):
    out = []
    x, dx = 40, 7
    for i in range(70):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        step = (i // 3) % 2
        spr = draw(size, step=step, blink=blink_at(i))
        if dx < 0:
            spr = spr.transpose(Image.FLIP_LEFT_RIGHT)
        ground = 250
        bob = 4 if step else 0
        d.ellipse([x + 10, ground - 6, x + spr.width - 10, ground + 8], fill=(26, 26, 30))
        img.paste(spr, (x, ground - spr.height - bob), spr)
        out.append(img)
        x += dx
        if x > W - spr.width - 40 or x < 40:
            dx = -dx
    return out


def save_gif(name, fr):
    fr[0].save(name, save_all=True, append_images=fr[1:], duration=70, loop=0, optimize=True)


def poses(name, draw, size):
    im = Image.new("RGB", (1000, 320), BG)
    for i, (s, b) in enumerate([(None, False), (0, False), (1, False), (None, True)]):
        c = draw(size, step=s, blink=b)
        im.paste(c, (10 + i * 245, 20), c)
    im.save(name)


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    os.makedirs("docs", exist_ok=True)
    # lock screen: Claude e Gemini em uso, Codex ocioso, Cursor fechado / todos em uso
    render({"claude": "working", "codex": "open", "cursor": "closed", "gemini": "working"},
           template="mascots").save("docs/lock-states.png")
    render({"claude": "working", "codex": "working", "cursor": "working", "gemini": "working"},
           template="mascots").save("docs/lock-all-active.png")
    save_gif("docs/demo-claude.gif", frames(draw_claude, 190, lambda i: (i % 28) in (24, 25)))
    save_gif("docs/demo-codex.gif", frames(draw_codex, 220, lambda i: (i // 5) % 2 == 1))
    print("ok")
