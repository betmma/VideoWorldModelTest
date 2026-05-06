from __future__ import annotations

import os
import random
import sys

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.flappyBird import FlappyBirdBase


class PipeDirectorFlappyBird(FlappyBirdBase):
    name = "Flappy Bird Pipe Director"
    moveInterval = 1

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.pipe_shift_speed = 2.8
        self.target_slide_speed = 1.55
        self.target_hold_min = 48
        self.target_hold_max = 108
        self.pipe_margin_top = -56
        self.pipe_margin_bottom = -56
        self.pipe_gap_size = 156
        self.pipe_gap_change = 72
        self.reset()

    def reset(self) -> None:
        super().reset()
        self.pipe_shift_speed = getattr(self, "pipe_shift_speed", 2.8)
        self.target_slide_speed = getattr(self, "target_slide_speed", 1.55)
        self.target_hold_min = getattr(self, "target_hold_min", 48)
        self.target_hold_max = getattr(self, "target_hold_max", 108)
        self.auto_flap_cooldown = 0
        self.target_height = self.start_bird_y
        self.target_goal = self.start_bird_y
        self.target_timer = random.randint(self.target_hold_min, self.target_hold_max)

    def _start_tip_text(self) -> str:
        return "Press W/S or Up/Down to move every pipe"

    def _target_limits(self) -> tuple[float, float]:
        return self.pipe_margin_top + 130.0, self._ground_top() - 48.0

    def _update_target_height(self) -> None:
        self.target_timer -= 1
        if self.target_timer <= 0:
            min_target, max_target = self._target_limits()
            self.target_goal = random.uniform(min_target, max_target)
            self.target_timer = random.randint(self.target_hold_min, self.target_hold_max)

        delta = self.target_goal - self.target_height
        step = max(-self.target_slide_speed, min(self.target_slide_speed, delta))
        self.target_height += step

    def _auto_flap_bird(self) -> None:
        if self.auto_flap_cooldown > 0:
            self.auto_flap_cooldown -= 1

        lookahead = 6.0
        predicted_y = self.bird.y + self.bird.vy * lookahead + self.gravity * lookahead * lookahead * 0.5
        should_flap = predicted_y > self.target_height + 51.0 or self.bird.y > self._ground_top() - 84
        if self.auto_flap_cooldown == 0 and should_flap:
            self.bird.vy = self.flap_velocity
            self.auto_flap_cooldown = random.randint(2, 4)

    def _draw_hud_extras(self) -> None:
        alphaMultiplier = max(0.0, 1.0 - self.frame_index / 480.0)
        marker_y = int(self.target_height)
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for x in range(0, self.width, 28):
            pygame.draw.line(
                overlay,
                (255, 255, 255, int(68 * alphaMultiplier)),
                (x, marker_y),
                (min(x + 14, self.width), marker_y),
                2,
            )
        pygame.draw.circle(overlay, (255, 118, 96, int(128 * alphaMultiplier)), (74, marker_y), 8)
        self.screen.blit(overlay, (0, 0))

        label = self.hud_font.render("Bird target", True, (50, 60, 74))
        self.screen.blit(label, (self.width - label.get_width() - 16, 14))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. The bird flaps automatically and tries to follow a changing target height. "
            "You do not control the bird directly. Hold W or Up Arrow to move every pipe upward, and hold S or Down Arrow to move every pipe downward so the gaps line up with the bird's path. The horizontal guide marks the bird's current target height. Passing through a gap scores a point, and hitting a pipe, the ceiling, or the ground ends the run. After crashing, press A or Left Arrow to restart."
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

        pipe_shift = 0.0
        if action["W"] or action["LU"]:
            pipe_shift -= self.pipe_shift_speed
        if action["S"] or action["LD"]:
            pipe_shift += self.pipe_shift_speed

        if pipe_shift != 0.0:
            self.started = True

        if not self.started:
            return False

        self.ground_scroll = (self.ground_scroll + self.pipe_speed) % 48.0
        self._update_target_height()
        self._auto_flap_bird()
        self._move_pipes_vertical(pipe_shift)
        self._update_bird_physics()
        self._advance_pipes()
        self._recycle_pipes()
        self._update_score_from_pipes()

        if self._check_world_bounds():
            return False

        self._check_pipe_collision()
        return False

    def getAutoAction(self, frame_index: int) -> ActionState:
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

        predicted_y = self.target_height
        if self.started:
            predicted_y = self.bird.y + self.bird.vy * 5.5 + self.gravity * 5.5 * 5.5 * 0.5

        focus_gap_y = predicted_y if target_pipe is None else target_pipe.gap_y
        error = focus_gap_y - predicted_y

        if error > 10.0:
            action["W"] = True
        elif error < -10.0:
            action["S"] = True
        elif not self.started:
            action[random.choice(["W", "S"])] = True

        if random.random() < 0.12:
            self.auto_wait_frames = 1

        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(PipeDirectorFlappyBird)
