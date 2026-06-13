import os, random, sys

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.simpleMove import SimpleMoveBase


class ContinuousSimpleMove(SimpleMoveBase):
    name = "Continuous Simple Move"

    def __init__(self, headless: bool = False) -> None:
        """Initialize continuous speed before the shared movement setup."""
        self.move_speed = random.choice([170, 210, 250])
        super().__init__(headless=headless)

    def reset(self) -> None:
        """Reset the smooth object position and autoplay state without changing controls."""
        self.frame_index = 0
        self.x = random.randint(self.object_radius, self.width - self.object_radius)
        self.y = random.randint(self.object_radius, self.height - self.object_radius)
        self.auto_key = None
        self.auto_ticks_left = random.randint(2, 7)

    def update(self, action: ActionState) -> bool:
        """Move the object continuously while assigned movement keys are held."""
        self.frame_index += 1
        step = self.move_speed / self.fps
        if action[self.direction_keys["up"]]:
            self.y -= step
        if action[self.direction_keys["down"]]:
            self.y += step
        if action[self.direction_keys["left"]]:
            self.x -= step
        if action[self.direction_keys["right"]]:
            self.x += step
        self._stop_at_edges()
        return False

    def _stop_at_edges(self) -> None:
        """Keep the whole object inside the screen."""
        if self.x < self.object_radius:
            self.x = self.object_radius
        if self.x > self.width - self.object_radius:
            self.x = self.width - self.object_radius
        if self.y < self.object_radius:
            self.y = self.object_radius
        if self.y > self.height - self.object_radius:
            self.y = self.height - self.object_radius

    def draw(self) -> None:
        """Draw the background grid and continuously positioned object."""
        self.screen.fill(self.theme["bg"])
        tile_size, offset_x, offset_y = self._grid_info()
        self._draw_grid(tile_size, offset_x, offset_y)
        self._draw_object(self.x, self.y, tile_size)

    def frameToState(self, frame_rgb: np.ndarray) -> dict[str, float | None]:
        """Recover the visible object position as normalized screen coordinates."""
        center = self._recover_object_center(frame_rgb)
        if center is None:
            return {"x": None, "y": None}
        center_x, center_y = center
        height, width = frame_rgb.shape[:2]
        return {"x": round(center_x / width, 3), "y": round(center_y / height, 3)}

    def expectedFrameToState(self) -> dict[str, float]:
        """Return the expected normalized object position for parser self-tests."""
        return {"x": round(float(self.x) / self.width, 3), "y": round(float(self.y) / self.height, 3)}

    def statesMatch(self, gt_state, pred_state, last_gt_state, last_pred_state) -> bool:
        """Allow small position drift for continuous movement."""
        if not isinstance(gt_state, dict) or not isinstance(pred_state, dict):
            return False
        if gt_state.get("x") is None or pred_state.get("x") is None or gt_state.get("y") is None or pred_state.get("y") is None:
            return False
        return abs(float(gt_state["x"]) - float(pred_state["x"])) <= 0.035 and abs(float(gt_state["y"]) - float(pred_state["y"])) <= 0.035

    def _choose_continuous_auto_key(self) -> str | None:
        """Choose a held movement key, a decoy key, or a blank wait."""
        if random.random() < 0.18:
            return None
        if random.random() < 0.2:
            return random.choice(self._decoy_keys())
        direction = random.choice(["up", "down", "left", "right"])
        return self.direction_keys[direction]

    def getPrompt(self) -> str:
        """Return the prompt describing continuous movement controls."""
        return f"This is Continuous Simple Move. Pressing and holding {self.key_names[self.direction_keys['up']]} moves the object up, pressing and holding {self.key_names[self.direction_keys['down']]} moves it down, pressing and holding {self.key_names[self.direction_keys['left']]} moves it left, and pressing and holding {self.key_names[self.direction_keys['right']]} moves it right. The object moves at {self.move_speed} pixels per second. It stops at the screen edges, and no part of it leaves the screen. Pressing any other action key does nothing."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Switch held keys only on moveInterval frames and hold them between switches."""
        action = self.BLANK_ACTION.copy()
        if frame_index % self.moveInterval == 0:
            if self.auto_ticks_left <= 0:
                self.auto_key = self._choose_continuous_auto_key()
                self.auto_ticks_left = random.randint(3, 12)
            else:
                self.auto_ticks_left -= 1
        if self.auto_key is not None:
            action[self.auto_key] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(ContinuousSimpleMove)
