"""Configurações do app (settings.json), compartilhadas pela bandeja, pelo detector,
pelo protetor de tela e pela janela de configurações.

Quem lê usa `get()`: devolve um dicionário já validado e só relê o arquivo quando ele muda.
Quem altera usa `update(chave=valor, ...)`, que grava de forma atômica.
"""
import json
import os
import time

from . import platforms, skins, templates

APP_NAME = "LockscreenAgents"
OUT_DIR = platforms.current().data_dir()
SETTINGS = OUT_DIR / "settings.json"

TOOLS = ("claude", "codex", "cursor")

DEFAULTS = {
    "lang": "auto",            # auto | pt | en
    "template": templates.DEFAULT,  # modelo visual (veja templates.py)
    "skins": skins.defaults(),      # visual de cada mascote (veja skins.py)
    "tools": {"claude": True, "codex": True, "cursor": True},
    "active_window": 180,      # s sem atividade nos arquivos até deixar de estar "em uso"
    "follow_focus": True,      # janela da ferramenta em foco + você ativo conta como "em uso"
    "focus_hold": 120,         # s que continua "em uso" depois de a janela sair de foco
    "close_grace": 25,         # s sem ver o processo até marcar "fechado"
    "saver_on": True,
    "idle_min": 5,             # min sem mexer no PC até abrir o protetor
    "lock_after": False,
}

# (mínimo, máximo) dos valores numéricos
LIMITS = {
    "active_window": (30, 900),
    "focus_hold": (0, 600),
    "close_grace": (5, 120),
    "idle_min": (1, 60),
}


def _clean(raw):
    """Junta `raw` com os padrões e força cada valor para um tipo e faixa válidos."""
    cfg = json.loads(json.dumps(DEFAULTS))  # cópia profunda
    if isinstance(raw, dict):
        for k, default in DEFAULTS.items():
            if k not in raw:
                continue
            v = raw[k]
            if k == "tools":
                if isinstance(v, dict):
                    for name in TOOLS:
                        if name in v:
                            cfg["tools"][name] = bool(v[name])
            elif k == "lang":
                cfg["lang"] = v if v in ("auto", "pt", "en") else "auto"
            elif k == "skins":  # só aceita visuais já disponíveis
                if isinstance(v, dict):
                    for tool in skins.SKINS:
                        if v.get(tool) in skins.available_ids(tool):
                            cfg["skins"][tool] = v[tool]
            elif k == "template":  # só aceita modelos já disponíveis
                cfg["template"] = v if v in templates.available_ids() else templates.DEFAULT
            elif isinstance(default, bool):
                cfg[k] = bool(v)
            elif isinstance(default, int):
                try:
                    lo, hi = LIMITS[k]
                    cfg[k] = max(lo, min(hi, int(v)))
                except (TypeError, ValueError):
                    pass
    if not any(cfg["tools"].values()):  # pelo menos uma ferramenta precisa ficar ligada
        cfg["tools"] = dict(DEFAULTS["tools"])
    return cfg


def load():
    try:
        return _clean(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return _clean(None)


def save(cfg):
    """Grava de forma atômica (arquivo temporário + troca), para ninguém ler pela metade."""
    cfg = _clean(cfg)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_name(SETTINGS.name + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, SETTINGS)
    _cache.update(mtime=None, at=0.0)  # força reler
    return cfg


def update(**changes):
    cfg = load()
    for k, v in changes.items():
        if k in ("tools", "skins"):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return save(cfg)


def reset():
    return save(_clean(None))


_cache = {"cfg": None, "mtime": None, "at": 0.0}


def get():
    """Configuração atual (cache; confere o arquivo no máximo uma vez por segundo)."""
    now = time.monotonic()
    if _cache["cfg"] is not None and now - _cache["at"] < 1.0:
        return _cache["cfg"]
    try:
        mtime = os.stat(SETTINGS).st_mtime_ns
    except OSError:
        mtime = None
    if _cache["cfg"] is None or mtime != _cache["mtime"]:
        _cache["cfg"] = load()
        _cache["mtime"] = mtime
    _cache["at"] = now
    return _cache["cfg"]
