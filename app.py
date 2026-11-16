"""Atalho para rodar o app a partir do código-fonte: `python app.py [--settings | --saver /s]`.

O código fica no pacote lockscreen_agents/. Este arquivo existe para o app poder chamar a si mesmo
(launcher.py) e para o PyInstaller ter um script de entrada.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lockscreen_agents.app import main  # noqa: E402

if __name__ == "__main__":
    main()
