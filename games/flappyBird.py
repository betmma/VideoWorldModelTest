from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


@dataclass
class Bird:
    x: float
    y: float
    vy: float
    radius: int


@dataclass
class PipePair:
    x: float
    gap_y: float
    gap_size: int
    width: int
    passed: bool = False


class FlappyBirdBase(GameBase):
    name = "Flappy Bird"
    variantsPath = "flappyBirds"
    moveInterval = 2

    def __init__(self, headless: bool = False) -> None:
        self.ground_height = 72
        self.bird_x = self.width * 0.28
        self.bird_radius = 18
        self.gravity = 0.42
        self.flap_velocity = -7.3
        self.max_fall_speed = 8.5
        self.pipe_speed = 3.4
        self.pipe_width = 92
        self.pipe_spacing = 250
        self.pipe_gap_size = 162
        self.pipe_gap_change = 84
        self.pipe_spawn_x = self.width + 150
        self.pipe_margin_top = 56
        self.pipe_margin_bottom = 56
        self.end_screen_auto_reset = 120

        super().__init__(headless=headless)

        pygame.font.init()
        self.score_font = pygame.font.SysFont("consolas", 40, bold=True)
        self.hud_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.tip_font = pygame.font.SysFont("consolas", 22)
        self.title_font = pygame.font.SysFont("consolas", 44, bold=True)

        self.sky_color = (145, 205, 255)
        self.hill_color = (112, 186, 118)
        self.pipe_color = (84, 188, 86)
        self.pipe_shadow = (50, 120, 52)
        self.ground_color = (224, 196, 112)
        self.ground_stripe = (198, 170, 90)
        self.bird_color = (250, 215, 72)
        self.wing_color = (235, 180, 44)
        self.eye_color = (40, 40, 40)
        self.beak_color = (238, 135, 42)

        self.best_score = 0
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

    def reset(self) -> None:
        self.score = 0
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.game_over = False
        self.started = False

        self.auto_wait_frames = 0

        start_y = self.height * 0.46
        self.bird = Bird(self.bird_x, start_y, 0.0, self.bird_radius)
        self.start_bird_y = start_y
        self.ground_scroll = 0.0
        self.last_gap_y: float | None = None
        self.pipes: list[PipePair] = []

        for i in range(3):
            self._spawn_pipe(self.pipe_spawn_x + i * self.pipe_spacing)

    def _ground_top(self) -> int:
        return self.height - self.ground_height

    def _current_bird_y(self) -> float:
        if self.started or self.game_over:
            return self.bird.y
        bob = math.sin(self.frame_index / 7.5) * 6.0
        return self.start_bird_y + bob

    def _spawn_pipe(self, x: float | None = None) -> None:
        if x is None:
            x = self.pipe_spawn_x
        gap_y = self._next_gap_y()
        self.pipes.append(
            PipePair(
                x=x,
                gap_y=gap_y,
                gap_size=self.pipe_gap_size,
                width=self.pipe_width,
            )
        )

    def _pipe_gap_limits(self) -> tuple[float, float]:
        ground_top = self._ground_top()
        min_gap_y = self.pipe_margin_top + self.pipe_gap_size / 2
        max_gap_y = ground_top - self.pipe_margin_bottom - self.pipe_gap_size / 2
        return min_gap_y, max_gap_y

    def _next_gap_y(self) -> float:
        min_gap_y, max_gap_y = self._pipe_gap_limits()
        if self.last_gap_y is None:
            gap_y = random.uniform(min_gap_y + 12.0, max_gap_y - 12.0)
        else:
            gap_y = self.last_gap_y + random.uniform(-self.pipe_gap_change, self.pipe_gap_change)
            gap_y = max(min_gap_y, min(max_gap_y, gap_y))
        self.last_gap_y = gap_y
        return gap_y

    def _pipe_rects(self, pipe: PipePair) -> tuple[pygame.Rect, pygame.Rect]:
        gap_half = pipe.gap_size / 2
        gap_top = int(pipe.gap_y - gap_half)
        gap_bottom = int(pipe.gap_y + gap_half)
        ground_top = self._ground_top()

        top_rect = pygame.Rect(int(pipe.x), 0, pipe.width, max(0, gap_top))
        bottom_rect = pygame.Rect(int(pipe.x), gap_bottom, pipe.width, max(0, ground_top - gap_bottom))
        return top_rect, bottom_rect

    def _bird_rect(self) -> pygame.Rect:
        y = self._current_bird_y()
        r = self.bird.radius
        return pygame.Rect(int(self.bird.x - r), int(y - r), r * 2, r * 2)

    def _pressed_actions(self, action: ActionState) -> ActionState:
        pressed_action = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action[key]:
                pressed_action[key] = True
        self.prev_action = action.copy()
        return pressed_action

    def _flap(self) -> None:
        if self.game_over:
            return
        self.started = True
        self.bird.vy = self.flap_velocity

    def _crash(self) -> None:
        if self.game_over:
            return
        self.game_over = True
        self.best_score = max(self.best_score, self.score)

    def _update_bird_physics(self) -> None:
        self.bird.vy = min(self.max_fall_speed, self.bird.vy + self.gravity)
        self.bird.y += self.bird.vy

    def _advance_pipes(self) -> None:
        for pipe in self.pipes:
            pipe.x -= self.pipe_speed

    def _recycle_pipes(self) -> None:
        while self.pipes and self.pipes[0].x + self.pipe_width < -8:
            self.pipes.pop(0)

        if not self.pipes or self.pipes[-1].x <= self.width - self.pipe_spacing:
            self._spawn_pipe()

    def _update_score_from_pipes(self) -> None:
        for pipe in self.pipes:
            if not pipe.passed and pipe.x + pipe.width < self.bird.x:
                pipe.passed = True
                self.score += 1
                self.best_score = max(self.best_score, self.score)

    def _move_pipes_vertical(self, delta: float) -> float:
        if not self.pipes or abs(delta) <= 0.0:
            return 0.0

        min_gap_y, max_gap_y = self._pipe_gap_limits()
        min_allowed = min_gap_y - min(pipe.gap_y for pipe in self.pipes)
        max_allowed = max_gap_y - max(pipe.gap_y for pipe in self.pipes)
        applied_delta = max(min_allowed, min(max_allowed, delta))

        if abs(applied_delta) <= 0.0:
            return 0.0

        for pipe in self.pipes:
            pipe.gap_y += applied_delta

        if self.last_gap_y is not None:
            self.last_gap_y = max(min_gap_y, min(max_gap_y, self.last_gap_y + applied_delta))

        return applied_delta

    def _check_world_bounds(self) -> bool:
        bird_rect = self._bird_rect()
        if bird_rect.top <= 0:
            self.bird.y = float(self.bird.radius)
            self._crash()
            return True

        if bird_rect.bottom >= self._ground_top():
            self.bird.y = float(self._ground_top() - self.bird.radius)
            self._crash()
            return True

        return False

    def _check_pipe_collision(self) -> bool:
        bird_rect = self._bird_rect()
        for pipe in self.pipes:
            top_rect, bottom_rect = self._pipe_rects(pipe)
            if bird_rect.colliderect(top_rect) or bird_rect.colliderect(bottom_rect):
                self._crash()
                return True
        return False

    def _bird_render_transform(self) -> tuple[float, bool]:
        return 0.0, False

    def _start_tip_text(self) -> str:
        return "Press W / Up Arrow to flap"

    def _restart_tip_text(self) -> str:
        return "Press A / Left Arrow to restart"

    def _draw_hud_extras(self) -> None:
        return None

    def _build_bird_surface(self) -> pygame.Surface:
        wing_shift = math.sin(self.frame_index / 2.0) * 3.0 if self.started and not self.game_over else 0.0
        bird_surface = pygame.Surface((60, 50), pygame.SRCALPHA)
        body_rect = pygame.Rect(9, 9, 42, 32)
        wing_rect = pygame.Rect(5, int(17 + wing_shift), 24, 16)
        eye_rect = pygame.Rect(0, 0, 8, 8)
        eye_rect.center = (36, 19)

        pygame.draw.ellipse(bird_surface, self.bird_color, body_rect)
        pygame.draw.ellipse(bird_surface, (216, 170, 30), body_rect, 2)
        pygame.draw.ellipse(bird_surface, self.wing_color, wing_rect)
        pygame.draw.ellipse(bird_surface, (186, 132, 18), wing_rect, 2)
        pygame.draw.ellipse(bird_surface, (255, 255, 255), eye_rect.inflate(4, 4))
        pygame.draw.ellipse(bird_surface, self.eye_color, eye_rect)
        pygame.draw.polygon(bird_surface, self.beak_color, [(45, 23), (58, 27), (45, 33)])
        return bird_surface

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

        if pressed_action["W"] or pressed_action["LU"]:
            self._flap()

        if not self.started:
            return False

        self.ground_scroll = (self.ground_scroll + self.pipe_speed) % 48.0

        self._update_bird_physics()
        self._advance_pipes()
        self._recycle_pipes()
        self._update_score_from_pipes()

        if self._check_world_bounds():
            return False

        self._check_pipe_collision()

        return False

    def draw(self) -> None:
        self.screen.fill(self.sky_color)

        self._draw_clouds()
        self._draw_hills()

        for pipe in self.pipes:
            self._draw_pipe(pipe)

        self._draw_ground()
        self._draw_bird()

        score_text = self.score_font.render(str(self.score), True, (255, 255, 255))
        score_shadow = self.score_font.render(str(self.score), True, (65, 75, 95))
        score_rect = score_text.get_rect(midtop=(self.width // 2, 18))
        self.screen.blit(score_shadow, score_rect.move(2, 2))
        self.screen.blit(score_text, score_rect)

        best = self.hud_font.render(f"Best: {self.best_score}", True, (50, 60, 74))
        self.screen.blit(best, (16, 14))
        self._draw_hud_extras()

        if not self.started and not self.game_over:
            tip = self.tip_font.render(self._start_tip_text(), True, (50, 60, 74))
            self.screen.blit(tip, tip.get_rect(center=(self.width // 2, self.height // 2 - 92)))

        if self.game_over:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 110))
            self.screen.blit(overlay, (0, 0))

            title = self.title_font.render("Game Over", True, (255, 242, 242))
            self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 34)))

            detail = self.tip_font.render(
                f"Score: {self.score}   Best: {self.best_score}",
                True,
                (245, 245, 245),
            )
            self.screen.blit(detail, detail.get_rect(center=(self.width // 2, self.height // 2 + 8)))

            restart = self.tip_font.render(self._restart_tip_text(), True, (245, 245, 245))
            self.screen.blit(restart, restart.get_rect(center=(self.width // 2, self.height // 2 + 40)))

    def _draw_clouds(self) -> None:
        offsets = [0.0, 180.0, 420.0, 650.0]
        for i, base_x in enumerate(offsets):
            cx = (base_x - self.frame_index * (0.35 + i * 0.05)) % (self.width + 180.0) - 90.0
            cy = 72 + i * 38
            color = (245, 251, 255)
            pygame.draw.circle(self.screen, color, (int(cx), cy), 22)
            pygame.draw.circle(self.screen, color, (int(cx + 22), cy - 10), 18)
            pygame.draw.circle(self.screen, color, (int(cx + 42), cy), 20)

    def _draw_hills(self) -> None:
        ground_top = self._ground_top()
        hill_points = [
            (0, ground_top),
            (120, ground_top - 20),
            (260, ground_top - 8),
            (410, ground_top - 28),
            (560, ground_top - 14),
            (720, ground_top - 34),
            (self.width, ground_top - 18),
            (self.width, ground_top),
        ]
        pygame.draw.polygon(self.screen, self.hill_color, hill_points)

    def _draw_pipe(self, pipe: PipePair) -> None:
        top_rect, bottom_rect = self._pipe_rects(pipe)
        cap_height = 24
        cap_pad = 6

        for rect in (top_rect, bottom_rect):
            if rect.height <= 0:
                continue
            pygame.draw.rect(self.screen, self.pipe_shadow, rect.move(6, 0), border_radius=4)
            pygame.draw.rect(self.screen, self.pipe_color, rect, border_radius=4)
            shine = pygame.Rect(rect.x + 10, rect.y + 8, 12, max(0, rect.height - 16))
            if shine.height > 0:
                pygame.draw.rect(self.screen, (128, 220, 130), shine, border_radius=4)

        if top_rect.height > 0:
            top_cap = pygame.Rect(top_rect.x - cap_pad, top_rect.bottom - cap_height, top_rect.width + cap_pad * 2, cap_height)
            pygame.draw.rect(self.screen, self.pipe_shadow, top_cap.move(6, 0), border_radius=5)
            pygame.draw.rect(self.screen, (92, 200, 94), top_cap, border_radius=5)

        if bottom_rect.height > 0:
            bottom_cap = pygame.Rect(bottom_rect.x - cap_pad, bottom_rect.y, bottom_rect.width + cap_pad * 2, cap_height)
            pygame.draw.rect(self.screen, self.pipe_shadow, bottom_cap.move(6, 0), border_radius=5)
            pygame.draw.rect(self.screen, (92, 200, 94), bottom_cap, border_radius=5)

    def _draw_ground(self) -> None:
        ground_rect = pygame.Rect(0, self._ground_top(), self.width, self.ground_height)
        pygame.draw.rect(self.screen, self.ground_color, ground_rect)
        pygame.draw.line(self.screen, (210, 182, 100), (0, ground_rect.top), (self.width, ground_rect.top), 4)

        tile_w = 48
        start_x = -int(self.ground_scroll)
        for x in range(start_x, self.width + tile_w, tile_w):
            stripe = pygame.Rect(x, ground_rect.top + 18, tile_w - 10, 14)
            pygame.draw.rect(self.screen, self.ground_stripe, stripe, border_radius=5)

    def _draw_bird(self) -> None:
        x = int(self.bird.x)
        y = int(self._current_bird_y())
        angle, flip_vertical = self._bird_render_transform()
        bird_surface = self._build_bird_surface()

        if flip_vertical:
            bird_surface = pygame.transform.flip(bird_surface, False, True)
        if abs(angle) > 0.01:
            bird_surface = pygame.transform.rotate(bird_surface, angle)

        self.screen.blit(bird_surface, bird_surface.get_rect(center=(x, y)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Press W or Up Arrow to flap upward. "
            "The bird constantly falls due to gravity while pipes scroll in from the right. Fly through the gaps between the pipes to score points. Hitting a pipe, the ceiling, or the ground ends the run. After crashing, press A or Left Arrow to restart."
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

        if not self.started:
            action["W"] = True
            self.auto_wait_frames = random.randint(0, 1)
            return action

        target_pipe = None
        for pipe in self.pipes:
            if pipe.x + pipe.width >= self.bird.x - self.bird.radius:
                target_pipe = pipe
                break

        target_y = self.height * 0.46 if target_pipe is None else target_pipe.gap_y - 16.0 + target_pipe.gap_size / 2
        distance = 999.0 if target_pipe is None else target_pipe.x + target_pipe.width - self.bird.x
        threshold = 14.0 if distance > 140.0 else 8.0
        lookahead = max(3.0, min(7.0, distance / max(self.pipe_speed, 0.1) / 22.0))
        predicted_y = self.bird.y + self.bird.vy * lookahead + self.gravity * lookahead * lookahead * 0.5

        should_flap = predicted_y > target_y + threshold or self.bird.y > self._ground_top() - 90

        if should_flap:
            action["W"] = True
            self.auto_wait_frames = random.randint(0, 1)

        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(FlappyBirdBase)
