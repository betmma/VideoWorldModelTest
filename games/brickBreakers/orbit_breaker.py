from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.brickBreaker import Ball, BrickBreakerBase


@dataclass
class OrbitPaddle:
    angle: float
    span: float
    radius: float
    thickness: int
    angular_speed: float


@dataclass
class RingBrick:
    inner_radius: float
    outer_radius: float
    angle: float
    span: float
    hp: int
    color: tuple[int, int, int]


class OrbitalBrickBreaker(BrickBreakerBase):
    name = "Brick Breaker Orbit"

    def __init__(self, headless: bool = False) -> None:
        self.orbit_panel_h = 56
        self.paddle_arc_span = 0.8
        self.paddle_angular_speed = 0.078
        self.paddle_thickness = 16
        self.ball_loss_buffer = 34
        self.brick_ring_gap = 8
        self.brick_ring_width = 18
        self.brick_segments = [6, 9, 12, 15]
        self.paddle_spin_dir = 0
        self.ball_lost = False
        super().__init__(headless=headless)

    def reset(self) -> None:
        self.score = 0
        self.lives = 3
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.win = False
        self.game_over = False

        self.auto_wait_frames = 0
        self.auto_jitter_dir = 1
        self.paddle_spin_dir = 0
        self.ball_lost = False

        self.panel_h = self.orbit_panel_h
        play_h = self.height - self.panel_h
        self.center_x = self.width / 2
        self.center_y = self.panel_h + play_h / 2 + 6
        self.arena_radius = min(self.width * 0.23, play_h * 0.44)
        self.paddle = OrbitPaddle(
            angle=math.pi / 2,
            span=self.paddle_arc_span,
            radius=self.arena_radius - 10,
            thickness=self.paddle_thickness,
            angular_speed=self.paddle_angular_speed,
        )

        self.ball = Ball(0.0, 0.0, self.ball_radius, self.ball_speed)
        self.ball_stuck = True
        self.bricks: list[RingBrick] = []
        self._build_bricks()
        self._snap_ball_to_paddle()

    def _normalize_angle(self, angle: float) -> float:
        return (angle + math.pi) % (2 * math.pi) - math.pi

    def _clamp(self, value: float, lo: float, hi: float) -> float:
        return max(lo, min(value, hi))

    def _point_on_circle(self, radius: float, angle: float) -> tuple[float, float]:
        return (
            self.center_x + radius * math.cos(angle),
            self.center_y + radius * math.sin(angle),
        )

    def _ball_polar(self) -> tuple[float, float, float, float]:
        dx = self.ball.x - self.center_x
        dy = self.ball.y - self.center_y
        radius = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)
        return dx, dy, radius, angle

    def _build_bricks(self) -> None:
        palette = [
            (242, 99, 91),
            (244, 176, 64),
            (94, 201, 126),
            (78, 163, 236),
        ]

        self.bricks = []
        inner_start = 36.0
        for ring_index, segments in enumerate(self.brick_segments):
            inner_radius = inner_start + ring_index * (self.brick_ring_width + self.brick_ring_gap)
            outer_radius = inner_radius + self.brick_ring_width
            gap_angle = 0.06 + ring_index * 0.004
            brick_span = (2 * math.pi / segments) - gap_angle
            angle_step = 2 * math.pi / segments
            angle_offset = angle_step / 2 if ring_index % 2 else 0.0

            for segment_index in range(segments):
                angle = angle_offset + segment_index * angle_step
                self.bricks.append(
                    RingBrick(
                        inner_radius=inner_radius,
                        outer_radius=outer_radius,
                        angle=angle,
                        span=brick_span,
                        hp=1,
                        color=palette[ring_index % len(palette)],
                    )
                )

    def _snap_ball_to_paddle(self) -> None:
        stick_radius = self.paddle.radius - self.paddle.thickness / 2 - self.ball.radius - 2
        self.ball.x, self.ball.y = self._point_on_circle(stick_radius, self.paddle.angle)
        self.ball.vx = 0.0
        self.ball.vy = 0.0

    def _launch_ball(self) -> None:
        if not self.ball_stuck:
            return

        self.ball_stuck = False
        normal_x = math.cos(self.paddle.angle)
        normal_y = math.sin(self.paddle.angle)
        tangent_x = -normal_y
        tangent_y = normal_x
        side_bias = random.uniform(-0.7, 0.7)

        dir_x = -normal_x + tangent_x * side_bias
        dir_y = -normal_y + tangent_y * side_bias
        length = math.hypot(dir_x, dir_y)
        if length <= 0:
            dir_x = -normal_x
            dir_y = -normal_y
            length = 1.0

        self.ball.vx = dir_x / length * self.ball.speed
        self.ball.vy = dir_y / length * self.ball.speed

    def _nearest_point_on_brick(self, brick: RingBrick) -> tuple[float, float]:
        _, _, radius, angle = self._ball_polar()
        local_angle = self._normalize_angle(angle - brick.angle)
        clamped_angle = brick.angle + self._clamp(local_angle, -brick.span / 2, brick.span / 2)
        clamped_radius = self._clamp(radius, brick.inner_radius, brick.outer_radius)
        return self._point_on_circle(clamped_radius, clamped_angle)

    def _normalize_ball_speed(self) -> None:
        speed_now = math.hypot(self.ball.vx, self.ball.vy)
        if speed_now <= 0:
            return
        scale = self.ball.speed / speed_now
        self.ball.vx *= scale
        self.ball.vy *= scale

    def _bounce_from_orbit_paddle(self, local_angle: float) -> None:
        dx, dy, radius, _ = self._ball_polar()
        if radius <= 0:
            return

        normal_x = dx / radius
        normal_y = dy / radius
        tangent_x = -normal_y
        tangent_y = normal_x

        offset = local_angle / max(self.paddle.span / 2, 0.001)
        offset = self._clamp(offset, -1.0, 1.0)
        control = self._clamp(offset + self.paddle_spin_dir * 0.18, -1.15, 1.15)

        dir_x = -normal_x + tangent_x * control
        dir_y = -normal_y + tangent_y * control
        length = math.hypot(dir_x, dir_y)
        if length <= 0:
            return

        self.ball.vx = dir_x / length * self.ball.speed
        self.ball.vy = dir_y / length * self.ball.speed

    def _handle_paddle_collision(self) -> None:
        dx, dy, _, ball_angle = self._ball_polar()
        local_angle = self._normalize_angle(ball_angle - self.paddle.angle)
        clamped_angle = self.paddle.angle + self._clamp(local_angle, -self.paddle.span / 2, self.paddle.span / 2)
        contact_x, contact_y = self._point_on_circle(self.paddle.radius, clamped_angle)

        diff_x = self.ball.x - contact_x
        diff_y = self.ball.y - contact_y
        dist = math.hypot(diff_x, diff_y)
        collision_radius = self.ball.radius + self.paddle.thickness / 2
        moving_outward = self.ball.vx * dx + self.ball.vy * dy > 0

        if not moving_outward:
            return
        if abs(local_angle) > self.paddle.span / 2 + 0.08:
            return
        if dist > collision_radius + 0.5:
            return

        if dist > 0:
            normal_x = diff_x / dist
            normal_y = diff_y / dist
        else:
            radius = math.hypot(dx, dy) or 1.0
            normal_x = dx / radius
            normal_y = dy / radius

        penetration = collision_radius - dist
        if penetration <= 0:
            penetration = 0.5
        self.ball.x += normal_x * penetration
        self.ball.y += normal_y * penetration
        self._bounce_from_orbit_paddle(local_angle)

    def _handle_brick_collision(self) -> None:
        hit_index = -1
        hit_point = (0.0, 0.0)

        for index, brick in enumerate(self.bricks):
            nearest_x, nearest_y = self._nearest_point_on_brick(brick)
            diff_x = self.ball.x - nearest_x
            diff_y = self.ball.y - nearest_y
            if diff_x * diff_x + diff_y * diff_y <= self.ball.radius * self.ball.radius:
                hit_index = index
                hit_point = (nearest_x, nearest_y)
                break

        if hit_index < 0:
            return

        nearest_x, nearest_y = hit_point
        diff_x = self.ball.x - nearest_x
        diff_y = self.ball.y - nearest_y
        dist = math.hypot(diff_x, diff_y)

        if dist > 0:
            normal_x = diff_x / dist
            normal_y = diff_y / dist
        else:
            dx, dy, radius, _ = self._ball_polar()
            radius = radius or 1.0
            normal_x = dx / radius
            normal_y = dy / radius
            dist = 0.0

        penetration = self.ball.radius - dist
        if penetration <= 0:
            penetration = 0.5
        self.ball.x += normal_x * penetration
        self.ball.y += normal_y * penetration

        dot = self.ball.vx * normal_x + self.ball.vy * normal_y
        if dot < 0:
            self.ball.vx -= 2.0 * dot * normal_x
            self.ball.vy -= 2.0 * dot * normal_y
            self._normalize_ball_speed()

        brick = self.bricks[hit_index]
        brick.hp -= 1
        if brick.hp <= 0:
            self.bricks.pop(hit_index)
            self.score += 10

    def _update_ball_physics(self) -> None:
        self.ball_lost = False
        self.ball.x += self.ball.vx
        self.ball.y += self.ball.vy

        self._handle_brick_collision()
        self._handle_paddle_collision()

        _, _, radius, _ = self._ball_polar()
        if radius - self.ball.radius > self.arena_radius + self.ball_loss_buffer:
            self.ball_lost = True

    def _process_paddle_input(self, action: ActionState) -> None:
        turn = 0
        if action["A"] or action["LL"]:
            turn += 1
        if action["D"] or action["LR"]:
            turn -= 1

        self.paddle_spin_dir = turn
        self.paddle.angle = self._normalize_angle(self.paddle.angle + turn * self.paddle.angular_speed)

        if self.ball_stuck:
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

        self._process_paddle_input(action)

        if self.ball_stuck and (pressed_action["W"] or pressed_action["LU"]):
            self._launch_ball()

        if not self.ball_stuck:
            self._update_ball_physics()

            if not self.bricks:
                self.win = True
            elif self.ball_lost:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                else:
                    self.ball_stuck = True
                    self._snap_ball_to_paddle()

        return False

    def _segment_points(
        self,
        inner_radius: float,
        outer_radius: float,
        angle: float,
        span: float,
    ) -> list[tuple[int, int]]:
        start = angle - span / 2
        end = angle + span / 2
        steps = max(6, int(span * 20))
        points: list[tuple[int, int]] = []

        for step in range(steps + 1):
            t = step / steps
            arc_angle = start + (end - start) * t
            x, y = self._point_on_circle(outer_radius, arc_angle)
            points.append((int(x), int(y)))

        for step in range(steps, -1, -1):
            t = step / steps
            arc_angle = start + (end - start) * t
            x, y = self._point_on_circle(inner_radius, arc_angle)
            points.append((int(x), int(y)))

        return points

    def _draw_bricks(self) -> None:
        for brick in self.bricks:
            points = self._segment_points(
                brick.inner_radius,
                brick.outer_radius,
                brick.angle,
                brick.span,
            )
            pygame.draw.polygon(self.screen, brick.color, points)
            pygame.draw.polygon(self.screen, (20, 24, 30), points, 4)

    def _draw_paddle(self) -> None:
        outer_rect = pygame.Rect(0, 0, int(self.paddle.radius * 2), int(self.paddle.radius * 2))
        outer_rect.center = (int(self.center_x), int(self.center_y))
        start = self.paddle.angle - self.paddle.span / 2
        end = self.paddle.angle + self.paddle.span / 2

        pygame.draw.arc(
            self.screen,
            (96, 209, 255),
            outer_rect,
            -end,
            -start,
            self.paddle.thickness,
        )
        pygame.draw.arc(
            self.screen,
            (241, 245, 250),
            outer_rect,
            -end,
            -start,
            self.paddle.thickness-4,
        )

    def draw(self) -> None:
        self.screen.fill((13, 18, 24))

        panel = pygame.Rect(0, 0, self.width, self.panel_h)
        pygame.draw.rect(self.screen, (30, 37, 48), panel)

        hud_font = pygame.font.SysFont("consolas", 24, bold=True)
        hud = hud_font.render(f"{self.name}   Score: {self.score}   Lives: {self.lives}", True, (234, 236, 240))
        self.screen.blit(hud, (14, 12))

        arena_center = (int(self.center_x), int(self.center_y))
        pygame.draw.circle(self.screen, (32, 39, 50), arena_center, int(self.arena_radius + 9), 3)
        pygame.draw.circle(self.screen, (20, 24, 31), arena_center, int(self.arena_radius - 26), 1)
        pygame.draw.circle(self.screen, (24, 29, 37), arena_center, 26)
        pygame.draw.circle(self.screen, (48, 57, 71), arena_center, 26, 2)

        self._draw_bricks()
        self._draw_paddle()

        pygame.draw.circle(
            self.screen,
            (245, 245, 250),
            (int(self.ball.x), int(self.ball.y)),
            self.ball.radius,
        )

        if self.ball_stuck and not (self.win or self.game_over):
            tip_font = pygame.font.SysFont("consolas", 20)
            tip = tip_font.render("Press W / Up Arrow to launch inward", True, (200, 205, 215))
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
            f"This is {self.name}. Rotate the paddle around the arena with A/D or Left/Right Arrow. "
            "Press W or Up Arrow to launch the ball inward from the rim. The bricks are arranged as concentric rings of arc segments around the center. Keep the ball from escaping past the rotating paddle, break every segment to win, and press A or Left Arrow to restart after the game ends."
        )

    def _predict_intercept_angle(self) -> float:
        dx = self.ball.x - self.center_x
        dy = self.ball.y - self.center_y
        vx = self.ball.vx
        vy = self.ball.vy
        target_radius = self.paddle.radius

        a = vx * vx + vy * vy
        if a <= 0:
            return math.atan2(dy, dx)

        b = 2.0 * (dx * vx + dy * vy)
        c = dx * dx + dy * dy - target_radius * target_radius
        discriminant = b * b - 4.0 * a * c
        if discriminant < 0:
            return math.atan2(dy, dx)

        root = math.sqrt(discriminant)
        candidates = [
            (-b - root) / (2.0 * a),
            (-b + root) / (2.0 * a),
        ]
        future_times = [value for value in candidates if value > 0.1]
        if not future_times:
            return math.atan2(dy, dx)

        t = min(future_times)
        return math.atan2(dy + vy * t, dx + vx * t)

    def getAutoAction(self, frame_index: int) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if frame_index % self.moveInterval != 0:
            return self.prev_action

        if self.win or self.game_over:
            if random.random() < 0.2:
                action["A"] = True
            return action

        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action

        if self.ball_stuck:
            if random.random() < 0.35:
                action["W"] = True
            else:
                action[random.choice(["A", "D"])] = True
            self.auto_wait_frames = random.randint(0, 2)
            return action

        target_angle = self._predict_intercept_angle()
        delta = self._normalize_angle(target_angle - self.paddle.angle)

        if delta > 0.04:
            action["A"] = True
        elif delta < -0.04:
            action["D"] = True

        if random.random() < 0.06:
            self.auto_wait_frames = 1
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(OrbitalBrickBreaker)
