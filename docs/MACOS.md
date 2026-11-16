# Guia do port para macOS

Objetivo: rodar o Lockscreen Agents em um Mac, com os mesmos mascotes e estados do Windows.
Este guia é para quem vai fazer o port. Leia antes [ARCHITECTURE.md](ARCHITECTURE.md) e
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Onde estamos

O app foi escrito no Windows, e **nada foi executado em um Mac ainda**. O trabalho de preparação:

- Tudo que depende do sistema operacional foi isolado em `lockscreen_agents/platforms/`.
- `platforms/macos.py` é um **rascunho**: as chamadas mais prováveis estão escritas, mas nenhuma foi
  testada. Cada ponto incerto está marcado com `TODO(macos)`.
- O CI (`.github/workflows/ci.yml`) já roda os testes em `macos-latest`. O resto do app (detector,
  configurações, desenho dos mascotes, textos) não depende de sistema e deve funcionar como está.

## Primeiros passos

```bash
git checkout -b macos
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                       # deve passar
python app.py --settings     # a janela de configurações abre?
python app.py --saver /s --seconds 5
python app.py                # bandeja
```

Vá anotando o que quebra. A ordem sugerida abaixo vai do mais fácil ao mais difícil.

## Checklist (cada item é um método de `Platform`)

| # | Método | Ideia para o macOS | Status |
| --- | --- | --- | --- |
| 1 | `data_dir` | `~/Library/Application Support/LockscreenAgents` | escrito |
| 2 | `running_processes` | `ps -axo comm=` (nomes em minúsculas) | testado (Claude) |
| 3 | `PROCESS_NAMES`, `FOCUS_MATCH` | conferir os nomes reais: Claude, Codex e Cursor | **verificar** |
| 4 | `idle_seconds` | `ioreg -c IOHIDSystem` (HIDIdleTime, em nanossegundos) | testado |
| 5 | `foreground_app_path` | `osascript` com System Events (pede permissão de Automação) | testado |
| 6 | `single_instance` | arquivo de trava com `fcntl.flock` | rascunho |
| 7 | `system_language`, `open_path` | `defaults read -g AppleLanguages`, `open` | rascunho |
| 8 | `autostart_*` | LaunchAgent em `~/Library/LaunchAgents` | rascunho |
| 9 | `ui_scale`, `style_window`, `monitors` | Tk no macOS: conferir tela Retina, barra de título, várias telas | **verificar** |
| 10 | `session_locked`, `lock_session` | Quartz (`CGSSessionScreenIsLocked`); bloquear a tela | **TODO** |
| 11 | `set_lock_screen` | troca o papel de parede (opt-in `lock_wallpaper`) e restaura o original | testado (osascript) |
| 12 | Empacotamento | `.app` com PyInstaller ou py2app, assinatura e notarização | **TODO** |

Ao terminar um item, atualize a coluna Status e abra um pull request pequeno. Um item por PR facilita
a revisão (e o Windows continua protegido pelo CI).

## O problema da tela de bloqueio (item 11)

No Windows existe uma API (`LockScreen.SetImageFileAsync`) que troca só a imagem da tela de bloqueio.
No macOS **não existe API pública equivalente**: a tela de bloqueio mostra o papel de parede da área de
trabalho. Opções a avaliar, de preferência conversando em uma issue antes:

1. **Trocar o papel de parede** com a imagem gerada (`osascript` ou NSWorkspace
   `setDesktopImageURL`). É simples e funciona, mas altera o papel de parede do usuário o tempo todo.
   Se for por aqui, precisa de uma opção clara nas configurações e de restaurar o original ao sair.
2. **Só o protetor de tela** no macOS (sem alterar a lock screen). O protetor em Tkinter já existe e
   é disparado pela bandeja quando o Mac fica parado; seria o recurso principal do port.
3. **Protetor nativo (`.saver`)**, que aparece nas configurações do macOS. Mais integrado, mas exige
   Objective-C/Swift e é outro projeto.

Qualquer uma delas cabe no contrato: se escolher a 2, `set_lock_screen` pode ser um método que não
faz nada, e o app precisa continuar funcionando (hoje ele loga o erro e tenta de novo a cada ciclo,
então vale tratar isso em `tray.apply`).

## Pontos de atenção

- **Permissões do macOS.** Ler a janela em foco com `osascript` pode exigir Automação/Acessibilidade.
  O app deve funcionar (só sem o sinal de foco) se o usuário negar; veja `detector.get_states`, que já
  ignora falhas dessa leitura.
- **Tkinter e a bandeja.** No macOS, `pystray` e o Tkinter querem a thread principal. Por isso a janela
  de configurações e o protetor são processos separados (`launcher.command`). Se a bandeja der problema,
  investigue o backend do `pystray` (`pystray._darwin`) e o `LSUIElement` (app sem ícone no Dock).
- **Tela cheia.** O protetor usa `overrideredirect` + `-topmost` do Tk; no macOS o comportamento é
  diferente (menu e Dock podem continuar visíveis). Pode precisar de ajuste.
- **Onde as ferramentas gravam.** O detector olha `~/.claude/projects`, `~/.codex/sessions` e `~/.cursor`.
  Confirme se esses caminhos são os mesmos no macOS; se não forem, ajuste em `detector.py` (e deixe
  isso por plataforma, não com `if sys.platform`).
- **Fontes.** `render.py` procura `segoeui.ttf` e cai em `arial.ttf`. No macOS isso provavelmente cai na
  fonte padrão do Pillow; vale escolher uma fonte do sistema por plataforma.
- **A janela de configurações** foi desenhada em pixels e testada só no Windows. Espere ajustes de
  escala, fontes e da barra de título.
- **Empacotamento.** O instalador atual (`packaging/windows/`) é só do Windows. Para o Mac, crie
  `packaging/macos/` e um job no `release.yml` em `macos-latest`. Sem assinatura/notarização da Apple o
  Gatekeeper vai avisar, como o SmartScreen faz no Windows.

## Como saber que está pronto

- `pytest` e `ruff check` passam no CI em macOS e Windows.
- Os três estados (em uso, ocioso, fechado) aparecem certos para as ferramentas instaladas no Mac.
- O protetor abre quando o Mac fica parado e fecha com tecla ou mouse.
- A bandeja (barra de menus) mostra o ícone e abre as configurações.
- Início automático liga e desliga pela janela.
- `README.md` diz o que funciona no macOS e o que não funciona.
