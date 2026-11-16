"""Ponto de entrada único do Lockscreen Agents.

    app.py                 bandeja (o app em si)
    app.py --settings      janela de configurações
    app.py --saver /s      protetor de tela animado (aceita --seconds N para testes)
    app.py --restore-wallpaper   devolve o papel de parede original (macOS) e sai

É o que o PyInstaller empacota em LockscreenAgents.exe.
"""
import sys


def main():
    args = sys.argv[1:]
    if args[:1] == ["--restore-wallpaper"]:
        from . import platforms
        plat = platforms.current()
        try:
            done = plat.restore_lock_screen()
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"Não foi possível restaurar: {exc}")
        print("Papel de parede original restaurado." if done else "Nada a restaurar.")
        return
    mode = args.pop(0)[2:] if args and args[0] in ("--tray", "--settings", "--saver") else "tray"
    sys.argv = [sys.argv[0]] + args  # cada modo lê só os argumentos que são dele
    if mode == "settings":
        from . import settings_ui
        settings_ui.main()
    elif mode == "saver":
        from . import saver
        saver.main()
    else:
        from . import tray
        tray.main()
