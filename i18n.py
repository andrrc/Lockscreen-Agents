"""Textos do app em português e inglês. `t("chave")` usa o idioma das configurações
("auto" segue o idioma do Windows)."""
import ctypes

import settings

STRINGS = {
    "pt": {
        # estados dos mascotes
        "state.working": "em uso", "state.open": "ocioso", "state.closed": "fechado",
        "tool.claude": "Claude Code", "tool.codex": "Codex", "tool.cursor": "Cursor",
        # bandeja
        "tray.waiting": "Aguardando...",
        "tray.settings": "Configurações…",
        "tray.pause": "Pausar",
        "tray.refresh": "Atualizar lock screen agora",
        "tray.saver": "Protetor de tela animado",
        "tray.test": "Testar protetor agora",
        "tray.folder": "Abrir pasta do app",
        "tray.quit": "Sair",
        # janela
        "ui.title": "Lockscreen Agents",
        "ui.subtitle": "Configurações",
        "nav.overview": "Visão geral",
        "nav.tools": "Ferramentas",
        "nav.detection": "Detecção",
        "nav.saver": "Protetor de tela",
        "nav.general": "Geral",
        "ui.saved": "Salvo",
        "ui.footer": "Projeto não oficial, sem vínculo com Anthropic, OpenAI ou Anysphere.",
        # visão geral
        "ov.title": "Visão geral",
        "ov.sub": "Veja o que está acontecendo agora, ao vivo.",
        "ov.preview": "Prévia da tela de bloqueio",
        "ov.live": "ao vivo",
        "ov.test": "Testar protetor de tela",
        "ov.off": "desligado",
        # ferramentas
        "tools.title": "Ferramentas",
        "tools.sub": "Escolha quais assistentes aparecem nos mascotes.",
        "tools.claude.desc": "Terminal e app desktop. Observa a pasta .claude do seu usuário.",
        "tools.codex.desc": "App e CLI da OpenAI. Observa a pasta .codex do seu usuário.",
        "tools.cursor.desc": "Editor com agente de IA. Observa a pasta .cursor do seu usuário.",
        "tools.min": "Pelo menos uma ferramenta precisa ficar ligada.",
        # detecção
        "det.title": "Detecção",
        "det.sub": "Ajuste quando uma ferramenta conta como em uso, ociosa ou fechada.",
        "det.active.t": "Tempo até ficar ocioso",
        "det.active.d": "Quanto tempo sem atividade nos arquivos antes de virar ocioso.",
        "det.follow.t": "Considerar a janela em foco",
        "det.follow.d": "Conta como em uso quando a janela da ferramenta está na frente e você está ativo.",
        "det.hold.t": "Manter em uso ao sair da janela",
        "det.hold.d": "Por quanto tempo continua em uso depois de você trocar de janela.",
        "det.grace.t": "Tolerância para fechado",
        "det.grace.d": "Quanto tempo sem ver o programa até marcar como fechado.",
        # protetor
        "sv.title": "Protetor de tela",
        "sv.sub": "Os mascotes em tela cheia quando o PC fica parado.",
        "sv.on.t": "Protetor animado",
        "sv.on.d": "Abre sozinho depois de um tempo sem usar o PC. Qualquer tecla ou movimento fecha.",
        "sv.idle.t": "Abrir após",
        "sv.idle.d": "Tempo sem mexer no teclado ou no mouse.",
        "sv.lock.t": "Bloquear o PC ao fechar",
        "sv.lock.d": "Pede a senha ao sair do protetor. Deixe desligado se você acessa o PC remotamente.",
        "sv.test": "Testar agora",
        # geral
        "gen.title": "Geral",
        "gen.sub": "Idioma, início automático e dados do app.",
        "gen.lang.t": "Idioma",
        "gen.lang.d": "Idioma desta janela, da bandeja e dos textos dos mascotes.",
        "gen.lang.auto": "Automático", "gen.lang.pt": "Português", "gen.lang.en": "English",
        "gen.start.t": "Iniciar com o Windows",
        "gen.start.d": "Abre o app na bandeja quando você entra no PC.",
        "gen.folder.t": "Pasta de dados",
        "gen.folder.d": "Registros e imagens geradas pelo app.",
        "gen.folder.b": "Abrir",
        "gen.reset.t": "Restaurar padrões",
        "gen.reset.d": "Volta todas as configurações ao que vem de fábrica.",
        "gen.reset.b": "Restaurar", "gen.reset.c": "Confirmar?",
        # unidades
        "unit.s": "{n} s", "unit.min": "{n} min", "unit.min_s": "{m} min {s} s",
        "unit.off": "desligado",
    },
    "en": {
        "state.working": "in use", "state.open": "idle", "state.closed": "closed",
        "tool.claude": "Claude Code", "tool.codex": "Codex", "tool.cursor": "Cursor",
        "tray.waiting": "Waiting...",
        "tray.settings": "Settings…",
        "tray.pause": "Pause",
        "tray.refresh": "Refresh lock screen now",
        "tray.saver": "Animated screensaver",
        "tray.test": "Test screensaver now",
        "tray.folder": "Open app folder",
        "tray.quit": "Quit",
        "ui.title": "Lockscreen Agents",
        "ui.subtitle": "Settings",
        "nav.overview": "Overview",
        "nav.tools": "Tools",
        "nav.detection": "Detection",
        "nav.saver": "Screensaver",
        "nav.general": "General",
        "ui.saved": "Saved",
        "ui.footer": "Unofficial project, not affiliated with Anthropic, OpenAI or Anysphere.",
        "ov.title": "Overview",
        "ov.sub": "See what is happening right now, live.",
        "ov.preview": "Lock screen preview",
        "ov.live": "live",
        "ov.test": "Test screensaver",
        "ov.off": "off",
        "tools.title": "Tools",
        "tools.sub": "Choose which assistants show up as mascots.",
        "tools.claude.desc": "Terminal and desktop app. Watches your user's .claude folder.",
        "tools.codex.desc": "OpenAI app and CLI. Watches your user's .codex folder.",
        "tools.cursor.desc": "Editor with an AI agent. Watches your user's .cursor folder.",
        "tools.min": "At least one tool has to stay on.",
        "det.title": "Detection",
        "det.sub": "Tune when a tool counts as in use, idle or closed.",
        "det.active.t": "Time until idle",
        "det.active.d": "How long without file activity before a tool becomes idle.",
        "det.follow.t": "Use the focused window",
        "det.follow.d": "Counts as in use when the tool's window is in front and you are active.",
        "det.hold.t": "Keep in use after leaving the window",
        "det.hold.d": "How long it stays in use after you switch to another window.",
        "det.grace.t": "Grace before closed",
        "det.grace.d": "How long without seeing the program before it is marked closed.",
        "sv.title": "Screensaver",
        "sv.sub": "The mascots in fullscreen when the PC sits idle.",
        "sv.on.t": "Animated screensaver",
        "sv.on.d": "Opens on its own after a while without using the PC. Any key or mouse move closes it.",
        "sv.idle.t": "Open after",
        "sv.idle.d": "Time without touching the keyboard or mouse.",
        "sv.lock.t": "Lock the PC when it closes",
        "sv.lock.d": "Asks for your password when leaving the screensaver. Keep it off if you use the PC remotely.",
        "sv.test": "Test now",
        "gen.title": "General",
        "gen.sub": "Language, autostart and app data.",
        "gen.lang.t": "Language",
        "gen.lang.d": "Language of this window, the tray menu and the mascot labels.",
        "gen.lang.auto": "Automatic", "gen.lang.pt": "Português", "gen.lang.en": "English",
        "gen.start.t": "Start with Windows",
        "gen.start.d": "Opens the app in the tray when you sign in.",
        "gen.folder.t": "Data folder",
        "gen.folder.d": "Logs and images generated by the app.",
        "gen.folder.b": "Open",
        "gen.reset.t": "Restore defaults",
        "gen.reset.d": "Sets every option back to the factory values.",
        "gen.reset.b": "Restore", "gen.reset.c": "Confirm?",
        "unit.s": "{n} s", "unit.min": "{n} min", "unit.min_s": "{m} min {s} s",
        "unit.off": "off",
    },
}


def system_lang():
    """'pt' se o Windows está em português, senão 'en'."""
    try:
        return "pt" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x16 else "en"
    except Exception:  # noqa: BLE001
        return "en"


def lang():
    choice = settings.get().get("lang", "auto")
    return choice if choice in STRINGS else system_lang()


def t(key, **kw):
    text = STRINGS.get(lang(), STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**kw) if kw else text


def duration(seconds):
    """'45 s', '3 min', '2 min 30 s'."""
    seconds = int(round(seconds))
    if seconds < 60:
        return t("unit.s", n=seconds)
    m, s = divmod(seconds, 60)
    return t("unit.min", n=m) if s == 0 else t("unit.min_s", m=m, s=s)
