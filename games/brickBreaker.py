from __future__ import annotations

import os
import random
import sys
import math

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class Paddle:
    def __init__(self, x: float, y: float, width: int, height: int, speed: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = speed

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)


class Ball:
    def __init__(self, x: float, y: float, radius: int, speed: float) -> None:
        self.x = x
        self.y = y
        self.radius = radius
        self.speed = speed
        self.vx = 0.0
        self.vy = 0.0

    def launch(self, direction: int = 1) -> None:
        self.vx = self.speed * direction * 0.7
        self.vy = -self.speed


class Brick:
    def __init__(self, rect: pygame.Rect, hp: int, color: tuple[int, int, int]) -> None:
        self.rect = rect
        self.hp = hp
        self.color = color


class BrickBreakerBase(GameBase):
    name = "Brick Breaker"
    variantsPath = "brickBreakers"

    def __init__(self, headless: bool = False) -> None:
        self.paddle_w = 140
        self.paddle_h = 16
        self.paddle_speed = 9.0

        self.ball_radius = 8
        self.ball_speed = 6.0

        self.brick_rows = 6
        self.brick_cols = 11
        self.brick_gap = 6
        self.brick_top = 70
        self.brick_h = 24
        
        self.panel_h = 44

        self.end_screen_auto_reset = 120
        self.min_vertical_speed = 0.5

        super().__init__(headless=headless)
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

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

        px = (self.width - self.paddle_w) / 2
        py = self.height - 50
        self.paddle = Paddle(px, py, self.paddle_w, self.paddle_h, self.paddle_speed)

        self.ball = Ball(0.0, 0.0, self.ball_radius, self.ball_speed)
        self.ball_stuck = True
        self._snap_ball_to_paddle()

        self.bricks: list[Brick] = []
        self._build_bricks()

    def _build_bricks(self) -> None:
        self.bricks = []
        side_pad = 26
        board_w = self.width - side_pad * 2
        brick_w = (board_w - self.brick_gap * (self.brick_cols - 1)) // self.brick_cols

        palette = [
            (231, 76, 60),
            (243, 156, 18),
            (241, 196, 15),
            (46, 204, 113),
            (52, 152, 219),
            (155, 89, 182),
        ]

        for r in range(self.brick_rows):
            y = self.brick_top + r * (self.brick_h + self.brick_gap)
            for c in range(self.brick_cols):
                x = side_pad + c * (brick_w + self.brick_gap)
                color = palette[r % len(palette)]
                self.bricks.append(Brick(pygame.Rect(x, y, brick_w, self.brick_h), 1, color))

    def _snap_ball_to_paddle(self) -> None:
        self.ball.x = self.paddle.x + self.paddle.width / 2
        self.ball.y = self.paddle.y - self.ball.radius - 1
        self.ball.vx = 0.0
        self.ball.vy = 0.0

    def _launch_ball(self) -> None:
        if not self.ball_stuck:
            return
        self.ball_stuck = False
        direction = random.choice([-1, 1])
        self.ball.launch(direction=direction)

    def _bounce_from_paddle(self) -> None:
        pad_center = self.paddle.x + self.paddle.width / 2
        dist = (self.ball.x - pad_center) / (self.paddle.width / 2)
        max_angle = 0.25
        self.ball.vx += self.ball.speed * dist * max_angle
        self.ball.vx = max(min(self.ball.vx, self.ball.speed), -self.ball.speed)
        vy_sq = max(self.ball.speed * self.ball.speed - self.ball.vx * self.ball.vx, 1.0)
        self.ball.vy = -(vy_sq ** 0.5)
        self._enforce_vertical_speed(prefer_up=True)

    def _enforce_vertical_speed(self, prefer_up: bool = False) -> None:
        if abs(self.ball.vy) >= self.min_vertical_speed:
            return

        new_vy_mag = min(self.min_vertical_speed, self.ball.speed * 0.95)
        if prefer_up:
            self.ball.vy = -new_vy_mag
        elif self.ball.vy > 0:
            self.ball.vy = new_vy_mag
        elif self.ball.vy < 0:
            self.ball.vy = -new_vy_mag
        else:
            self.ball.vy = -new_vy_mag if self.ball.y > self.height * 0.5 else new_vy_mag

        vx_sq = max(self.ball.speed * self.ball.speed - self.ball.vy * self.ball.vy, 0.0)
        new_vx_mag = math.sqrt(vx_sq)
        if self.ball.vx < 0:
            self.ball.vx = -new_vx_mag
        elif self.ball.vx > 0:
            self.ball.vx = new_vx_mag
        else:
            self.ball.vx = new_vx_mag if random.random() < 0.5 else -new_vx_mag

    def _ball_rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.ball.x - self.ball.radius),
            int(self.ball.y - self.ball.radius),
            self.ball.radius * 2,
            self.ball.radius * 2,
        )

    def _update_ball_physics(self) -> None:
        self.ball.x += self.ball.vx
        self.ball.y += self.ball.vy

        if self.ball.x - self.ball.radius <= 0:
            self.ball.x = self.ball.radius
            self.ball.vx = abs(self.ball.vx)
        elif self.ball.x + self.ball.radius >= self.width:
            self.ball.x = self.width - self.ball.radius
            self.ball.vx = -abs(self.ball.vx)

        if self.ball.y - self.ball.radius <= self.panel_h:
            self.ball.y = self.ball.radius + self.panel_h
            self.ball.vy = abs(self.ball.vy)

        ball_rect = self._ball_rect()
        paddle_rect = self.paddle.rect()
        if self.ball.vy > 0 and ball_rect.colliderect(paddle_rect):
            self.ball.y = self.paddle.y - self.ball.radius - 1
            self._bounce_from_paddle()

        hit_index = -1
        for i, brick in enumerate(self.bricks):
            closest_x = min(max(self.ball.x, brick.rect.left), brick.rect.right)
            closest_y = min(max(self.ball.y, brick.rect.top), brick.rect.bottom)
            dx = self.ball.x - closest_x
            dy = self.ball.y - closest_y
            if dx * dx + dy * dy <= self.ball.radius * self.ball.radius:
                hit_index = i
                break

        if hit_index >= 0:
            brick = self.bricks[hit_index]
            closest_x = min(max(self.ball.x, brick.rect.left), brick.rect.right)
            closest_y = min(max(self.ball.y, brick.rect.top), brick.rect.bottom)

            nx = self.ball.x - closest_x
            ny = self.ball.y - closest_y
            dist_sq = nx * nx + ny * ny

            if dist_sq > 0:
                dist = math.sqrt(dist_sq)
                nx /= dist
                ny /= dist
            else:
                if abs(self.ball.vx) >= abs(self.ball.vy):
                    nx = -1.0 if self.ball.vx > 0 else 1.0
                    ny = 0.0
                else:
                    nx = 0.0
                    ny = -1.0 if self.ball.vy > 0 else 1.0
                dist = 0.0

            penetration = self.ball.radius - dist
            if penetration <= 0:
                penetration = 0.5
            self.ball.x += nx * penetration
            self.ball.y += ny * penetration

            dot = self.ball.vx * nx + self.ball.vy * ny
            if dot < 0:
                self.ball.vx -= 2.0 * dot * nx
                self.ball.vy -= 2.0 * dot * ny

            speed_now = math.sqrt(self.ball.vx * self.ball.vx + self.ball.vy * self.ball.vy)
            if speed_now > 0:
                scale = self.ball.speed / speed_now
                self.ball.vx *= scale
                self.ball.vy *= scale
                self._enforce_vertical_speed()

            brick.hp -= 1
            if brick.hp <= 0:
                self.bricks.pop(hit_index)
                self.score += 10

    def _process_paddle_input(self, action: ActionState) -> None:
        move = 0.0
        if action["A"] or action["LL"]:
            move -= self.paddle.speed
        if action["D"] or action["LR"]:
            move += self.paddle.speed

        self.paddle.x += move
        if self.paddle.x < 0:
            self.paddle.x = 0
        if self.paddle.x + self.paddle.width > self.width:
            self.paddle.x = self.width - self.paddle.width

        if self.ball_stuck:
            self._snap_ball_to_paddle()

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1

        pressed_action = self.BLANK_ACTION.copy()
        for k, v in action.items():
            if v and not self.prev_action[k]:
                pressed_action[k] = True
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

            if self.ball.y - self.ball.radius > self.height:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                else:
                    self.ball_stuck = True
                    self._snap_ball_to_paddle()

            if not self.bricks:
                self.win = True

        return False

    def draw(self) -> None:
        self.screen.fill((18, 22, 28))

        panel = pygame.Rect(0, 0, self.width, self.panel_h)
        pygame.draw.rect(self.screen, (34, 40, 50), panel)

        hud_font = pygame.font.SysFont("consolas", 24, bold=True)
        hud = hud_font.render(f"{self.name}   Score: {self.score}   Lives: {self.lives}", True, (234, 236, 240))
        self.screen.blit(hud, (14, 10))

        for brick in self.bricks:
            pygame.draw.rect(self.screen, brick.color, brick.rect, border_radius=4)
            pygame.draw.rect(self.screen, (24, 24, 24), brick.rect, 1, border_radius=4)

        paddle_rect = self.paddle.rect()
        pygame.draw.rect(self.screen, (220, 220, 226), paddle_rect, border_radius=8)

        pygame.draw.circle(
            self.screen,
            (245, 245, 250),
            (int(self.ball.x), int(self.ball.y)),
            self.ball.radius,
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
            "Press W or Up Arrow to launch the ball. The ball bounces off walls and the paddle. Break all bricks to win. Missing the ball costs one life. When game ends, press A or Left Arrow to restart."
        )

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
            if self.frame_index % self.moveInterval != 0:
                return action
            if random.random() < 0.25:
                action["W"] = True
            else:
                action[random.choice(["A", "D"])] = True
            self.auto_wait_frames = random.randint(0, 2)
            return action

        target_x = self.ball.x
        if self.ball.vy < 0:
            target_x = self.paddle.x + self.paddle.width / 2 + self.auto_jitter_dir * random.uniform(8.0, 26.0)

        paddle_center = self.paddle.x + self.paddle.width / 2
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

    run_autoplay(BrickBreakerBase)
