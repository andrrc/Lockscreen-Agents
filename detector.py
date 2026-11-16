"""Detecta se Claude Code, Codex e Cursor estão ativos, olhando só a data de
modificação dos arquivos locais deles (não lê conteúdo, não precisa de login)."""
import ctypes
import os
import time
from ctypes import wintypes
from datetime import datetime, timedelta
from pathlib import Path

import settings

HOME = Path.home()
ACTIVE_WINDOW = 180  # padrão (configurável em settings.py): segundos sem atividade nos arquivos
# até deixar de considerar "em uso". A ferramenta só grava arquivos quando está respondendo;
# enquanto você lê/digita entre uma resposta e outra ela fica quieta, por isso a janela é longa.


def _mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def _newest_in(dirs, pattern):
    """Maior mtime entre os arquivos que casam com `pattern` dentro de `dirs` (sem recursão)."""
    best = 0.0
    for d in dirs:
        try:
            for entry in os.scandir(d):
                if entry.is_file() and entry.name.endswith(pattern):
                    best = max(best, entry.stat().st_mtime)
        except OSError:
            continue
    return best


def _subdirs(root):
    try:
        return [e.path for e in os.scandir(root) if e.is_dir()]
    except OSError:
        return []


def claude_last_activity():
    # ~/.claude/projects/<projeto>/<sessao>.jsonl
    return _newest_in(_subdirs(HOME / ".claude" / "projects"), ".jsonl")


def codex_last_activity():
    # ~/.codex/sessions/AAAA/MM/DD/rollout-*.jsonl (olha hoje e ontem)
    dirs = []
    for delta in (0, 1):
        d = datetime.now() - timedelta(days=delta)
        dirs.append(HOME / ".codex" / "sessions" / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}")
    return _newest_in(dirs, ".jsonl")


def cursor_last_activity():
    # Terminais do agente, transcrições e banco de rastreamento de código de IA.
    best = 0.0
    base = HOME / ".cursor"
    for proj in _subdirs(base / "projects"):
        best = max(best, _newest_in([Path(proj) / "terminals"], ".txt"))
        best = max(best, _newest_in([Path(proj) / "agent-transcripts"], ".jsonl"))
        best = max(best, _newest_in(_subdirs(Path(proj) / "agent-transcripts"), ".jsonl"))
    for name in ("ai-code-tracking.db", "ai-code-tracking.db-wal"):
        best = max(best, _mtime(base / "ai-tracking" / name))
    return best


SOURCES = {
    "claude": claude_last_activity,
    "codex": codex_last_activity,
    "cursor": cursor_last_activity,
}


def get_status(window=ACTIVE_WINDOW):
    """Retorna {'claude': True/False, ...} e quantos segundos desde a última atividade."""
    now = time.time()
    status, age = {}, {}
    for name, fn in SOURCES.items():
        last = fn()
        age[name] = (now - last) if last else None
        status[name] = last > 0 and (now - last) <= window
    return status, age


# Executáveis de cada ferramenta (para saber se estão abertas)
PROCESS_EXES = {
    "claude": {"claude.exe"},
    "codex": {"codex.exe"},
    "cursor": {"cursor.exe"},
}


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


def running_exes():
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


_last_seen = {}   # ferramenta -> última vez que o processo (ou atividade) foi visto

# Janela em foco: se você está com o app da ferramenta na frente e mexendo no PC, está "em uso"
# (o Cursor, por exemplo, quase não grava arquivos enquanto você só edita código).
FG_MAX_IDLE = 180    # sem teclado/mouse por mais que isso, janela em foco não conta
FG_MATCH = {         # ferramenta -> (nomes de exe, trechos do caminho)
    "claude": ({"claude.exe"}, ()),
    "codex": ({"codex.exe"}, ("openai.codex",)),
    "cursor": ({"cursor.exe"}, ()),
}
_last_fg = {}


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    """Segundos desde o último teclado/mouse."""
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    k32 = ctypes.windll.kernel32
    k32.GetTickCount.restype = wintypes.DWORD
    return ((k32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


def foreground_path():
    """Caminho (minúsculo) do executável da janela em foco, ou '' se não der para saber."""
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


def tool_of_path(path):
    """Qual ferramenta (claude/codex/cursor) é dona desse executável, ou None."""
    exe = os.path.basename(path)
    for name, (exes, parts) in FG_MATCH.items():
        if exe in exes or any(p in path for p in parts):
            return name
    return None


def get_states(window=None):
    """Estado de cada ferramenta: 'working' (arquivos mudando), 'open' (processo rodando,
    sem atividade), 'closed' (nenhum processo por mais de `close_grace` segundos) ou 'off'
    (desligada nas configurações). Os limites vêm de settings.py.
    A tolerância evita que uma leitura de processos falha (ex.: ao bloquear o PC) vire 'fechado'."""
    cfg = settings.get()
    window = cfg["active_window"] if window is None else window
    now = time.time()
    working, _ = get_status(window)
    try:
        running = running_exes()
    except Exception:  # noqa: BLE001
        running = None  # leitura falhou: mantém o que já se sabia
    if cfg["follow_focus"]:
        try:  # janela em foco + usuário mexendo no PC = ferramenta em uso
            fg = tool_of_path(foreground_path())
            if fg and idle_seconds() < FG_MAX_IDLE:
                _last_fg[fg] = now
        except Exception:  # noqa: BLE001
            pass
    states = {}
    for name in SOURCES:
        if not cfg["tools"].get(name, True):
            states[name] = "off"
            continue
        focused = cfg["follow_focus"] and now - _last_fg.get(name, 0) <= cfg["focus_hold"]
        if working[name] or focused:
            _last_seen[name] = now
            states[name] = "working"
            continue
        if running is not None and PROCESS_EXES[name] & running:
            _last_seen[name] = now
        seen = _last_seen.get(name)
        if seen is None and running is None:
            seen = now  # sem informação nenhuma: assume aberto
        states[name] = "open" if seen is not None and now - seen <= cfg["close_grace"] else "closed"
    return states


if __name__ == "__main__":
    print("Monitorando... (Ctrl+C para sair)")
    try:
        while True:
            status, age = get_status()
            parts = []
            for n in SOURCES:
                a = age[n]
                txt = "sem dados" if a is None else f"{a:6.0f}s atrás"
                parts.append(f"{n:6s} {'ATIVO ' if status[n] else 'ocioso'} ({txt})")
            print("  |  ".join(parts), flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
