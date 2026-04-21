from __future__ import annotations

import os
from typing import Any

import pygame

from engineBase import ActionState, GameBase as _EngineGameBase


# ---------------------------------------------------------------------------
# PygameGameBase — concrete Pygame engine layer
# ---------------------------------------------------------------------------

class GameBase(_EngineGameBase):
    """
    Pygame-backed concrete game base.
    Inherits the engine-agnostic contract from engineBase.GameBase and adds
    pygame initialisation: self.screen (pygame.Surface) and self.clock.
    """

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        if headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        self.screen: pygame.Surface = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()


# ---------------------------------------------------------------------------
# Re-export ActionState so callers can do:
#   from pygameBase import ActionState, GameBase
# ---------------------------------------------------------------------------

__all__ = ["ActionState", "GameBase"]
