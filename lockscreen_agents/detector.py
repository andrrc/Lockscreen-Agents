"""Detecta se Claude Code, Codex e Cursor estão ativos, olhando só a data de
modificação dos arquivos locais deles (não lê conteúdo, não precisa de login)."""
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import platforms, settings

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


def _plat():
    return platforms.current()


def running_exes():
    """Nomes (minúsculos) dos programas em execução (a leitura em si é de cada sistema)."""
    return _plat().running_processes()


_last_seen = {}   # ferramenta -> última vez que o processo (ou atividade) foi visto

# Janela em foco: se você está com o app da ferramenta na frente e mexendo no PC, está "em uso"
# (o Cursor, por exemplo, quase não grava arquivos enquanto você só edita código).
FG_MAX_IDLE = 180    # sem teclado/mouse por mais que isso, janela em foco não conta
_last_fg = {}


def idle_seconds():
    """Segundos desde o último teclado/mouse."""
    return _plat().idle_seconds()


def foreground_path():
    """Caminho (minúsculo) do programa da janela em foco, ou '' se não der para saber."""
    return _plat().foreground_app_path()


def tool_of_path(path):
    """Qual ferramenta (claude/codex/cursor) é dona desse executável, ou None."""
    exe = os.path.basename(path)
    for name, (exes, parts) in _plat().FOCUS_MATCH.items():
        if exe in exes or any(p in path for p in parts):
            return name
    return None


LAST = {}  # sinais da última leitura de cada ferramenta (a tela "Como funciona" mostra isto)


def get_states(window=None):
    """Estado de cada ferramenta: 'working' (arquivos mudando), 'open' (processo rodando,
    sem atividade), 'closed' (nenhum processo por mais de `close_grace` segundos) ou 'off'
    (desligada nas configurações). Os limites vêm de settings.py.
    A tolerância evita que uma leitura de processos falha (ex.: ao bloquear o PC) vire 'fechado'.
    Os sinais usados (arquivos, processo, foco) ficam em `LAST`."""
    cfg = settings.get()
    window = cfg["active_window"] if window is None else window
    now = time.time()
    working, age = get_status(window)
    try:
        running = running_exes()
    except Exception:  # noqa: BLE001
        running = None  # leitura falhou: mantém o que já se sabia
    fg, user_active = None, False
    try:  # janela em foco + usuário mexendo no PC = ferramenta em uso
        fg = tool_of_path(foreground_path())
        user_active = idle_seconds() < FG_MAX_IDLE
    except Exception:  # noqa: BLE001
        pass
    if fg and user_active and cfg["follow_focus"]:
        _last_fg[fg] = now
    states = {}
    for name in SOURCES:
        sig = {"file_age": age.get(name),
               "running": None if running is None else bool(_plat().PROCESS_NAMES[name] & running),
               "focus_now": bool(fg == name and user_active),
               "focus_age": (now - _last_fg[name]) if name in _last_fg else None}
        if not cfg["tools"].get(name, True):
            state = "off"
        elif working[name] or (cfg["follow_focus"] and now - _last_fg.get(name, 0) <= cfg["focus_hold"]):
            _last_seen[name] = now
            state = "working"
        else:
            if running is not None and _plat().PROCESS_NAMES[name] & running:
                _last_seen[name] = now
            seen = _last_seen.get(name)
            if seen is None and running is None:
                seen = now  # sem informação nenhuma: assume aberto
            state = "open" if seen is not None and now - seen <= cfg["close_grace"] else "closed"
        states[name] = state
        sig["state"] = state
        LAST[name] = sig
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
