from __future__ import annotations

from typing import Callable, Optional, Type

import numpy as np
import pygame

from engineBase import ActionState, GameBase, BaseRunner, FrameCallback, choose_random_variant


# ---------------------------------------------------------------------------
# Pygame concrete runner implementations
# ---------------------------------------------------------------------------

class HumanDebugRunner(BaseRunner):
    """Runner for local debug play, controlled by keyboard input."""

    def _next_action(self) -> ActionState:
        keys = pygame.key.get_pressed()
        return {
            "W":  bool(keys[pygame.K_w]),
            "A":  bool(keys[pygame.K_a]),
            "S":  bool(keys[pygame.K_s]),
            "D":  bool(keys[pygame.K_d]),
            "LU": bool(keys[pygame.K_UP]),
            "LL": bool(keys[pygame.K_LEFT]),
            "LD": bool(keys[pygame.K_DOWN]),
            "LR": bool(keys[pygame.K_RIGHT]),
        }

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    def grab_frame_rgb(self) -> np.ndarray:
        rgb = pygame.surfarray.array3d(self.game.screen)
        return np.transpose(rgb, (1, 0, 2)).astype(np.uint8)

    def _flip(self) -> None:
        pygame.display.flip()

    def _tick(self) -> None:
        self.game.clock.tick(self.game.fps)

    def _quit(self) -> None:
        pygame.quit()


class AutoPlayRunner(BaseRunner):
    """Runner for automated play; intended for data/video pipelines."""

    def _next_action(self) -> ActionState:
        return self.game.getAutoAction(self.frame_index)

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    def grab_frame_rgb(self) -> np.ndarray:
        rgb = pygame.surfarray.array3d(self.game.screen)
        return np.transpose(rgb, (1, 0, 2)).astype(np.uint8)

    def _flip(self) -> None:
        pygame.display.flip()

    def _tick(self) -> None:
        if self.game.headless:
            return
        self.game.clock.tick(self.game.fps)

    def _quit(self) -> None:
        pygame.quit()


# ---------------------------------------------------------------------------
# Convenience functions (same API as the old gameRunner.py)
# ---------------------------------------------------------------------------

def run_human_debug(
    game_cls: Type[GameBase],
    headless: bool = False,
    max_frames: int | None = None,
    on_frame: FrameCallback | None = None,
) -> int:
    """Construct and run one game instance in human-debug mode."""
    game = game_cls(headless=headless)
    runner = HumanDebugRunner(game=game, max_frames=max_frames, on_frame=on_frame)
    return runner.run()


def run_autoplay(
    game_cls: Type[GameBase],
    headless: bool = False,
    max_frames: int | None = None,
    on_frame: FrameCallback | None = None,
) -> int:
    """Construct and run one game instance in autoplay mode."""
    game = game_cls(headless=headless)
    runner = AutoPlayRunner(game=game, max_frames=max_frames, on_frame=on_frame)
    return runner.run()


# Re-export choose_random_variant for callers that import it from here
__all__ = [
    "HumanDebugRunner",
    "AutoPlayRunner",
    "run_human_debug",
    "run_autoplay",
    "choose_random_variant",
    "FrameCallback",
]
