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
    # O Gemini CLI roda no Node (node.exe): só um binário próprio "gemini.exe" é reconhecido aqui;
    # o detector usa a atividade nos arquivos para saber se ele está aberto (FILE_OPEN_HOLD).
    PROCESS_NAMES = {"claude": {"claude.exe"}, "codex": {"codex.exe"}, "cursor": {"cursor.exe"},
                     "gemini": {"gemini.exe"}}
    FOCUS_MATCH = {
        "claude": ({"claude.exe"}, ()),
        "codex": ({"codex.exe"}, ("openai.codex",)),
        "cursor": ({"cursor.exe"}, ()),
        "gemini": ({"gemini.exe"}, ()),
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

    def display_sleep_blocked(self):
        """Dois sinais, qualquer um basta: algum programa pediu a tela acesa (ES_DISPLAY_REQUIRED,
        o que players e navegadores fazem ao tocar vídeo) ou há um app em tela cheia/apresentação."""
        try:
            state = ctypes.c_ulong(0)
            # SystemExecutionState = 16: soma do que os programas pediram com SetThreadExecutionState
            if (ctypes.windll.powrprof.CallNtPowerInformation(16, None, 0, ctypes.byref(state), 4) == 0
                    and state.value & 0x00000002):  # ES_DISPLAY_REQUIRED
                return True
            shown = ctypes.c_int(0)
            if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(shown)) == 0:
                return shown.value in (2, 3, 4)  # ocupado (tela cheia), Direct3D em tela cheia, apresentação
        except Exception:  # noqa: BLE001
            pass
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

    # ---- início automático (tarefa agendada + registro Run + atalho em Inicializar)
    # Três caminhos de propósito; o mutex do tray evita cópia dupla. A chave Run e a pasta
    # Inicializar falharam em vários logons (17 a 19/11, com pythonw + app.py, o Windows nem tentou
    # executar a entrada do Run). A tarefa agendada no logon é o caminho principal: espera alguns
    # segundos a área de notificação ficar pronta e não para quando o notebook está na bateria.
    def _startup_lnk(self):
        return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                / "Startup" / f"{APP_NAME}.lnk")

    @staticmethod
    def _task_user():
        domain = os.environ.get("USERDOMAIN")
        user = os.environ.get("USERNAME", "")
        return f"{domain}\\{user}" if domain else user

    @staticmethod
    def task_xml(command, user, delay_seconds=10):
        """XML da tarefa agendada que abre o app no logon de `user` (sem pedir administrador)."""
        from xml.sax.saxutils import escape
        args = " ".join(f'"{a}"' for a in command[1:])
        workdir = Path(command[-1]).parent if len(command) > 1 else Path(command[0]).parent
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Abre o Lockscreen Agents ao entrar no Windows.</Description></RegistrationInfo>
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>{escape(user)}</UserId><Delay>PT{int(delay_seconds)}S</Delay></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author"><UserId>{escape(user)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>4</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{escape(command[0])}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(str(workdir))}</WorkingDirectory></Exec>
  </Actions>
</Task>
"""

    def _schtasks(self, *args):
        return subprocess.run(["schtasks", *args], capture_output=True, creationflags=CREATE_NO_WINDOW)

    def _task_exists(self):
        return self._schtasks("/Query", "/TN", APP_NAME).returncode == 0

    def _task_create(self, command):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        try:
            Path(path).write_text(self.task_xml(command, self._task_user()), encoding="utf-16")
            return self._schtasks("/Create", "/TN", APP_NAME, "/XML", path, "/F").returncode == 0
        finally:
            Path(path).unlink(missing_ok=True)

    def autostart_is_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, APP_NAME)
                return True
        except OSError:
            return self._startup_lnk().exists() or self._task_exists()

    def autostart_enable(self, command, icon=None):
        quote = lambda a: f'"{a}"'  # noqa: E731
        task_ok = self._task_create(command)
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
        return lnk.exists() or task_ok

    def autostart_disable(self):
        if self._task_exists():
            self._schtasks("/Delete", "/TN", APP_NAME, "/F")
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
