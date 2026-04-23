from __future__ import annotations

from ursina import Entity, Ursina, window
from panda3d.core import WindowProperties

from engineBase import ActionState, GameBase as _EngineGameBase


class UrsinaGameBase(_EngineGameBase):
    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

        original_make_editor_gui = window.make_editor_gui
        window.make_editor_gui = lambda *args, **kwargs: None
        try:
            # IMPORTANT: always use the normal windowed path
            self.app = Ursina(
                development_mode=False,
                editor_ui_enabled=False,
                fullscreen=False,
                borderless=False,
                size=(self.width, self.height),
            )

            window.title = self.name
            window.size = (self.width, self.height)
            window.borderless = False

            if headless:
                props = WindowProperties()
                props.setUndecorated(True)
                props.setOrigin(-20000, -20000)   # move off-screen
                props.setSize(self.width, self.height)
                props.setCursorHidden(True)
                self.app.win.requestProperties(props)

        finally:
            window.make_editor_gui = original_make_editor_gui

        if getattr(window, "editor_ui", None) is None:
            window.editor_ui = Entity(name="editor_ui_stub", enabled=False, eternal=True)

    def draw(self) -> None:
        pass
