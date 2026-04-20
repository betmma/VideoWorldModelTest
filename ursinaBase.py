from __future__ import annotations

# ---------------------------------------------------------------------------
# ursinaBase.py — Ursina concrete game base (STUB)
# ---------------------------------------------------------------------------
# Fill this in when building the Ursina marble maze.
# Import ursina here; do NOT import pygame.
#
# from ursina import Ursina, Entity, camera, ...
# ---------------------------------------------------------------------------

from engineBase import ActionState, GameBase as _EngineGameBase


class UrsinaGameBase(_EngineGameBase):
    """
    Ursina-backed concrete game base (not yet implemented).

    When implementing:
    - __init__ should create the Ursina app and an offscreen buffer for
      headless rendering (Panda3D's GraphicsOutput / OffscreenBuffer).
    - self.screen equivalent will be a Panda3D texture / framebuffer handle.
    - draw() is called each frame before the engine renders; in Ursina this
      maps to update() or a custom Task callback.
    """

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        raise NotImplementedError("UrsinaGameBase is a stub — implement before use.")

    def reset(self) -> None:
        raise NotImplementedError

    def update(self, action: ActionState) -> bool:
        raise NotImplementedError

    def draw(self) -> None:
        raise NotImplementedError

    def getPrompt(self) -> str:
        raise NotImplementedError

    def getAutoAction(self) -> ActionState:
        raise NotImplementedError
