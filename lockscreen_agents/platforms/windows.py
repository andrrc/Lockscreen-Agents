"""Implementação para Windows 10/11."""
import asyncio
import ctypes
import os
import subprocess
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

from .base import Platform

APP_NAME = "LockscreenAgents"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CREATE_NO_WINDOW = 0x08000000


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class WindowsPlatform(Platform):
    name = "windows"
    PROCESS_NAMES = {"claude": {"claude.exe"}, "codex": {"codex.exe"}, "cursor": {"cursor.exe"}}
    FOCUS_MATCH = {
        "claude": ({"claude.exe"}, ()),
        "codex": ({"codex.exe"}, ("openai.codex",)),
        "cursor": ({"cursor.exe"}, ()),
    }

    def __init__(self):
        self._mutexes = {}

    # ---- dados
    def data_dir(self):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME

    # ---- leitura do sistema
    def running_processes(self):
        """Nomes (minúsculos) dos executáveis em execução. Usa a API Toolhelp, sem dependências."""
        k32 = ctypes.windll.kernel32
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
        k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        names = set()
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if not snap or snap == ctypes.c_void_p(-1).value:
            return names
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            ok = k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                names.add(entry.szExeFile.lower())
                ok = k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            k32.CloseHandle(snap)
        return names

    def foreground_app_path(self):
        u, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                   ctypes.POINTER(wintypes.DWORD)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value.lower()
        finally:
            k32.CloseHandle(h)
        return ""

    def idle_seconds(self):
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        k32 = ctypes.windll.kernel32
        k32.GetTickCount.restype = wintypes.DWORD
        return ((k32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0

    def session_locked(self):
        """True se a área de trabalho de entrada não é a do usuário (tela bloqueada, UAC...)."""
        u = ctypes.windll.user32
        u.OpenInputDesktop.restype = ctypes.c_void_p
        u.CloseDesktop.argtypes = [ctypes.c_void_p]
        h = u.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
        if not h:
            return True
        u.CloseDesktop(h)
        return False

    # ---- ações
    def set_lock_screen(self, image_path):
        """API WinRT LockScreen. A tela de bloqueio precisa estar no modo "Imagem"."""
        from winrt.windows.storage import StorageFile
        from winrt.windows.system.userprofile import LockScreen

        async def _set(path):
            f = await StorageFile.get_file_from_path_async(path)
            await LockScreen.set_image_file_async(f)

        asyncio.run(_set(os.path.abspath(image_path)))

    def lock_session(self):
        ctypes.windll.user32.LockWorkStation()

    def open_path(self, path):
        os.startfile(path)

    def system_language(self):
        try:
            return "pt" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x16 else "en"
        except Exception:  # noqa: BLE001
            return "en"

    def single_instance(self, name):
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\" + name)
        self._mutexes[name] = handle  # precisa continuar referenciado enquanto o app roda
        return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS

    # ---- início automático (registro Run + atalho em Inicializar)
    # Dois caminhos de propósito: no logon de 16/11 o Windows ignorou a entrada do Run; com os
    # dois, o que funcionar sobe o app (o mutex do tray evita cópia dupla).
    def _startup_lnk(self):
        return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                / "Startup" / f"{APP_NAME}.lnk")

    def autostart_is_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, APP_NAME)
                return True
        except OSError:
            return self._startup_lnk().exists()

    def autostart_enable(self, command, icon=None):
        quote = lambda a: f'"{a}"'  # noqa: E731
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, " ".join(quote(a) for a in command))
        lnk = self._startup_lnk()
        args = " ".join(quote(a) for a in command[1:])
        icon_ps = f"$s.IconLocation='{icon}';" if icon else ""
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
              f"$s.TargetPath='{command[0]}';$s.Arguments='{args}';{icon_ps}"
              f"$s.WorkingDirectory='{Path(command[0]).parent}';$s.WindowStyle=7;$s.Save()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                       creationflags=CREATE_NO_WINDOW)
        return lnk.exists()

    def autostart_disable(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, APP_NAME)
        except FileNotFoundError:
            pass
        self._startup_lnk().unlink(missing_ok=True)

    # ---- janelas
    def python_gui(self):
        exe = Path(sys.executable)
        w = exe.with_name("pythonw.exe")  # sem janela de console
        return str(w if w.exists() else exe)

    def init_ui_process(self, app_id):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa: BLE001
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:  # noqa: BLE001
                pass
        try:  # identidade própria: o Windows não agrupa a janela com o Python na barra de tarefas
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:  # noqa: BLE001
            pass

    def ui_scale(self, root):
        return root.winfo_fpixels("1i") / 96

    def style_window(self, root, bg, fg, border):
        """Barra de título escura e na mesma cor do fundo (Windows 10 recente / 11)."""
        try:
            user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
            user32.GetParent.restype = wintypes.HWND
            hwnd = user32.GetParent(root.winfo_id())
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

            def put(attr, val):
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

            bgr = lambda c: c[0] | (c[1] << 8) | (c[2] << 16)  # noqa: E731
            put(20, 1)            # modo escuro
            put(35, bgr(bg))      # cor da barra de título
            put(34, bgr(border))  # cor da borda
            put(36, bgr(fg))      # cor do texto
        except Exception:  # noqa: BLE001
            pass

    def focus_window(self, title):
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)

    def monitors(self, root):
        rects = []
        proc_t = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)

        def cb(_hmon, _hdc, rect, _data):
            r = rect.contents
            rects.append((r.left, r.top, r.right, r.bottom))
            return 1

        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc_t(cb), 0)
        return rects or super().monitors(root)

    def show_message(self, title, text):
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)

    def stop_app_processes(self, patterns):
        regex = "|".join(patterns)
        ps = (
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\\.exe$' -and "
            f"$_.CommandLine -match '({regex})' }} | ForEach-Object "
            "{ Stop-Process -Id $_.ProcessId -Force; 'encerrado PID ' + $_.ProcessId }"
        )
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                             text=True, creationflags=CREATE_NO_WINDOW).stdout.strip()
        return out.splitlines() if out else []
