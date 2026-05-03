from __future__ import annotations

import time
from typing import Type

import numpy as np
from ursina import held_keys

from engineBase import ActionState, BaseRunner, FrameCallback, GameBase, choose_random_variant


class _UrsinaBaseRunner(BaseRunner):

    def _handle_events(self) -> None:
        # Ursina processes window events during app.step().
        pass

    def grab_frame_rgb(self) -> np.ndarray:
        texture = self.game.app.win.getScreenshot()
        if texture is None:
            # Give Panda a few more render passes.
            # Important for scenes with shadow maps / extra render targets.
            for _ in range(4):
                self.game.app.graphicsEngine.renderFrame()
                texture = self.game.app.win.getScreenshot()
                if texture is not None:
                    break

        if texture is None:
            gsg = self.game.app.win.getGsg() if hasattr(self.game.app.win, "getGsg") else None
            pipe = self.game.app.win.getPipe() if hasattr(self.game.app.win, "getPipe") else None
            raise RuntimeError(
                "Ursina screenshot capture failed. "
                f"pipe={pipe}, gsg={gsg}, active={self.game.app.win.isActive() if hasattr(self.game.app.win, 'isActive') else 'unknown'}"
            )

        data = texture.getRamImageAs("RGB")
        if data is None:
            raise RuntimeError("Ursina screenshot RAM image is unavailable")

        width = texture.getXSize()
        height = texture.getYSize()
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        return np.flipud(frame).copy()

    def _flip(self) -> None:
        pass

    def _tick(self) -> None:
        if self.game.headless or self.game.fps <= 0:
            return

        now = time.perf_counter()
        if not hasattr(self, "_next_frame_deadline"):
            self._next_frame_deadline = now + (1.0 / float(self.game.fps))
            return

        remaining = self._next_frame_deadline - now
        if remaining > 0:
            time.sleep(remaining)
            now = time.perf_counter()

        frame_duration = 1.0 / float(self.game.fps)
        self._next_frame_deadline = max(self._next_frame_deadline + frame_duration, now + frame_duration)

    def _quit(self) -> None:
        self.game.app.destroy()

    def run(self) -> int:
        self.running = True
        self.frame_index = 0
        self.rendered_frame_index = 0
        self.ended_once = False
        self._next_frame_deadline = time.perf_counter()

        self.game.reset()
        self.game.draw()
        self.game.app.step()
        self._emit_frame(self._blank_action(), False)
        self.rendered_frame_index += 1

        while self.running:
            self._handle_events()
            if not self.running:
                break

            action = self._next_action()
            ended_this_frame = self.game.update(action)
            if ended_this_frame:
                self.ended_once = True

            self.game.draw()
            self.game.app.step()
            self.rendered_frame_index += 1
            self._emit_frame(action, ended_this_frame)
            self._tick()

            self.frame_index += 1
            if self.max_frames is not None and self.frame_index >= self.max_frames:
                self.running = False

        self._quit()
        return self.frame_index


class UrsinaHumanRunner(_UrsinaBaseRunner):
    def _next_action(self) -> ActionState:
        return {
            "W": bool(held_keys["w"]),
            "A": bool(held_keys["a"]),
            "S": bool(held_keys["s"]),
            "D": bool(held_keys["d"]),
            "LU": bool(held_keys["up arrow"]),
            "LL": bool(held_keys["left arrow"]),
            "LD": bool(held_keys["down arrow"]),
            "LR": bool(held_keys["right arrow"]),
        }


class UrsinaAutoPlayRunner(_UrsinaBaseRunner):
    def _next_action(self) -> ActionState:
        return self.game.getAutoAction()


def run_human_debug(
    game_cls: Type[GameBase],
    headless: bool = False,
    max_frames: int | None = None,
    on_frame: FrameCallback | None = None,
) -> int:
    game = game_cls(headless=headless)
    return UrsinaHumanRunner(game=game, max_frames=max_frames, on_frame=on_frame).run()


def run_autoplay(
    game_cls: Type[GameBase],
    headless: bool = False,
    max_frames: int | None = None,
    on_frame: FrameCallback | None = None,
) -> int:
    game = game_cls(headless=headless)
    return UrsinaAutoPlayRunner(game=game, max_frames=max_frames, on_frame=on_frame).run()


__all__ = [
    "UrsinaHumanRunner",
    "UrsinaAutoPlayRunner",
    "run_human_debug",
    "run_autoplay",
    "choose_random_variant",
]
