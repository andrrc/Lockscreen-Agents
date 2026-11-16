"""Aplica uma imagem como tela de bloqueio do Windows (API WinRT LockScreen)."""
import asyncio
import os

from winrt.windows.storage import StorageFile
from winrt.windows.system.userprofile import LockScreen


async def _set(path):
    f = await StorageFile.get_file_from_path_async(path)
    await LockScreen.set_image_file_async(f)


def set_lockscreen(path):
    asyncio.run(_set(os.path.abspath(path)))


if __name__ == "__main__":
    import sys
    set_lockscreen(sys.argv[1])
    print("Lock screen atualizada:", sys.argv[1])
