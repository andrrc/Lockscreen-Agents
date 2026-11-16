"""Gera as imagens da logo em docs/ (logo.png) a partir de logo.py.

Uso: python make_logo.py
"""
from pathlib import Path

from logo import logo

OUT = Path(__file__).with_name("docs")

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    logo(512).save(OUT / "logo.png")
    print("ok")
