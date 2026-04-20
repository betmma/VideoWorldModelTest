from __future__ import annotations

import importlib.util
import inspect
import os
import random
from abc import ABC, abstractmethod
from typing import Callable, Optional, TypedDict

import numpy as np


# ---------------------------------------------------------------------------
# Action contract (engine-agnostic)
# ---------------------------------------------------------------------------

class ActionState(TypedDict):
    W: bool
    A: bool
    S: bool
    D: bool
    LU: bool
    LL: bool
    LD: bool
    LR: bool


# ---------------------------------------------------------------------------
# Frame callback type used by both runner and dataset generator
# Receives an HxWx3 uint8 RGB numpy array instead of a raw engine surface.
# ---------------------------------------------------------------------------

FrameCallback = Callable[["np.ndarray", ActionState, int, bool], Optional[bool]]


# ---------------------------------------------------------------------------
# GameBase — abstract game contract, engine-agnostic
# ---------------------------------------------------------------------------

'''
When writing a specific game, add the following at the end of the file to
allow testing directly:

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(GameClassName)
'''

class GameBase(ABC):
    """
    Engine-agnostic base contract for game simulation and rendering.
    Subclasses must NOT import pygame or ursina directly; that belongs in
    the concrete engine layer (pygameBase / ursinaBase).

    The game cannot use actions other than the 8 defined in ActionState,
    but it can interpret them in any way.
    LU, LL, LD, LR are arrow keys representing up, left, down, right.
    """

    # Game's name
    name = "Game"
    # Directory to load game variants from (relative to the game file)
    variantsPath = "variants"
    # Aspect close to 16:9
    width = 854
    height = 480

    moveInterval = 4

    BLANK_ACTION: ActionState = {
        "W": False, "A": False, "S": False, "D": False,
        "LU": False, "LL": False, "LD": False, "LR": False,
    }

    def __init__(self, headless: bool = False) -> None:
        self.fps = 30
        self.headless = headless
        # self.screen is NOT set here — concrete engine subclasses provide it.

    @abstractmethod
    def reset(self) -> None:
        """
        Reset internal game state. Must NOT change the game variant.
        Also reset auto-play's internal state.
        The game should only call reset() from within its own update(), NOT
        from outer code.
        """

    @abstractmethod
    def update(self, action: ActionState) -> bool:
        """
        Advance the game by one frame with the given action.
        Returns True exactly once per game session (e.g. when the end-screen
        animation finishes). Used by the dataset pipeline to cut clips.
        """

    @abstractmethod
    def draw(self) -> None:
        """Draw the current game state to the engine surface (self.screen)."""

    @abstractmethod
    def getPrompt(self) -> str:
        """
        Return a string prompt describing the rules of the game for training.
        Every variant should return its own prompt.
        """

    @abstractmethod
    def getAutoAction(self) -> ActionState:
        """
        Implement a logical, somewhat randomised auto-play agent.
        Called every frame. Must have internal state and should not act at a
        perfectly steady interval to imitate human reaction times.
        """


# ---------------------------------------------------------------------------
# BaseRunner — abstract runner, engine-agnostic
# ---------------------------------------------------------------------------

class BaseRunner(ABC):
    """
    Abstract game loop. Subclasses supply the engine-specific I/O:
      _next_action()   — read keyboard / call getAutoAction
      _handle_events() — process OS window events, set self.running = False to quit
      grab_frame_rgb() — return current rendered frame as HxWx3 uint8 numpy (RGB)
      _flip()          — present frame to display
      _tick()          — throttle to target FPS
      _quit()          — engine teardown
    """

    def __init__(
        self,
        game: GameBase,
        max_frames: int | None = None,
        on_frame: FrameCallback | None = None,
    ) -> None:
        self.game = game
        self.max_frames = max_frames
        self.on_frame = on_frame
        self.frame_index = 0
        self.rendered_frame_index = 0
        self.ended_once = False
        self.running = False

    @abstractmethod
    def _next_action(self) -> ActionState:
        """Return the action for the current frame."""

    @abstractmethod
    def _handle_events(self) -> None:
        """
        Process windowing/OS events. Set self.running = False to signal quit.
        """

    @abstractmethod
    def grab_frame_rgb(self) -> np.ndarray:
        """
        Capture the current rendered frame and return it as an HxWx3 uint8
        numpy array in RGB channel order. This is the critical seam that
        decouples the dataset pipeline from any specific engine surface type.
        """

    @abstractmethod
    def _flip(self) -> None:
        """Present the current frame to the display (e.g. pygame.display.flip)."""

    @abstractmethod
    def _tick(self) -> None:
        """Throttle loop to the game's target FPS."""

    @abstractmethod
    def _quit(self) -> None:
        """Tear down the engine (e.g. pygame.quit)."""

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def _blank_action(self) -> ActionState:
        return {
            "W": False, "A": False, "S": False, "D": False,
            "LU": False, "LL": False, "LD": False, "LR": False,
        }

    def _emit_frame(self, action: ActionState, ended_this_frame: bool) -> None:
        """Grab pixels via grab_frame_rgb() and invoke on_frame callback."""
        if self.on_frame is None:
            return
        frame_rgb = self.grab_frame_rgb()
        should_continue = self.on_frame(
            frame_rgb, action, self.rendered_frame_index, ended_this_frame
        )
        if should_continue is False:
            self.running = False

    # ------------------------------------------------------------------
    # Concrete frame loop
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        Run the game loop until a quit signal or max_frames is reached.
        Returns the total number of processed frames.
        """
        self.running = True
        self.frame_index = 0
        self.rendered_frame_index = 0
        self.ended_once = False
        self.game.reset()
        self.game.draw()
        if not self.game.headless:
            self._flip()

        while self.running:
            self._handle_events()
            if not self.running:
                break

            action = self._next_action()
            ended_this_frame = self.game.update(action)
            if ended_this_frame:
                self.ended_once = True

            self.game.draw()
            if not self.game.headless:
                self._flip()
            self.rendered_frame_index += 1
            self._emit_frame(action, ended_this_frame)
            self._tick()

            self.frame_index += 1
            if self.max_frames is not None and self.frame_index >= self.max_frames:
                self.running = False

        self._quit()
        return self.frame_index


# ---------------------------------------------------------------------------
# Utility — engine-agnostic variant loader
# ---------------------------------------------------------------------------

def choose_random_variant(game_cls: type[GameBase]) -> type[GameBase]:
    """
    Pick one random subclass from game_cls.variantsPath.
    If no valid variant is found, returns game_cls itself.
    """
    base_file = inspect.getfile(game_cls)
    base_dir = os.path.dirname(os.path.abspath(base_file))
    variants_dir = os.path.join(base_dir, game_cls.variantsPath)

    if not os.path.isdir(variants_dir):
        return game_cls

    variant_classes: list[type[GameBase]] = [game_cls]
    for filename in os.listdir(variants_dir):
        if not filename.endswith(".py") or filename.startswith("__"):
            continue

        module_path = os.path.join(variants_dir, filename)
        module_name = f"_variant_{game_cls.__name__}_{filename[:-3]}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is game_cls:
                continue
            if issubclass(obj, game_cls):
                variant_classes.append(obj)

    return random.choice(variant_classes)
