"""Visuais (skins) de cada mascote.

Cada ferramenta tem uma lista de visuais; o primeiro é o padrão. Hoje o Claude Code tem dois:
a chave inglesa e a garrafa de café. Os outros mascotes só têm o visual padrão.

Para criar um visual novo:

  1. acrescente `{"id": "meu-visual", "available": True}` na lista da ferramenta aqui;
  2. desenhe-o na função da ferramenta em `render.py` (veja `draw_claude`, parâmetro `skin`);
  3. crie o nome `skin.<ferramenta>.<id>` em português e inglês em `i18n.py`.

A página "Personagens" da janela de configurações mostra todos os visuais disponíveis.
"""

SKINS = {
    "claude": [
        {"id": "wrench", "available": True},
        {"id": "coffee", "available": True},
    ],
    "codex": [{"id": "default", "available": True}],
    "cursor": [{"id": "default", "available": True}],
}


def default(tool):
    return SKINS[tool][0]["id"]


def defaults():
    return {tool: default(tool) for tool in SKINS}


def available_ids(tool):
    return [s["id"] for s in SKINS.get(tool, []) if s["available"]]
