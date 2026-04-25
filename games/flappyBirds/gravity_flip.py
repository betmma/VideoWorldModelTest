from __future__ import annotations

import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.flappyBird import FlappyBirdBase


class GravityFlipFlappyBird(FlappyBirdBase):
    name = "Flappy Bird VVVVVV"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.gravity_strength = 0.62
        self.max_vertical_speed = 7.8
        self.pipe_gap_size = 170
        self.pipe_gap_change = 92
        self.reset()

    def reset(self) -> None:
        super().reset()
        self.gravity_strength = getattr(self, "gravity_strength", 0.62)
        self.max_vertical_speed = getattr(self, "max_vertical_speed", 7.8)
        self.gravity_direction = 1
        self.gravity = self.gravity_strength * self.gravity_direction

    def _flap(self) -> None:
        if self.game_over:
            return
        self.started = True
        self.gravity_direction *= -1
        self.gravity = self.gravity_strength * self.gravity_direction

    def _update_bird_physics(self) -> None:
        self.bird.vy += self.gravity
        if self.bird.vy > self.max_vertical_speed:
            self.bird.vy = self.max_vertical_speed
        elif self.bird.vy < -self.max_vertical_speed:
            self.bird.vy = -self.max_vertical_speed
        self.bird.y += self.bird.vy

    def _bird_render_transform(self) -> tuple[float, bool]:
        return 0.0, self.gravity_direction < 0

    def _start_tip_text(self) -> str:
        return "Press W / Up Arrow to flip gravity"

    def _draw_hud_extras(self) -> None:
        label = "Gravity: Up" if self.gravity_direction < 0 else "Gravity: Down"
        gravity_text = self.hud_font.render(label, True, (50, 60, 74))
        self.screen.blit(gravity_text, (self.width - gravity_text.get_width() - 16, 14))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Variant rule: the bird uses VVVVVV-style controls. "
            "Press W or Up Arrow to flip gravity instead of flapping, and the bird sprite flips upside down whenever gravity points upward. "
            "Pipes still scroll in from the right, you score by passing through their gaps, and hitting a pipe, the ceiling, or the ground ends the run. After crashing, press A or Left Arrow to restart."
        )

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if self.frame_index % self.moveInterval != 0:
            return action

        if self.game_over:
            if random.random() < 0.18:
                action["A"] = True
            return action

        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action

        target_pipe = None
        for pipe in self.pipes:
            if pipe.x + pipe.width >= self.bird.x - self.bird.radius:
                target_pipe = pipe
                break

        target_y = self.height * 0.46 if target_pipe is None else target_pipe.gap_y
        distance = 999.0 if target_pipe is None else target_pipe.x + target_pipe.width - self.bird.x
        lookahead = max(5.0, min(10.0, distance / max(self.pipe_speed, 0.1) / 18.0))
        predicted_y = self.bird.y + self.bird.vy * lookahead + self.gravity * lookahead * lookahead * 0.5

        should_flip = False
        if not self.started:
            should_flip = random.random() < 0.9
        elif self.gravity_direction > 0:
            should_flip = predicted_y > target_y + 16.0 or self.bird.y > self._ground_top() - 76
        else:
            should_flip = predicted_y < target_y - 16.0 or self.bird.y < 76

        if should_flip:
            action["W"] = True
            self.auto_wait_frames = random.randint(1, 2)

        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(GravityFlipFlappyBird)
