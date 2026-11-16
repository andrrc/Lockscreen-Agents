"""Ponto de entrada único do Lockscreen Agents.

    app.py                 bandeja (o app em si)
    app.py --settings      janela de configurações
    app.py --saver /s      protetor de tela animado (aceita --seconds N para testes)

É o que o PyInstaller empacota em LockscreenAgents.exe.
"""
import sys


def main():
    args = sys.argv[1:]
    mode = args.pop(0)[2:] if args and args[0] in ("--tray", "--settings", "--saver") else "tray"
    sys.argv = [sys.argv[0]] + args  # cada modo lê só os argumentos que são dele
    if mode == "settings":
        import settings_ui
        settings_ui.main()
    elif mode == "saver":
        import saver
        saver.main()
    else:
        import tray
        tray.main()


if __name__ == "__main__":
    main()
