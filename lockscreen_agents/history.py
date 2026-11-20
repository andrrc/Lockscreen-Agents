"""Histórico do dia: quanto tempo cada ferramenta ficou em uso hoje (usado pelo modelo Placar).

A bandeja chama `add` a cada ciclo com os estados detectados e o tempo desde o ciclo anterior.
Só o total do dia fica guardado, em `history.json` na pasta de dados; à meia-noite ele recomeça.
O arquivo não guarda nada das ferramentas além desses segundos.
"""
import json
import os
import time

from . import settings

MAX_STEP = 30  # segundos: um intervalo maior que isso (PC suspenso, bandeja travada) não conta


def _path():
    return settings.OUT_DIR / "history.json"


def _today():
    return time.strftime("%Y-%m-%d")


def today():
    """{'claude': segundos, ...} de hoje (vazio se o arquivo é de outro dia ou não existe)."""
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("date") != _today():
        return {}
    seconds = data.get("seconds", {})
    return {k: float(v) for k, v in seconds.items() if isinstance(v, (int, float)) and v >= 0}


def add(states, elapsed):
    """Soma `elapsed` segundos às ferramentas em uso ('working'). Devolve os totais de hoje."""
    totals = today()
    if not 0 < elapsed <= MAX_STEP:
        return totals
    working = [k for k, st in states.items() if st == "working"]
    if not working:
        return totals
    for k in working:
        totals[k] = totals.get(k, 0.0) + elapsed
    path = _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"date": _today(), "seconds": {k: round(v, 1) for k, v in totals.items()}}),
                       encoding="utf-8")
        os.replace(tmp, path)  # troca de uma vez: quem lê nunca pega o arquivo pela metade
    except OSError:
        pass
    return totals
