# Lockscreen Agents no macOS

O app roda em um Mac **pelo código-fonte** (ainda não há `.app` nem instalador) com os mesmos mascotes e
estados do Windows. Este documento diz o que já funciona, o que falta e como testar. Para quem vai
mexer no código, leia antes [ARCHITECTURE.md](ARCHITECTURE.md) e [CONTRIBUTING.md](../CONTRIBUTING.md).

## Onde estamos

- O port foi feito por um colaborador (PRs #1 e #2) e está na `main`. Tudo que depende do sistema
  operacional fica em `lockscreen_agents/platforms/macos.py`; o resto do app (detector, configurações,
  desenho dos mascotes, textos) é o mesmo do Windows.
- O CI roda `ruff` e `pytest` em `macos-latest`, mas os testes de macOS usam um papel de parede falso e
  saídas simuladas de `pmset`. Eles garantem a lógica, **não** o comportamento do `osascript`, do `ioreg`
  ou do Tk num Mac de verdade. Por isso a coluna Status abaixo diz o que foi realmente executado.
- Mudanças da versão 0.4.2: o app não troca mais o papel de parede se não conseguir ler o atual; guarda e
  devolve o papel de parede de **cada monitor**; o plist do início automático é gerado com `plistlib`
  (caminhos com `&` quebravam); textos e caminhos colocados em AppleScript são escapados.

## Como testar

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                  # deve passar
python app.py --settings                # a janela de configurações abre?
python app.py --saver /s --seconds 5    # o protetor cobre a tela e fecha com tecla ou mouse?
python app.py                           # bandeja (barra de menus)
```

Vá anotando o que quebra e abra uma issue ou um pull request pequeno (um item por PR facilita a revisão;
o Windows continua protegido pelo CI).

## Checklist (cada item é um método de `Platform`)

| # | Método | Como é no macOS | Status |
| --- | --- | --- | --- |
| 1 | `data_dir` | `~/Library/Application Support/LockscreenAgents` | pronto |
| 2 | `running_processes` | `ps -axo comm=` (nomes em minúsculas) | testado (Claude) |
| 3 | `PROCESS_NAMES`, `FOCUS_MATCH` | `claude`, `codex`, `cursor` e os `.app` correspondentes | Claude conferido; **verificar Codex e Cursor** |
| 4 | `idle_seconds` | `ioreg -c IOHIDSystem` (HIDIdleTime, em nanossegundos) | testado |
| 5 | `foreground_app_path` | `osascript` com System Events (pede permissão de Automação) | testado |
| 6 | `single_instance` | arquivo de trava com `fcntl.flock` | escrito, não conferido |
| 7 | `system_language`, `open_path` | `defaults read -g AppleLanguages`, `open` | escrito, não conferido |
| 8 | `autostart_*` | LaunchAgent em `~/Library/LaunchAgents`, gerado com `plistlib` | escrito; **conferir o início no login** |
| 9 | `ui_scale`, `monitors`, `make_fullscreen` | Tk com `-fullscreen`; escala 1.0 | **verificar** Retina e barra de título; cobre só o monitor principal |
| 10 | `session_locked` | `ioreg -n Root -d1 -a` (`CGSSessionScreenIsLocked`); sem sessão no console conta como bloqueado | escrito, em uso pelo app |
| 10 | `lock_session` | `pmset displaysleepnow` | **limitado**: só apaga a tela, não bloqueia de fato (veja abaixo) |
| 11 | `set_lock_screen`, `restore_lock_screen`, `has_pending_restore` | troca o papel de parede (opção "Mostrar na tela de bloqueio"); os originais ficam em `original_wallpaper.txt`, um por monitor | testado com um monitor; **leitura por monitor (System Events) ainda não conferida num Mac** |
| 12 | `display_sleep_blocked` | `pmset -g assertions` (`PreventUserIdleDisplaySleep`) para não abrir o protetor durante vídeo | lógica testada com saída simulada; **conferir com vídeo de verdade** |
| 13 | Empacotamento | `.app` com PyInstaller ou py2app, assinatura e notarização | **não feito** |

Ao terminar um item, atualize a coluna Status.

## A tela de bloqueio

No Windows existe uma API (`LockScreen.SetImageFileAsync`) que troca só a imagem da tela de bloqueio. No
macOS **não existe API pública equivalente**: a tela de bloqueio mostra o papel de parede da área de
trabalho. O que o app faz hoje:

- **Papel de parede, opcional.** Com **Configurações → Geral → Mostrar na tela de bloqueio** ligado, o
  app troca o papel de parede enquanto o Mac está bloqueado e devolve o original ao desbloquear, ao
  pausar, ao sair, pelo menu da bandeja ("Restaurar papel de parede original"), na próxima inicialização
  (se o app caiu) ou com `python app.py --restore-wallpaper`. Se o usuário trocar o papel de parede nesse
  meio-tempo, o app respeita a escolha e não restaura. Se não conseguir ler o papel de parede atual, não
  troca nada.
- **Protetor de tela.** O protetor em Tkinter funciona igual ao do Windows e é aberto pela bandeja quando
  o Mac fica parado. Não abre durante vídeo, chamada ou apresentação.
- **Protetor nativo (`.saver`)** continua sendo uma opção futura: ele apareceria nas configurações do
  macOS, mas exige Objective-C/Swift e é outro projeto.

### Bloquear o Mac ao fechar o protetor

A opção "bloquear o PC ao fechar" chama `pmset displaysleepnow`, que só apaga a tela. O Mac pede senha ao
acordar apenas se **Ajustes do Sistema → Tela de bloqueio → Exigir senha** estiver em "imediatamente".
Bloquear de fato (por exemplo com `CGSession -suspend`, que some nas versões novas, ou via Quartz) ainda
precisa ser avaliado em um Mac.

## Pontos de atenção

- **Permissões do macOS.** Ler a janela em foco e trocar o papel de parede passam pelo System Events e pelo
  Finder, que pedem **Automação**. Se o usuário negar, o app continua (só sem o sinal de foco); veja
  `detector.get_states`, que ignora falhas dessa leitura, e `tray.worker`, que registra o erro e tenta de
  novo.
- **Tkinter e a bandeja.** No macOS, `pystray` e o Tkinter querem a thread principal. Por isso a janela de
  configurações e o protetor são processos separados (`launcher.command`). Se a bandeja der problema,
  investigue o backend do `pystray` (`pystray._darwin`) e o `LSUIElement` (app sem ícone no Dock).
- **Tela cheia.** O protetor usa `-fullscreen` e `-topmost` do Tk, que cobre só o monitor principal.
  `monitors()` ainda é o padrão da base.
- **Onde as ferramentas gravam.** O detector olha `~/.claude/projects`, `~/.codex/sessions`, `~/.cursor` e `~/.gemini/tmp`.
  Confirme se são os mesmos no macOS; se não forem, deixe isso por plataforma, não com `if sys.platform`.
- **Fontes.** `render.py` usa `FONTS` da plataforma (SF e Helvetica no macOS) e cai na fonte padrão do
  Pillow se não achar.
- **A janela de configurações** foi desenhada em pixels e testada sobretudo no Windows. Espere ajustes de
  escala, fontes e da barra de título.
- **Empacotamento.** O instalador atual (`packaging/windows/`) é só do Windows. Para o Mac, crie
  `packaging/macos/` e um job no `release.yml` em `macos-latest`. Sem assinatura e notarização da Apple o
  Gatekeeper vai avisar, como o SmartScreen faz no Windows.

## Como saber que está pronto

- [x] `pytest` e `ruff check` passam no CI em macOS e Windows.
- [ ] Os três estados (em uso, ocioso, fechado) aparecem certos para as ferramentas instaladas no Mac
  (Claude conferido; falta Codex e Cursor).
- [ ] O protetor abre quando o Mac fica parado e fecha com tecla ou mouse, em Retina e com vários monitores.
- [ ] A bandeja (barra de menus) mostra o ícone e abre as configurações.
- [ ] Início automático liga e desliga pela janela e o app abre no login.
- [ ] A troca do papel de parede funciona e restaura com vários monitores.
- [ ] Existe um `.app` (ou outro jeito de instalar) e a release dele.
- [x] `README.md` diz o que funciona no macOS e o que não funciona.
