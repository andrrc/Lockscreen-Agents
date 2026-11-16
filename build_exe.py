"""Gera o executável (pasta build/dist/LockscreenAgents/) com o PyInstaller.

Uso: pip install pyinstaller
     python build_exe.py

O resultado é uma pasta (não um arquivo único): abre mais rápido e costuma gerar menos alertas
de antivírus. O instalador (installer.iss, Inno Setup) empacota essa pasta.
"""
import sys
from pathlib import Path

from version import __version__

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
NAME = "LockscreenAgents"
HIDDEN = [  # módulos que o PyInstaller não enxerga sozinho
    "pystray._win32",
    "winrt.runtime",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.storage",
    "winrt.windows.storage.streams",
    "winrt.windows.system.userprofile",
]


def version_file():
    """Informações que o Windows mostra no Gerenciador de Tarefas e nas Propriedades do .exe."""
    nums = tuple(int(p) for p in (__version__.split(".") + ["0"] * 4)[:4])
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Lockscreen Agents'),
      StringStruct('FileDescription', 'Lockscreen Agents'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', 'Lockscreen Agents'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = BUILD / "version_info.txt"
    path.write_text(text, encoding="utf-8")
    return path


def main():
    import PyInstaller.__main__
    import logo

    BUILD.mkdir(exist_ok=True)
    ico = BUILD / "logo.ico"
    logo.save_ico(ico)
    args = [
        str(ROOT / "app.py"),
        "--name", NAME,
        "--noconfirm", "--clean",
        "--windowed", "--onedir",
        "--icon", str(ico),
        "--version-file", str(version_file()),
        "--distpath", str(BUILD / "dist"),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
    ]
    for mod in HIDDEN:
        args += ["--hidden-import", mod]
    PyInstaller.__main__.run(args)
    print(f"\nPronto: {BUILD / 'dist' / NAME / (NAME + '.exe')}")


if __name__ == "__main__":
    sys.exit(main())
