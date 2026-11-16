# Arquitetura

## Estrutura de pastas

```
app.py                      entrada na raiz: python app.py [--settings | --saver /s]
lockscreen_agents/          o app
  app.py                    escolhe o modo (bandeja, configurações ou protetor)
  tray.py                   bandeja: lê o estado, atualiza a lock screen, abre o protetor
  settings_ui.py            janela de configurações (Tkinter, controles desenhados à mão)
  saver.py                  protetor de tela animado (Tkinter em tela cheia)
  detector.py               descobre o estado de cada ferramenta
  render.py                 desenha os mascotes e a imagem da lock screen
  settings.py               settings.json com validação
  i18n.py                   textos em português e inglês
  templates.py              lista dos modelos (visuais)
  logo.py                   a logo e o ícone da bandeja
  launcher.py               como o app chama a si mesmo (código-fonte ou .exe)
  autostart.py              início automático (usa a plataforma)
  platforms/                TUDO que depende do sistema operacional
    base.py                 o contrato (classe Platform)
    windows.py              implementação para Windows
    macos.py                rascunho para macOS
packaging/windows/          build_exe.py (PyInstaller), installer.iss (Inno Setup), install.py
tools/                      gera as imagens do README
tests/                      pytest (com um sistema operacional falso)
```

## Três processos

O app roda como processos separados, todos iniciados pelo mesmo programa (`app.py`, ou o `.exe`):

| Processo | Comando | O que faz |
| --- | --- | --- |
| Bandeja | `app.py` | Fica sempre aberto. A cada 3 s lê o estado, redesenha a lock screen se mudou e abre o protetor quando o PC fica parado. |
| Configurações | `app.py --settings` | Abre pelo menu da bandeja. Só uma por vez. |
| Protetor | `app.py --saver /s` | Aberto pela bandeja; fecha com qualquer tecla ou movimento. |

Eles conversam por **arquivos** na pasta de dados (no Windows, `%LOCALAPPDATA%\LockscreenAgents`):

- `settings.json`: gravado pela janela de configurações; todos leem. A bandeja percebe a mudança sozinha.
- `status.json`: gravado pela bandeja a cada leitura (estado + sinais); a página "Como funciona" lê.
- `log.txt`, `saver.log`, `settings_ui.log`: registros.
- `lock_0.png` / `lock_1.png`: a imagem da lock screen, alternando o nome porque o Windows guarda cache pelo caminho.

## Fluxo da detecção

```
detector.get_states()
  ├─ arquivos das ferramentas (data de modificação)   -> detector.SOURCES (igual em todo sistema)
  ├─ programas abertos                                -> platform.running_processes()
  └─ janela em foco + teclado/mouse                   -> platform.foreground_app_path(), idle_seconds()
        │
        ▼  estado de cada ferramenta: working | open | closed | off
tray.App.worker
  ├─ render.render(estado) -> imagem -> platform.set_lock_screen()
  ├─ escreve status.json
  └─ abre o protetor quando idle >= configurado
```

As regras (em uso, ocioso, fechado) e seus tempos ficam em `detector.get_states` e em
`settings.py`; veja também a página "Como funciona" do app.

## A camada de plataforma

`platforms/base.py` define a classe `Platform` com tudo que o app precisa do sistema operacional.
`platforms.current()` devolve a implementação do sistema atual. Regras:

- O resto do código **nunca** importa `ctypes.windll`, `winreg` ou chama `osascript` direto.
- Um método novo entra primeiro em `base.py`, depois em **todas** as plataformas. O teste
  `tests/test_platforms.py` falha se alguma deixar de implementar um método obrigatório.

## Como adicionar...

**Um modelo (visual) novo**

1. Em `templates.py`, acrescente `{"id": "meu-modelo", "available": False}` (aparece como "em breve").
2. Em `i18n.py`, crie `tpl.meu-modelo.n` (nome) e `tpl.meu-modelo.d` (descrição) em pt e en.
3. Opcional: um desenho de conceito em `settings_ui.concept_preview`.
4. Para lançar: escreva a função que desenha o modelo (como `render.render`), faça `tray.py` e
   `saver.py` escolherem o desenho pela chave `template` das configurações e troque `available` para `True`.

**Uma ferramenta nova (além de Claude Code, Codex e Cursor)**

1. `settings.TOOLS` e a função de atividade em `detector.SOURCES`.
2. Nomes de processo e janela em cada plataforma (`PROCESS_NAMES`, `FOCUS_MATCH`).
3. Mascote em `render.py` (`draw_*`, a cor em `ACCENT` e `makers` dentro de `render`), `saver.SPECS`
   e `settings_ui.mascot`.
4. Textos `tool.<id>` e `tools.<id>.desc` em `i18n.py`.

**Um idioma novo**

Acrescente um dicionário em `i18n.STRINGS` com as mesmas chaves do português (um teste confere),
inclua o código em `settings._clean` e na página Geral da janela.

## Decisões que valem saber

- **Tkinter** em vez de um framework de interface: nenhuma dependência extra. A janela de
  configurações desenha seus próprios controles com Pillow para ficar com bordas suaves e animações.
- **Processos separados** para janela e protetor: o Tkinter e a bandeja não convivem bem na mesma
  thread principal, e uma janela travada não derruba a bandeja.
- **Dois jeitos de iniciar com o Windows** (chave `Run` e atalho na pasta Inicializar): num logon o
  Windows ignorou o `Run`. O mutex da bandeja evita cópia dupla.
- **Executável em modo pasta** (PyInstaller `--onedir`): abre mais rápido e gera menos alertas de
  antivírus que o arquivo único.
