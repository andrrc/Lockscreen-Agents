"""Modelos (visuais) da tela de bloqueio e do protetor de tela.

Hoje existem os modelos "mascotes", "escritório" (office.py) e "placar" (scoreboard.py). Os outros
aparecem na janela de configurações como "em breve". Para lançar um modelo novo:

  1. troque `available` para True aqui;
  2. escreva a função que desenha o modelo (como `render.render` faz para os mascotes) e
     faça `tray.py` e `saver.py` escolherem o desenho pela chave `template` das configurações;
  3. confira os textos `tpl.<id>.n` (nome) e `tpl.<id>.d` (descrição) em `i18n.py`.

Para listar um modelo futuro como "em breve", basta acrescentar uma linha aqui, os dois textos
em `i18n.py` e (opcional) um desenho em `settings_ui.concept_preview`.
"""

DEFAULT = "mascots"

TEMPLATES = [
    {"id": "mascots", "available": True},
    {"id": "office", "available": True},
    {"id": "scoreboard", "available": True},
    {"id": "minimal", "available": False},
    {"id": "terminal", "available": False},
    {"id": "panel", "available": False},
]


def available_ids():
    return [t["id"] for t in TEMPLATES if t["available"]]
