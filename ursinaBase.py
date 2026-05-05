from __future__ import annotations

from ursina import Entity, Ursina, application, scene, window
from panda3d.core import WindowProperties

from engineBase import ActionState, GameBase as _EngineGameBase


class UrsinaGameBase(_EngineGameBase):
    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

        original_make_editor_gui = window.make_editor_gui
        window.make_editor_gui = lambda *args, **kwargs: None
        try:
            existing_app = getattr(application, "base", None)
            if existing_app is not None and getattr(existing_app, "win", None) is not None:
                self.app = existing_app
            else:
                # IMPORTANT: always use the normal windowed path.
                # Ursina is a singleton, so repeated dataset clips reuse this
                # app instead of constructing a second Panda3D ShowBase.
                self.app = Ursina(
                    development_mode=False,
                    editor_ui_enabled=False,
                    fullscreen=False,
                    borderless=False,
                    size=(self.width, self.height),
                )
            if getattr(self.app, "win", None) is None:
                raise RuntimeError("Ursina app has no window; avoid destroying the shared Ursina app between clips")

            window.title = self.name
            window.borderless = False

            props = WindowProperties()
            props.setSize(self.width, self.height)
            self.app.win.requestProperties(props)

            if headless:
                props.setUndecorated(True)
                props.setOrigin(-20000, -20000)   # move off-screen
                props.setSize(self.width, self.height)
                props.setCursorHidden(True)
                self.app.win.requestProperties(props)

        finally:
            window.make_editor_gui = original_make_editor_gui

        if getattr(window, "editor_ui", None) is None:
            window.editor_ui = Entity(name="editor_ui_stub", enabled=False, eternal=True)

    def close(self) -> None:
        scene.clear()
        if getattr(self, "app", None) is not None:
            self.app.step()

    def draw(self) -> None:
        pass
