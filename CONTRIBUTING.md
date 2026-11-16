# Contribuindo com o Lockscreen Agents

Obrigado por ajudar! Este guia mostra como rodar o projeto, onde mexer e como enviar uma mudança.
**English summary at the bottom.**

## Preparando o ambiente

Precisa de Python 3.10 ou mais novo (com `tkinter`) e Git.

```bash
git clone https://github.com/andrrc/Lockscreen-Agents.git
cd Lockscreen-Agents
python -m venv .venv
```

Ative o ambiente (`.venv\Scripts\activate` no Windows, `source .venv/bin/activate` no macOS) e instale:

```bash
pip install -r requirements-dev.txt
```

## Rodando

```bash
python app.py              # bandeja (o app em si)
python app.py --settings   # janela de configurações
python app.py --saver /s --seconds 5   # protetor de tela por 5 segundos
```

Não precisa instalar nada: rode direto da pasta do projeto. Se você já tem o app instalado, feche-o
antes (só uma bandeja roda por vez).

## Testes e estilo

```bash
pytest
ruff check
```

Os dois precisam passar; o GitHub Actions roda ambos em Windows, macOS e Linux em todo pull request.
Os testes usam um sistema operacional **falso** (`tests/conftest.py`), então não dependem do seu PC.

## Onde fica cada coisa

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Em resumo:

- `lockscreen_agents/` é o app. Código que depende do sistema operacional fica **só** em
  `lockscreen_agents/platforms/`; o resto não pode usar `ctypes.windll`, `winreg`, `osascript` etc.
- `packaging/windows/` tem o executável e o instalador do Windows.
- `docs/` tem a documentação e as imagens do README. `tools/` gera essas imagens.

Quer portar para o macOS? Comece por [docs/MACOS.md](docs/MACOS.md).

## Regras do projeto

1. **Windows não pode quebrar.** O CI avisa, mas teste o que mexer nele.
2. **Textos novos em português e inglês**, em `lockscreen_agents/i18n.py`. Um teste confere que as duas
   línguas têm as mesmas chaves.
3. **Mudou o visual?** Anexe um print no pull request. A janela tira prints de si mesma:
   `python app.py --settings --shot pasta-de-saida` (salva uma imagem de cada página).
4. **Sem dependências novas** sem combinar antes; o app precisa continuar fácil de instalar.
5. O app **não lê o conteúdo** dos arquivos das ferramentas e **não usa a internet**. Mudanças que
   alterem isso precisam ser discutidas em uma issue primeiro.

## Enviando uma mudança

1. Crie um branch a partir do `main`: `git checkout -b macos-processos` (um assunto por branch).
2. Faça commits pequenos, com mensagem em português explicando o **porquê**.
3. Abra um pull request para o `main` e preencha o checklist. Não faça push direto no `main`.
4. Espere o CI ficar verde e a revisão.

## Publicando uma versão (mantenedor)

Troque o número em `lockscreen_agents/version.py`, faça commit e push, e crie a tag igual ao número:

```bash
git tag v0.2.0
git push origin v0.2.0
```

O workflow `release.yml` gera o instalador, o `.zip` portátil e os checksums e publica a Release.

---

## English summary

- Setup: Python 3.10+, `pip install -r requirements-dev.txt`, run with `python app.py`.
- `pytest` and `ruff check` must pass (CI runs them on Windows, macOS and Linux).
- OS-specific code lives only in `lockscreen_agents/platforms/`. Strings go in `i18n.py` in both
  languages. No new dependencies without discussion. The app never reads file contents or uses the network.
- Work on a branch, open a pull request to `main`, include a screenshot for UI changes
  (`python app.py --settings --shot out/`).
- macOS port: see [docs/MACOS.md](docs/MACOS.md).
