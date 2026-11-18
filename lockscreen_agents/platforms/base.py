"""Contrato entre o app e o sistema operacional.

Todo código que só funciona em um sistema (Windows, macOS...) fica dentro de uma subclasse de
`Platform`. O resto do app (detector, janelas, bandeja) só chama os métodos abaixo; nunca usa
`ctypes.windll`, `winreg`, `osascript` etc. diretamente.

Para portar o app para outro sistema: crie `platforms/<sistema>.py` com uma subclasse, preencha
os métodos e registre-a em `platforms/__init__.py`. Veja docs/MACOS.md.
"""
from pathlib import Path


class Platform:
    name = "unknown"

    # Nomes de processo (minúsculos) de cada ferramenta, usados para saber se estão abertas.
    PROCESS_NAMES = {"claude": set(), "codex": set(), "cursor": set(), "gemini": set()}

    # Como reconhecer a janela em foco de cada ferramenta: (nomes de executável, trechos do caminho).
    FOCUS_MATCH = {"claude": (set(), ()), "codex": (set(), ()), "cursor": (set(), ()), "gemini": (set(), ())}

    # Fontes (caminho ou nome de arquivo) tentadas em ordem pelo render; cai na padrão do Pillow.
    FONTS = ("segoeui.ttf", "arial.ttf")

    # True se trocar a imagem da tela de bloqueio mexe em algo do usuário (ex.: o papel de parede
    # no macOS). Então o app só chama set_lock_screen com a opção "lock_wallpaper" ligada.
    LOCK_SCREEN_OPT_IN = False

    # True se a imagem só deve ser aplicada enquanto a tela está bloqueada (e desfeita ao
    # desbloquear), para não deixar o papel de parede do usuário trocado o dia todo.
    LOCK_SCREEN_WHILE_LOCKED = False

    # ---- dados do app
    def data_dir(self) -> Path:
        """Pasta onde o app guarda configurações, logs e imagens (criada pelo chamador)."""
        raise NotImplementedError

    # ---- leitura do sistema (detector)
    def running_processes(self) -> set:
        """Nomes (minúsculos) dos programas em execução, no mesmo formato de PROCESS_NAMES."""
        raise NotImplementedError

    def foreground_app_path(self) -> str:
        """Caminho (minúsculo) do programa da janela em foco, ou '' se não der para saber."""
        raise NotImplementedError

    def idle_seconds(self) -> float:
        """Segundos desde o último teclado/mouse."""
        raise NotImplementedError

    def session_locked(self) -> bool:
        """True se a tela está bloqueada ou o usuário não está na sessão ativa."""
        raise NotImplementedError

    # ---- ações
    def set_lock_screen(self, image_path) -> None:
        """Define a imagem como tela de bloqueio."""
        raise NotImplementedError

    def restore_lock_screen(self) -> bool:
        """Desfaz set_lock_screen quando a plataforma alterou algo do usuário (padrão: nada).
        True se devolveu algo; False se não havia o que desfazer. Levanta erro se falhar."""
        return False

    def has_pending_restore(self) -> bool:
        """True se um set_lock_screen anterior (talvez de outra execução do app) ainda não foi
        desfeito. Lê do disco, não da memória: o app pode ter fechado sem restaurar."""
        return False

    def display_sleep_blocked(self) -> bool:
        """True se algo (vídeo, chamada, apresentação) está pedindo para a tela ficar acesa. O
        protetor não deve abrir nesse caso: ver o vídeo não conta como mexer no PC. Em caso de
        dúvida, devolva False."""
        return False

    def lock_session(self) -> None:
        """Bloqueia o computador agora."""
        raise NotImplementedError

    def open_path(self, path) -> None:
        """Abre uma pasta ou arquivo no gerenciador de arquivos."""
        raise NotImplementedError

    def system_language(self) -> str:
        """'pt' se o sistema está em português, senão 'en'."""
        return "en"

    def single_instance(self, name: str) -> bool:
        """Tenta marcar 'esta é a única instância de `name`'. False se já havia outra rodando."""
        raise NotImplementedError

    # ---- início automático
    def autostart_is_enabled(self) -> bool:
        raise NotImplementedError

    def autostart_enable(self, command, icon=None) -> bool:
        """Liga o início automático com `command` (lista de argumentos). `icon`: caminho opcional."""
        raise NotImplementedError

    def autostart_disable(self) -> None:
        raise NotImplementedError

    # ---- janelas (Tkinter)
    def python_gui(self) -> str:
        """Executável do Python sem janela de console, para iniciar o app a partir do código-fonte."""
        import sys
        return sys.executable

    def init_ui_process(self, app_id: str) -> None:
        """Chamado antes de criar qualquer janela: DPI, identidade do app na barra de tarefas..."""

    def ui_scale(self, root) -> float:
        """Fator de escala (1.0 = 100%). Windows: dpi/96; macOS: 1.0."""
        return 1.0

    def style_window(self, root, bg, fg, border) -> None:
        """Opcional: personaliza a barra de título (cores em tuplas RGB)."""

    def focus_window(self, title: str) -> None:
        """Opcional: traz para a frente a janela com este título."""

    def monitors(self, root) -> list:
        """Lista de telas como (esquerda, topo, direita, base) em pixels."""
        return [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]

    def make_fullscreen(self, root, rect) -> None:
        """Cobre `rect` (esquerda, topo, direita, base) com a janela, sem borda e por cima de tudo."""
        left, top, right, bottom = rect
        root.overrideredirect(True)
        root.geometry(f"{right - left}x{bottom - top}+{left}+{top}")
        root.attributes("-topmost", True)

    def show_message(self, title: str, text: str) -> None:
        """Mostra uma caixa de mensagem simples."""
        print(f"{title}: {text}")

    def stop_app_processes(self, patterns) -> list:
        """Encerra processos do app (usado ao reinstalar). Devolve uma descrição do que fechou."""
        return []
