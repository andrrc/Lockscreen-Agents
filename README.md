# Lockscreen Agents

**Português** · [English](#english)

Mascotes na tela de bloqueio e no protetor de tela do Windows que mostram, num relance, quais assistentes de código você está usando: **Claude Code**, **Codex** e **Cursor**.

![Lock screen com os três mascotes em uso](docs/lock-all-active.png)

| Estado | Como aparece |
| --- | --- |
| **em uso** | mascote colorido (no protetor de tela ele anda; o Cursor flutua) |
| **ocioso** | ferramenta aberta, sem atividade: mascote cinza e parado |
| **fechado** | ferramenta não está rodando: mascote bem apagado |

![Estados: em uso, ocioso e fechado](docs/lock-states.png)

> Projeto **não oficial**. Não tem vínculo com a Anthropic, a OpenAI nem a Anysphere (Cursor). Os mascotes são desenhos próprios, inspirados nas ferramentas. Claude, Codex e Cursor são marcas dos respectivos donos.

## O que faz

- **Tela de bloqueio**: gera uma imagem com o estado de cada ferramenta e a define como lock screen sempre que o estado muda. Aperte `Win + L` e veja.
- **Protetor de tela animado**: depois de alguns minutos sem mexer no PC, abre uma tela cheia com os mascotes animados. Qualquer tecla ou movimento do mouse fecha.
- **Ícone na bandeja** (perto do relógio) com menu para pausar, forçar atualização, ligar ou desligar o protetor e escolher depois de quantos minutos ele abre.
- Inicia junto com o Windows.

## Requisitos

- Windows 10 ou 11
- Python 3.10 ou mais novo, com `tkinter` (já vem no instalador oficial de python.org)
- A tela de bloqueio precisa estar em **Configurações → Personalização → Tela de bloqueio → Personalizar sua tela de bloqueio: Imagem**. No modo "Windows Spotlight" o Windows ignora a imagem do app.

## Instalação

```bash
git clone https://github.com/andrrc/lockscreen-agents.git
cd lockscreen-agents
pip install -r requirements.txt
python install.py
```

O `install.py` copia o app para `%LOCALAPPDATA%\LockscreenAgents`, liga o início automático (chave `Run` do registro e atalho na pasta Inicializar) e abre o app. Procure o ícone do mascote perto do relógio. Pode apagar a pasta do projeto depois, o app instalado não depende dela.

Sem usar Git: baixe o ZIP em **Releases** (ou em *Code → Download ZIP*), extraia e rode os dois últimos comandos acima.

Para remover:

```bash
python install.py --uninstall
```

Isso desliga o início automático e fecha o app. A pasta `%LOCALAPPDATA%\LockscreenAgents` fica; apague se quiser.

## Como ele sabe que a ferramenta está em uso

Tudo local, sem login e sem internet. O app **não lê o conteúdo** de nada, só olha:

- a **data de modificação** dos arquivos que cada ferramenta grava enquanto responde: `~/.claude/projects/*/*.jsonl`, `~/.codex/sessions/AAAA/MM/DD/*.jsonl` e arquivos de `~/.cursor`;
- a **lista de processos** (`claude.exe`, `codex.exe`, `cursor.exe`) para saber se está aberta;
- **qual janela está em foco** e se você mexeu no teclado ou mouse nos últimos 3 minutos. O Cursor, por exemplo, quase não grava arquivos enquanto você só edita código.

Regras: arquivo mudou nos últimos 3 minutos ou janela da ferramenta em foco (com você ativo, e por mais 2 minutos depois de perder o foco) → **em uso**. Processo aberto, sem atividade → **ocioso**. Sem processo por mais de 25 segundos → **fechado**. Os números ficam no topo do `detector.py`.

## Limitações

- Só Windows. A lock screen é uma **imagem estática** atualizada a cada mudança de estado, não uma animação. A animação fica no protetor de tela.
- O protetor é aberto pelo próprio app quando o PC fica parado (não é um arquivo `.scr`).
- Os textos dos mascotes (“em uso”, “ocioso”, “fechado”) estão em português. Traduções são bem-vindas.
- Se o app não aparecer na bandeja depois de reiniciar o PC, abra `%LOCALAPPDATA%\LockscreenAgents\log.txt` e rode `python install.py` de novo.

## Estrutura

| Arquivo | Função |
| --- | --- |
| `detector.py` | descobre o estado de cada ferramenta |
| `render.py` | desenha os mascotes e a imagem da lock screen |
| `lockscreen.py` | aplica a imagem como lock screen (API WinRT) |
| `saver.py` | protetor de tela animado (Tk) |
| `tray.py` | app da bandeja, junta tudo |
| `install.py` | instala, liga o autostart e remove |
| `make_demo.py` | regenera as imagens da pasta `docs/` |

## Contribuindo

Issues e PRs são bem-vindos: novos mascotes ou ferramentas, traduções, melhorias na detecção. Para testar sem instalar, rode `python tray.py` na pasta do projeto.

## Licença

[MIT](LICENSE)

---

## English

Mascots on the Windows lock screen and screensaver that show at a glance which AI coding assistants you are using: **Claude Code**, **Codex** and **Cursor**.

- **in use** (labelled “em uso”): colored mascot (walking in the screensaver, Cursor floats)
- **idle** (“ocioso”): tool is open but quiet, gray and still
- **closed** (“fechado”): tool is not running, very dim

> **Unofficial** project, not affiliated with Anthropic, OpenAI or Anysphere (Cursor). The mascots are original drawings inspired by the tools. Claude, Codex and Cursor are trademarks of their respective owners.

![Claude Code mascot walking](docs/demo-claude.gif)

### Features

- **Lock screen**: renders an image with each tool's state and sets it as your lock screen whenever the state changes. Press `Win + L` to see it.
- **Animated screensaver**: after a few idle minutes, a fullscreen scene with the animated mascots. Any key or mouse move closes it.
- **Tray icon** with a menu to pause, force a refresh, toggle the screensaver and pick the idle delay.
- Starts with Windows.

### Requirements

- Windows 10 or 11
- Python 3.10+ with `tkinter` (included in the python.org installer)
- Lock screen set to **Picture** (Settings → Personalization → Lock screen). Windows ignores the image in “Windows Spotlight” mode.

### Install

```bash
git clone https://github.com/andrrc/lockscreen-agents.git
cd lockscreen-agents
pip install -r requirements.txt
python install.py
```

`install.py` copies the app to `%LOCALAPPDATA%\LockscreenAgents`, enables autostart (registry `Run` key plus a Startup-folder shortcut) and launches it. Look for the mascot icon near the clock. No Git? Download the ZIP from **Releases**, extract it and run the last two commands.

Uninstall with `python install.py --uninstall`.

### How it detects usage

Fully local, no login, no network. It never reads file contents, only:

- **modification times** of files each tool writes while it is answering (`~/.claude/projects`, `~/.codex/sessions`, `~/.cursor`);
- the **process list** (`claude.exe`, `codex.exe`, `cursor.exe`);
- the **foreground window**, plus whether you used the keyboard or mouse in the last 3 minutes.

Recent file activity or the tool in focus while you are active → **in use**. Process running, no activity → **idle**. No process for 25+ seconds → **closed**. Thresholds are constants at the top of `detector.py`.

### Limitations

- Windows only. The lock screen is a **static image** refreshed on state changes; the animation lives in the screensaver, which the tray app launches when the PC is idle (it is not a `.scr` file).
- On-screen labels are in Portuguese. Translations are welcome.

### License

[MIT](LICENSE)
