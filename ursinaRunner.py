from __future__ import annotations

# ---------------------------------------------------------------------------
# ursinaRunner.py — Ursina concrete runner (STUB)
# ---------------------------------------------------------------------------
# Fill this in when building the Ursina marble maze.
#
# When implementing:
# - _next_action:   poll ursina.held_keys for keyboard state
# - _handle_events: Panda3D/Ursina event dispatch
# - grab_frame_rgb: read pixels from offscreen GraphicsBuffer into numpy array
# - _flip:          ursina app.step() or equivalent
# - _tick:          Panda3D clock / taskMgr step
# - _quit:          application.quit()
# ---------------------------------------------------------------------------

import numpy as np

from engineBase import ActionState, BaseRunner


class UrsinaRunner(BaseRunner):
    """
    Ursina-backed autoplay/human runner (not yet implemented).
    """

    def _next_action(self) -> ActionState:
        raise NotImplementedError("UrsinaRunner is a stub — implement before use.")

    def _handle_events(self) -> None:
        raise NotImplementedError

    def grab_frame_rgb(self) -> np.ndarray:
        raise NotImplementedError

    def _flip(self) -> None:
        raise NotImplementedError

    def _tick(self) -> None:
        raise NotImplementedError

    def _quit(self) -> None:
        raise NotImplementedError
