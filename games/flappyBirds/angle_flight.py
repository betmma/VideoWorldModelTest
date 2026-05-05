from __future__ import annotations

import math
import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.flappyBird import FlappyBirdBase


class AngleFlightFlappyBird(FlappyBirdBase):
    name = "Flappy Bird Zero-G Steering"
    moveInterval = 1

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.turn_speed = 4.0
        self.flight_speed = 5.1
        self.pipe_speed = 2.8
        self.pipe_gap_size = 176
        self.pipe_gap_change = 76
        self.pipe_spacing = 266
        self.reset()

    def reset(self) -> None:
        super().reset()
        self.turn_speed = getattr(self, "turn_speed", 4.0)
        self.flight_speed = getattr(self, "flight_speed", 5.1)
        self.flight_angle = 0.0
        self.bird.x = self.bird_x
        self.bird.vy = 0.0

    def _normalize_angle(self, angle: float) -> float:
        return (angle + 180.0) % 360.0 - 180.0

    def _bird_render_transform(self) -> tuple[float, bool]:
        return -self.flight_angle, False

    def _start_tip_text(self) -> str:
        return "Press A/D or Left/Right Arrow to steer"

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. The bird continuously flies forward at a fixed speed with no gravity while the scene side-scrolls. "
            "Hold A or Left Arrow to rotate counterclockwise so the bird climbs, and hold D or Right Arrow to rotate clockwise so the bird dives. Flying through a gap scores a point, and hitting a pipe, the ceiling, or the ground ends the run. After crashing, press A or Left Arrow to restart."
        )

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1
        pressed_action = self._pressed_actions(action)

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.game_over:
            if not self.end_reported:
                self.end_reported = True
                self.end_event_pending = True

            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        turn_dir = 0
        if action["A"] or action["LL"]:
            turn_dir -= 1
        if action["D"] or action["LR"]:
            turn_dir += 1

        if turn_dir != 0:
            self.started = True

        if not self.started:
            return False

        self.flight_angle = max(-82.0, min(82.0, self.flight_angle + turn_dir * self.turn_speed))
        heading = math.radians(self.flight_angle)
        self.ground_scroll = (self.ground_scroll + self.pipe_speed) % 48.0

        self.bird.y += math.sin(heading) * self.flight_speed
        self.bird.x = self.bird_x
        self.bird.vy = math.sin(heading) * self.flight_speed

        self._advance_pipes()
        self._recycle_pipes()
        self._update_score_from_pipes()

        if self._check_world_bounds():
            return False

        self._check_pipe_collision()
        return False

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()

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

        target_y = self.height * 0.46
        if target_pipe is not None:
            target_y = target_pipe.gap_y

        if self.bird.y < 72:
            target_y = self.height * 0.62
        elif self.bird.y > self._ground_top() - 72:
            target_y = self.height * 0.34

        predicted_y = self.bird.y + self.bird.vy * 6.0
        error = target_y - predicted_y

        if not self.started and abs(error) < 10.0:
            action[random.choice(["A", "D"])] = True
            return action

        if error < -12.0:
            action["A"] = True
        elif error > 12.0:
            action["D"] = True
        elif self.flight_angle < -5.0:
            action["D"] = True
        elif self.flight_angle > 5.0:
            action["A"] = True

        if random.random() < 0.08:
            self.auto_wait_frames = 1

        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(AngleFlightFlappyBird)
