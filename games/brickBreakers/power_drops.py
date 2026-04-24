from __future__ import annotations

import math
import os
import random
import sys

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.brickBreaker import Ball, Brick, BrickBreakerBase


class FallingItem:
    size = 24

    def __init__(self, x: float, y: float, item_type: str, speed: float) -> None:
        self.x = x
        self.y = y
        self.item_type = item_type
        self.speed = speed

    def rect(self) -> pygame.Rect:
        half = self.size / 2
        return pygame.Rect(
            int(self.x - half),
            int(self.y - half),
            self.size,
            self.size,
        )


class PowerDropBrickBreaker(BrickBreakerBase):
    name = "Brick Breaker Drops"

    EXTRA_BALL = "extra_ball"
    EXTRA_LIFE = "extra_life"
    LONG_PADDLE = "long_paddle"
    FAST_PLAY = "fast_play"

    ITEM_NAMES = {
        EXTRA_BALL: "Extra Ball",
        EXTRA_LIFE: "1 Life",
        LONG_PADDLE: "Long Paddle",
        FAST_PLAY: "Speed Boost",
    }

    ITEM_COLORS = {
        EXTRA_BALL: (80, 174, 255),
        EXTRA_LIFE: (232, 92, 92),
        LONG_PADDLE: (79, 201, 127),
        FAST_PLAY: (255, 186, 58),
    }

    def __init__(self, headless: bool = False) -> None:
        self.variant_panel_h = 84
        self.variant_brick_top = 110
        self.drop_chance = 0.28
        self.item_fall_speed = 3.2
        self.paddle_growth_multiplier = 1.45
        self.speed_boost_multiplier = 1.35
        self.effect_duration_seconds = 30
        self.effect_duration_frames = 30 * 30
        self.item_weights = [3.0, 1.5, 2.5, 2.5]
        super().__init__(headless=headless)
        self.effect_duration_frames = self.fps * self.effect_duration_seconds

    def reset(self) -> None:
        self.panel_h = getattr(self, "variant_panel_h", 84)
        self.brick_top = getattr(self, "variant_brick_top", 110)

        if hasattr(self, "base_paddle_w"):
            self.paddle_w = self.base_paddle_w
            self.paddle_speed = self.base_paddle_speed
            self.ball_speed = self.base_ball_speed

        super().reset()

        self.base_paddle_w = self.paddle_w
        self.base_paddle_speed = self.paddle_speed
        self.base_ball_speed = self.ball_speed

        self.balls: list[Ball] = [self.ball]
        self.falling_items: list[FallingItem] = []
        self.effect_timers = {
            self.LONG_PADDLE: 0,
            self.FAST_PLAY: 0,
        }
        self._sync_primary_ball()

    def _sync_primary_ball(self) -> None:
        if self.balls:
            self.ball = self.balls[0]

    def _current_speed_multiplier(self) -> float:
        if getattr(self, "effect_timers", {}).get(self.FAST_PLAY, 0) > 0:
            return self.speed_boost_multiplier
        return 1.0

    def _active_ball_speed(self) -> float:
        return self.base_ball_speed * self._current_speed_multiplier()

    def _launch_stuck_ball(self, direction: int | None = None) -> None:
        if not self.ball_stuck:
            return

        self.ball_stuck = False
        self.ball.speed = self._active_ball_speed()
        self.ball.launch(direction=direction if direction is not None else random.choice([-1, 1]))
        self._enforce_vertical_speed_for(self.ball, prefer_up=True)

    def _set_ball_speed(self, ball: Ball, target_speed: float) -> None:
        ball.speed = target_speed
        speed_now = math.hypot(ball.vx, ball.vy)
        if speed_now <= 0:
            return

        scale = target_speed / speed_now
        ball.vx *= scale
        ball.vy *= scale
        self._enforce_vertical_speed_for(ball, prefer_up=ball.vy < 0)

    def _ball_rect_for(self, ball: Ball) -> pygame.Rect:
        return pygame.Rect(
            int(ball.x - ball.radius),
            int(ball.y - ball.radius),
            ball.radius * 2,
            ball.radius * 2,
        )

    def _enforce_vertical_speed_for(self, ball: Ball, prefer_up: bool = False) -> None:
        if abs(ball.vy) >= self.min_vertical_speed:
            return

        new_vy_mag = min(self.min_vertical_speed, ball.speed * 0.95)
        if prefer_up:
            ball.vy = -new_vy_mag
        elif ball.vy > 0:
            ball.vy = new_vy_mag
        elif ball.vy < 0:
            ball.vy = -new_vy_mag
        else:
            ball.vy = -new_vy_mag if ball.y > self.height * 0.5 else new_vy_mag

        vx_sq = max(ball.speed * ball.speed - ball.vy * ball.vy, 0.0)
        new_vx_mag = math.sqrt(vx_sq)
        if ball.vx < 0:
            ball.vx = -new_vx_mag
        elif ball.vx > 0:
            ball.vx = new_vx_mag
        else:
            ball.vx = new_vx_mag if random.random() < 0.5 else -new_vx_mag

    def _bounce_ball_from_paddle(self, ball: Ball) -> None:
        pad_center = self.paddle.x + self.paddle.width / 2
        dist = (ball.x - pad_center) / (self.paddle.width / 2)
        max_angle = 0.25
        ball.vx += ball.speed * dist * max_angle
        ball.vx = max(min(ball.vx, ball.speed), -ball.speed)
        vy_sq = max(ball.speed * ball.speed - ball.vx * ball.vx, 1.0)
        ball.vy = -(vy_sq ** 0.5)
        self._enforce_vertical_speed_for(ball, prefer_up=True)

    def _set_paddle_width(self, target_width: int) -> None:
        center_x = self.paddle.x + self.paddle.width / 2
        self.paddle.width = target_width
        self.paddle.x = center_x - target_width / 2
        self.paddle.x = max(0, min(self.paddle.x, self.width - self.paddle.width))
        if self.ball_stuck:
            self._snap_ball_to_paddle()

    def _refresh_paddle_length(self) -> None:
        target_width = self.base_paddle_w
        if self.effect_timers[self.LONG_PADDLE] > 0:
            target_width = int(round(self.base_paddle_w * self.paddle_growth_multiplier))
        if self.paddle.width != target_width:
            self._set_paddle_width(target_width)

    def _refresh_speed_boost(self) -> None:
        active_speed = self._active_ball_speed()
        self.ball_speed = active_speed
        self.paddle.speed = self.base_paddle_speed * self._current_speed_multiplier()
        for ball in self.balls:
            self._set_ball_speed(ball, active_speed)

    def _tick_effects(self) -> None:
        grow_was_active = self.effect_timers[self.LONG_PADDLE] > 0
        speed_was_active = self.effect_timers[self.FAST_PLAY] > 0

        for item_type in self.effect_timers:
            if self.effect_timers[item_type] > 0:
                self.effect_timers[item_type] -= 1

        if grow_was_active != (self.effect_timers[self.LONG_PADDLE] > 0):
            self._refresh_paddle_length()
        if speed_was_active != (self.effect_timers[self.FAST_PLAY] > 0):
            self._refresh_speed_boost()

    def _spawn_extra_ball(self) -> None:
        if self.ball_stuck:
            first_direction = random.choice([-1, 1])
            self._launch_stuck_ball(direction=first_direction)
            second_direction = -first_direction
        else:
            second_direction = random.choice([-1, 1])

        new_ball = Ball(
            self.paddle.x + self.paddle.width / 2,
            self.paddle.y - self.ball_radius - 1,
            self.ball_radius,
            self._active_ball_speed(),
        )
        new_ball.launch(direction=second_direction)
        self._enforce_vertical_speed_for(new_ball, prefer_up=True)
        self.balls.append(new_ball)
        self._sync_primary_ball()

    def _apply_item(self, item_type: str) -> None:
        if item_type == self.EXTRA_BALL:
            self._spawn_extra_ball()
            return

        if item_type == self.EXTRA_LIFE:
            self.lives += 1
            return

        self.effect_timers[item_type] = self.effect_duration_frames
        if item_type == self.LONG_PADDLE:
            self._refresh_paddle_length()
        elif item_type == self.FAST_PLAY:
            self._refresh_speed_boost()

    def _maybe_drop_item(self, brick: Brick) -> None:
        if random.random() >= self.drop_chance:
            return

        item_type = random.choices(
            [self.EXTRA_BALL, self.EXTRA_LIFE, self.LONG_PADDLE, self.FAST_PLAY],
            weights=self.item_weights,
            k=1,
        )[0]
        self.falling_items.append(
            FallingItem(brick.rect.centerx, brick.rect.centery, item_type, self.item_fall_speed)
        )

    def _update_falling_items(self) -> None:
        paddle_rect = self.paddle.rect()
        remaining_items: list[FallingItem] = []

        for item in self.falling_items:
            item.y += item.speed
            if item.rect().colliderect(paddle_rect):
                self._apply_item(item.item_type)
                continue
            if item.y - item.size / 2 > self.height:
                continue
            remaining_items.append(item)

        self.falling_items = remaining_items

    def _update_single_ball(self, ball: Ball) -> None:
        ball.x += ball.vx
        ball.y += ball.vy

        if ball.x - ball.radius <= 0:
            ball.x = ball.radius
            ball.vx = abs(ball.vx)
        elif ball.x + ball.radius >= self.width:
            ball.x = self.width - ball.radius
            ball.vx = -abs(ball.vx)

        if ball.y - ball.radius <= self.panel_h:
            ball.y = ball.radius + self.panel_h
            ball.vy = abs(ball.vy)

        ball_rect = self._ball_rect_for(ball)
        paddle_rect = self.paddle.rect()
        if ball.vy > 0 and ball_rect.colliderect(paddle_rect):
            ball.y = self.paddle.y - ball.radius - 1
            self._bounce_ball_from_paddle(ball)

        hit_index = -1
        for i, brick in enumerate(self.bricks):
            closest_x = min(max(ball.x, brick.rect.left), brick.rect.right)
            closest_y = min(max(ball.y, brick.rect.top), brick.rect.bottom)
            dx = ball.x - closest_x
            dy = ball.y - closest_y
            if dx * dx + dy * dy <= ball.radius * ball.radius:
                hit_index = i
                break

        if hit_index < 0:
            return

        brick = self.bricks[hit_index]
        closest_x = min(max(ball.x, brick.rect.left), brick.rect.right)
        closest_y = min(max(ball.y, brick.rect.top), brick.rect.bottom)

        nx = ball.x - closest_x
        ny = ball.y - closest_y
        dist_sq = nx * nx + ny * ny

        if dist_sq > 0:
            dist = math.sqrt(dist_sq)
            nx /= dist
            ny /= dist
        else:
            if abs(ball.vx) >= abs(ball.vy):
                nx = -1.0 if ball.vx > 0 else 1.0
                ny = 0.0
            else:
                nx = 0.0
                ny = -1.0 if ball.vy > 0 else 1.0
            dist = 0.0

        penetration = ball.radius - dist
        if penetration <= 0:
            penetration = 0.5
        ball.x += nx * penetration
        ball.y += ny * penetration

        dot = ball.vx * nx + ball.vy * ny
        if dot < 0:
            ball.vx -= 2.0 * dot * nx
            ball.vy -= 2.0 * dot * ny

        speed_now = math.hypot(ball.vx, ball.vy)
        if speed_now > 0:
            scale = ball.speed / speed_now
            ball.vx *= scale
            ball.vy *= scale
            self._enforce_vertical_speed_for(ball)

        brick.hp -= 1
        if brick.hp <= 0:
            destroyed_brick = self.bricks.pop(hit_index)
            self.score += 10
            self._maybe_drop_item(destroyed_brick)

    def _respawn_stuck_ball(self) -> None:
        self.ball_speed = self._active_ball_speed()
        self.ball = Ball(0.0, 0.0, self.ball_radius, self.ball_speed)
        self.balls = [self.ball]
        self.ball_stuck = True
        self._snap_ball_to_paddle()

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1

        pressed_action = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action[key]:
                pressed_action[key] = True
        self.prev_action = action.copy()

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.win or self.game_over:
            if not self.end_reported:
                self.end_reported = True
                self.end_event_pending = True

            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        self._tick_effects()
        self._process_paddle_input(action)

        if self.ball_stuck and (pressed_action["W"] or pressed_action["LU"]):
            self._launch_stuck_ball()

        if not self.ball_stuck:
            for ball in list(self.balls):
                self._update_single_ball(ball)

            self.balls = [
                ball for ball in self.balls
                if ball.y - ball.radius <= self.height
            ]

            if not self.balls:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                else:
                    self._respawn_stuck_ball()
            else:
                self._sync_primary_ball()

            if not self.bricks:
                self.win = True

        self._update_falling_items()
        return False

    def _draw_item_icon(self, surface: pygame.Surface, item_type: str, rect: pygame.Rect) -> None:
        fg = (245, 247, 250)
        cx, cy = rect.center

        if item_type == self.EXTRA_BALL:
            radius = max(3, rect.width // 7)
            pygame.draw.circle(surface, fg, (cx - radius - 3, cy), radius)
            pygame.draw.circle(surface, fg, (cx + radius + 3, cy), radius)
            pygame.draw.line(surface, fg, (cx, rect.top + 3), (cx, rect.bottom - 3), 2)
            pygame.draw.line(surface, fg, (rect.left + 3, cy), (rect.right - 3, cy), 2)
            return

        if item_type == self.EXTRA_LIFE:
            radius = max(3, rect.width // 5)
            pygame.draw.circle(surface, fg, (cx - radius, cy - radius // 2), radius)
            pygame.draw.circle(surface, fg, (cx + radius, cy - radius // 2), radius)
            pygame.draw.polygon(
                surface,
                fg,
                [
                    (rect.left + 4, cy - 1),
                    (rect.right - 4, cy - 1),
                    (cx, rect.bottom - 3),
                ],
            )
            return

        if item_type == self.LONG_PADDLE:
            paddle_rect = pygame.Rect(rect.left + 6, cy, rect.width - 12, max(4, rect.height // 5))
            pygame.draw.rect(surface, fg, paddle_rect, border_radius=4)
            pygame.draw.polygon(
                surface,
                fg,
                [(rect.left + 2, cy + 2), (rect.left + 8, cy - 3), (rect.left + 8, cy + 7)],
            )
            pygame.draw.polygon(
                surface,
                fg,
                [(rect.right - 2, cy + 2), (rect.right - 8, cy - 3), (rect.right - 8, cy + 7)],
            )
            return

        paddle_rect = pygame.Rect(rect.left + 4, rect.bottom - 8, rect.width - 12, 4)
        pygame.draw.rect(surface, fg, paddle_rect, border_radius=3)
        pygame.draw.circle(surface, fg, (cx - 1, rect.top + 7), max(3, rect.width // 8))
        pygame.draw.line(surface, fg, (rect.left + 3, rect.top + 7), (cx - 8, rect.top + 7), 2)
        pygame.draw.line(surface, fg, (rect.left + 6, rect.top + 3), (cx - 4, rect.top + 3), 2)
        pygame.draw.polygon(
            surface,
            fg,
            [(rect.right - 2, rect.top + 7), (rect.right - 8, rect.top + 3), (rect.right - 8, rect.top + 11)],
        )

    def _draw_falling_items(self) -> None:
        for item in self.falling_items:
            rect = item.rect()
            color = self.ITEM_COLORS[item.item_type]
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            pygame.draw.rect(self.screen, (24, 26, 30), rect, 2, border_radius=8)
            self._draw_item_icon(self.screen, item.item_type, rect.inflate(-6, -6))

    def _draw_effect_hud(self) -> None:
        active_effects = []
        if self.effect_timers[self.LONG_PADDLE] > 0:
            active_effects.append((self.LONG_PADDLE, self.effect_timers[self.LONG_PADDLE]))
        if self.effect_timers[self.FAST_PLAY] > 0:
            active_effects.append((self.FAST_PLAY, self.effect_timers[self.FAST_PLAY]))

        body_font = pygame.font.SysFont("consolas", 18, bold=True)
        timer_font = pygame.font.SysFont("consolas", 17)

        if not active_effects:
            tip = timer_font.render("Catch falling drops for power-ups.", True, (185, 191, 201))
            self.screen.blit(tip, (14, 49))
            return

        for index, (item_type, frames_left) in enumerate(active_effects):
            box = pygame.Rect(14 + index * 240, 44, 228, 32)
            pygame.draw.rect(self.screen, (47, 55, 68), box, border_radius=9)
            pygame.draw.rect(self.screen, self.ITEM_COLORS[item_type], box, 2, border_radius=9)

            icon_rect = pygame.Rect(box.x + 5, box.y + 4, 24, 24)
            self._draw_item_icon(self.screen, item_type, icon_rect)

            label = body_font.render(self.ITEM_NAMES[item_type], True, (235, 237, 242))
            self.screen.blit(label, (box.x + 34, box.y + 4))

            seconds_left = frames_left / self.fps
            timer_text = timer_font.render(f"{seconds_left:.1f}s", True, (214, 220, 228))
            timer_rect = timer_text.get_rect(midright=(box.right - 8, box.y + box.height / 2))
            self.screen.blit(timer_text, timer_rect)

    def draw(self) -> None:
        self.screen.fill((18, 22, 28))

        panel = pygame.Rect(0, 0, self.width, self.panel_h)
        pygame.draw.rect(self.screen, (34, 40, 50), panel)

        hud_font = pygame.font.SysFont("consolas", 24, bold=True)
        hud = hud_font.render(
            f"{self.name}   Score: {self.score}   Lives: {self.lives}   Balls: {len(self.balls)}",
            True,
            (234, 236, 240),
        )
        self.screen.blit(hud, (14, 9))
        self._draw_effect_hud()

        for brick in self.bricks:
            pygame.draw.rect(self.screen, brick.color, brick.rect, border_radius=4)
            pygame.draw.rect(self.screen, (24, 24, 24), brick.rect, 1, border_radius=4)

        self._draw_falling_items()

        paddle_rect = self.paddle.rect()
        pygame.draw.rect(self.screen, (220, 220, 226), paddle_rect, border_radius=8)

        for ball in self.balls:
            pygame.draw.circle(
                self.screen,
                (245, 245, 250),
                (int(ball.x), int(ball.y)),
                ball.radius,
            )

        if self.ball_stuck and not (self.win or self.game_over):
            tip_font = pygame.font.SysFont("consolas", 20)
            tip = tip_font.render("Press W / Up Arrow to launch", True, (200, 205, 215))
            self.screen.blit(tip, tip.get_rect(center=(self.width // 2, self.height - 20)))

        if self.win or self.game_over:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))

            title_font = pygame.font.SysFont("consolas", 44, bold=True)
            body_font = pygame.font.SysFont("consolas", 22)

            title_text = "You Win" if self.win else "Game Over"
            title_color = (80, 235, 120) if self.win else (235, 100, 100)
            title = title_font.render(title_text, True, title_color)
            self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 22)))

            tip = body_font.render("Press A / Left Arrow to restart", True, (224, 224, 230))
            self.screen.blit(tip, tip.get_rect(center=(self.width // 2, self.height // 2 + 24)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Move the paddle with A/D or Left/Right Arrow. "
            "Press W or Up Arrow to launch the ball. Break all bricks to win. You only lose a life when the last active ball falls off the screen. Destroyed bricks can drop items that you catch with the paddle: the double-ball icon shoots an extra ball, the heart icon gives 1 extra life, the wide-paddle icon makes the paddle longer for 30 seconds, and the speed icon makes both the paddle and every ball move faster for 30 seconds. Timed effects are shown at the top with their remaining time. When game ends, press A or Left Arrow to restart."
        )

    def _choose_focus_ball(self) -> Ball:
        descending_balls = [ball for ball in self.balls if ball.vy > 0]
        if descending_balls:
            return max(descending_balls, key=lambda ball: ball.y)
        return max(self.balls, key=lambda ball: ball.y)

    def _choose_item_target(self) -> FallingItem | None:
        catchable_items = [item for item in self.falling_items if item.y > self.height * 0.45]
        if not catchable_items:
            return None
        return max(catchable_items, key=lambda item: item.y)

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if self.frame_index % self.moveInterval != 0:
            return self.prev_action

        if self.win or self.game_over:
            if random.random() < 0.2:
                action["A"] = True
            return action

        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action

        if self.ball_stuck:
            if random.random() < 0.3:
                action["W"] = True
            else:
                action[random.choice(["A", "D"])] = True
            self.auto_wait_frames = random.randint(0, 2)
            return action

        focus_ball = self._choose_focus_ball()
        paddle_center = self.paddle.x + self.paddle.width / 2
        target_x = focus_ball.x

        urgent_ball = any(ball.vy > 0 and ball.y > self.height * 0.55 for ball in self.balls)
        item_target = self._choose_item_target()
        if item_target is not None and not urgent_ball and focus_ball.vy < 0:
            target_x = item_target.x
        elif focus_ball.vy < 0:
            target_x = paddle_center + self.auto_jitter_dir * random.uniform(8.0, 26.0)

        if target_x < paddle_center - 8:
            action["A"] = True
        elif target_x > paddle_center + 8:
            action["D"] = True

        if random.random() < 0.12:
            self.auto_jitter_dir *= -1

        if random.random() < 0.12:
            self.auto_wait_frames = random.randint(0, 2)
        return action


if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(PowerDropBrickBreaker)
