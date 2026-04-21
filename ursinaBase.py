from __future__ import annotations

from ursina import Entity, Ursina, window

from engineBase import ActionState, GameBase as _EngineGameBase


class UrsinaGameBase(_EngineGameBase):
    """
    Ursina-backed concrete game base.

    __init__ creates the Ursina app (window or offscreen).
    draw() is a no-op — Ursina renders automatically when the runner
    calls base.taskMgr.step() each frame.
    self.screen is not used; entities are created directly in Ursina's
    scene graph inside reset().
    """

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        original_make_editor_gui = window.make_editor_gui
        window.make_editor_gui = lambda *args, **kwargs: None
        try:
            if headless:
                self.app = Ursina(
                    window_type="offscreen",
                    development_mode=False,
                    editor_ui_enabled=False,
                    fullscreen=False,
                    borderless=False,
                    size=(self.width, self.height),
                )
            else:
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
        finally:
            window.make_editor_gui = original_make_editor_gui

        if getattr(window, "editor_ui", None) is None:
            window.editor_ui = Entity(name="editor_ui_stub", enabled=False, eternal=True)

    def draw(self) -> None:
        """No-op — rendering is driven by base.taskMgr.step() in the runner."""
        pass
