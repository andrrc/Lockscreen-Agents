"""Gera as imagens da logo em docs/ (logo.png) a partir de logo.py.

Uso (na raiz do projeto): python tools/make_logo.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lockscreen_agents.logo import logo  # noqa: E402

OUT = ROOT / "docs"

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    logo(512).save(OUT / "logo.png")
    print("ok")
