from __future__ import annotations

from pathlib import Path

from ursina import Entity, Ursina, application, scene, window
from panda3d.core import WindowProperties

from engineBase import ActionState, GameBase as _EngineGameBase


_URSINA_ASSET_ROOT = Path(__file__).resolve().parent / "games"


def _set_ursina_asset_root() -> None:
    """Keep Ursina's recursive asset lookup out of generated dataset folders."""
    application.asset_folder = _URSINA_ASSET_ROOT
    application.scenes_folder = _URSINA_ASSET_ROOT / "scenes"
    application.scripts_folder = _URSINA_ASSET_ROOT / "scripts"
    application.fonts_folder = _URSINA_ASSET_ROOT / "fonts"
    application.textures_compressed_folder = _URSINA_ASSET_ROOT / "textures_compressed"
    application.models_compressed_folder = _URSINA_ASSET_ROOT / "models_compressed"


class UrsinaGameBase(_EngineGameBase):
    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

        _set_ursina_asset_root()

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
