from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypedDict
import pygame, os

class ActionState(TypedDict):
    W: bool
    A: bool
    S: bool
    D: bool
    LU: bool
    LL: bool
    LD: bool
    LR: bool

class GameBase(ABC):
    """Base contract for game simulation and rendering. The game cannot use actions other than the 8 defined in ActionState, but it can interpret them in any way. LU, LL, LD, LR are arrow keys representing up, left, down, right respectively."""
    
    # Game's name
    name = "Game"
    # Directory to load game variants from. For example, if the game class is at games/game.py and variants (subclasses of the game class) are in games/variants/, then this should be "variants"
    variantsPath = 'variants'
    # Aspect close to 16:9
    width = 854
    height = 480

    moveInterval = 4
    
    BLANK_ACTION = {
        "W": False, "A": False, "S": False, "D": False,
        "LU": False, "LL": False, "LD": False, "LR": False
    }
    
    def __init__(self, headless=False) -> None:
        self.fps = 30
        self.headless = headless
        if headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        
    @abstractmethod
    def reset(self):
        """Reset internal game state. Must NOT change the game variant. Also reset auto play's internal state. The game should have a ending screen and only reset if certain action is performed on the ending screen, e.g. pressing A to reset, or auto resets after some time on the ending screen. This function should be called by game itself in update, NOT by outer code."""

    @abstractmethod
    def update(self, action: ActionState) -> bool:
        """Advance game by one frame with the given action. Besides responding to the action, this method should also update things like animations. Returns if the game ends after this update. It should return True exactly once per game, like at the frame end screen appear animation finishes. It will only be used to cut gameplay video based on session and not related to the reset function."""

    @abstractmethod
    def draw(self) -> None:
        """Draw the current game state to self.screen."""
        
    @abstractmethod
    def getPrompt(self) -> str:
        """Return a string prompt describing the rules of the game for training. It should explain the rules and controls. It generally uses if statements to return different rules for different variants."""
        
    @abstractmethod
    def getAutoAction(self) -> ActionState:
        """Implement the logical, somewhat randomized auto-play agent. It will be called every frame, but it does NOT need to perform action every time or act solely based on the current state. Instead, it must have internal state and act after proper time has passed to imitate a human player's reflections. Another point is that, if the game's action happens at key pressed down instead of holding key, auto action should only execute actions at multiples of 4 frames."""
