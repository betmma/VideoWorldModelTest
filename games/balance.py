import math, os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class BalanceGame(GameBase):
    name = "Balance"

    def __init__(self, headless: bool = False) -> None:
        """Initialize the balance physics, dimensions, and visual theme."""
        self.rail_length = self.width * 58 // 100
        self.rail_thickness = self.height // 34
        self.bracket_height = self.height // 8
        self.bracket_width = self.height // 24
        self.ball_radius = self.height // 28
        self.max_angle = 0.34
        self.angle_acceleration = 0.05
        self.angle_damping = 0.91
        self.ball_acceleration = 58.0
        self.ball_damping = 0.996
        super().__init__(headless=headless)
        self.theme = self._make_theme()
        self.reset()

    def _make_theme(self) -> dict[str, tuple[int, int, int]]:
        """Choose one visual theme for the balance."""
        themes = [
            {"bg_top": (232, 237, 243), "bg_bottom": (206, 216, 228), "stand": (88, 99, 113), "stand_dark": (54, 63, 75), "rail": (61, 75, 92), "rail_light": (112, 130, 150), "rail_dark": (35, 45, 58), "ball": (230, 87, 82), "ball_light": (255, 182, 164), "ball_dark": (144, 35, 41), "trail": (230, 87, 82)},
            {"bg_top": (28, 35, 46), "bg_bottom": (18, 23, 31), "stand": (190, 199, 210), "stand_dark": (112, 126, 144), "rail": (220, 228, 236), "rail_light": (255, 255, 255), "rail_dark": (137, 151, 169), "ball": (255, 198, 73), "ball_light": (255, 236, 157), "ball_dark": (176, 108, 24), "trail": (255, 198, 73)},
            {"bg_top": (245, 234, 220), "bg_bottom": (224, 203, 184), "stand": (113, 83, 65), "stand_dark": (73, 51, 39), "rail": (82, 132, 153), "rail_light": (145, 198, 218), "rail_dark": (39, 82, 102), "ball": (87, 178, 111), "ball_light": (172, 238, 186), "ball_dark": (33, 105, 63), "trail": (87, 178, 111)},
        ]
        return random.choice(themes)

    def reset(self) -> None:
        """Reset the balance, ball, trail, and autoplay state."""
        self.frame_index = 0
        self.angle = random.uniform(-0.08, 0.08)
        self.angle_velocity = 0.0
        self.ball_limit = self.rail_length / 2 - self.ball_radius
        self.ball_x = random.uniform(-self.ball_limit * 0.35, self.ball_limit * 0.35)
        self.ball_velocity = random.uniform(-8.0, 8.0)
        self.trail = []
        self.auto_key = None
        self.auto_ticks_left = random.randint(3, 10)
        self._record_trail()

    def update(self, action: ActionState) -> bool:
        """Advance the angle, ball physics, and trail by one frame."""
        self.frame_index += 1
        dt = 1 / self.fps
        self._apply_controls(action, dt)
        self._update_ball(dt)
        self._record_trail()
        return False

    def _apply_controls(self, action: ActionState, dt: float) -> None:
        """Use A and D to rotate the balance within a small angle range."""
        if action["A"]:
            self.angle_velocity -= self.angle_acceleration * dt
        if action["D"]:
            self.angle_velocity += self.angle_acceleration * dt
        self.angle_velocity *= self.angle_damping
        self.angle += self.angle_velocity
        if self.angle < -self.max_angle:
            self.angle = -self.max_angle
            self.angle_velocity = 0.0
        if self.angle > self.max_angle:
            self.angle = self.max_angle
            self.angle_velocity = 0.0

    def _update_ball(self, dt: float) -> None:
        """Roll the ball along the tilted balance and keep it inside the bracket."""
        self.ball_velocity += math.sin(self.angle) * self.ball_acceleration * dt
        self.ball_velocity *= self.ball_damping
        self.ball_x += self.ball_velocity * dt
        if self.ball_x < -self.ball_limit:
            self.ball_x = -self.ball_limit
            self.ball_velocity = abs(self.ball_velocity) * 0.25
        if self.ball_x > self.ball_limit:
            self.ball_x = self.ball_limit
            self.ball_velocity = -abs(self.ball_velocity) * 0.25

    def draw(self) -> None:
        """Draw the background, stand, balance bracket, trail, and ball."""
        self._draw_background()
        self._draw_stand()
        self._draw_bracket()
        self._draw_trail()
        self._draw_ball()

    def _draw_background(self) -> None:
        """Draw a vertical background gradient."""
        top = self.theme["bg_top"]
        bottom = self.theme["bg_bottom"]
        denom = self.height - 1
        for y in range(self.height):
            color = ((top[0] * (denom - y) + bottom[0] * y) // denom, (top[1] * (denom - y) + bottom[1] * y) // denom, (top[2] * (denom - y) + bottom[2] * y) // denom)
            pygame.draw.line(self.screen, color, (0, y), (self.width, y))

    def _pivot(self) -> tuple[int, int]:
        """Return the screen pivot point for the rotating balance."""
        return self.width // 2, self.height * 58 // 100

    def _local_point(self, x: float, y: float) -> tuple[int, int]:
        """Transform a balance-local point into screen coordinates."""
        pivot_x, pivot_y = self._pivot()
        cos_angle = math.cos(self.angle)
        sin_angle = math.sin(self.angle)
        return round(pivot_x + x * cos_angle - y * sin_angle), round(pivot_y + x * sin_angle + y * cos_angle)

    def _local_rect_points(self, left: float, top: float, width: float, height: float) -> list[tuple[int, int]]:
        """Return transformed polygon points for a local rectangle."""
        return [self._local_point(left, top), self._local_point(left + width, top), self._local_point(left + width, top + height), self._local_point(left, top + height)]

    def _draw_stand(self) -> None:
        """Draw the stationary support under the balance."""
        pivot_x, pivot_y = self._pivot()
        base_y = self.height * 82 // 100
        pygame.draw.polygon(self.screen, self.theme["stand_dark"], [(pivot_x - self.height // 8, base_y), (pivot_x + self.height // 8, base_y), (pivot_x, pivot_y + self.height // 20)])
        pygame.draw.polygon(self.screen, self.theme["stand"], [(pivot_x - self.height // 11, base_y), (pivot_x + self.height // 11, base_y), (pivot_x, pivot_y + self.height // 18)])
        pygame.draw.circle(self.screen, self.theme["stand_dark"], (pivot_x, pivot_y), self.height // 32)
        pygame.draw.circle(self.screen, self.theme["stand"], (pivot_x, pivot_y), self.height // 44)

    def _draw_bracket(self) -> None:
        """Draw the rotating square bracket shaped balance."""
        half = self.rail_length / 2
        base = self._local_rect_points(-half, 0, self.rail_length, self.rail_thickness)
        left_side = self._local_rect_points(-half - self.bracket_width, -self.bracket_height, self.bracket_width, self.bracket_height + self.rail_thickness)
        right_side = self._local_rect_points(half, -self.bracket_height, self.bracket_width, self.bracket_height + self.rail_thickness)
        pygame.draw.polygon(self.screen, self.theme["rail_dark"], self._local_rect_points(-half - self.bracket_width, self.rail_thickness, self.rail_length + self.bracket_width * 2, self.rail_thickness // 2))
        for points in (base, left_side, right_side):
            pygame.draw.polygon(self.screen, self.theme["rail"], points)
            pygame.draw.lines(self.screen, self.theme["rail_light"], True, points, 2)

    def _ball_center(self) -> tuple[int, int]:
        """Return the current screen center of the ball."""
        return self._local_point(self.ball_x, -self.ball_radius - 2)

    def _record_trail(self) -> None:
        """Store the current ball position and speed for the fading trail."""
        x, y = self._ball_center()
        self.trail.append((x, y, abs(self.ball_velocity)))
        if len(self.trail) > 28:
            self.trail.pop(0)

    def _draw_trail(self) -> None:
        """Draw fading circles behind the ball to show its speed."""
        layer = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        trail_count = len(self.trail)
        for index, (x, y, speed) in enumerate(self.trail):
            progress = (index + 1) / trail_count
            speed_scale = speed / 170
            if speed_scale > 1.0:
                speed_scale = 1.0
            alpha = round((122 + 90 * speed_scale) * progress)
            radius = round(self.ball_radius * (0.85 + 0.55 * speed_scale) * progress)
            color = (*self.theme["trail"], alpha)
            pygame.draw.circle(layer, color, (x, y), radius)
        self.screen.blit(layer, (0, 0))

    def _draw_ball(self) -> None:
        """Draw the rolling ball."""
        x, y = self._ball_center()
        pygame.draw.circle(self.screen, self.theme["ball_dark"], (x, y + self.ball_radius // 10), self.ball_radius)
        pygame.draw.circle(self.screen, self.theme["ball"], (x, y), self.ball_radius)
        pygame.draw.circle(self.screen, self.theme["ball_light"], (x - self.ball_radius // 3, y - self.ball_radius // 3), self.ball_radius // 4)

    def _choose_auto_key(self) -> str | None:
        """Choose the next held autoplay key without forcing the ball to stay centered."""
        if self.ball_x > self.ball_limit * 0.74:
            return "A"
        if self.ball_x < -self.ball_limit * 0.74:
            return "D"
        if self.angle > self.max_angle * 0.75:
            return "A"
        if self.angle < -self.max_angle * 0.75:
            return "D"
        return random.choice([None, None, "A", "D"])

    def getPrompt(self) -> str:
        """Return the prompt describing the balance controls and physics."""
        return "This is Balance. Press A to rotate the square bracket balance counterclockwise, and press D to rotate it clockwise. The ball rolls slowly along the tilted balance because of gravity. The ball stays inside the bracket and cannot fall off. A fading trail follows the ball to show its speed."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Hold A, D, or blank actions while switching only on moveInterval frames."""
        action = self.BLANK_ACTION.copy()
        if frame_index % self.moveInterval == 0:
            if self.auto_ticks_left <= 0:
                self.auto_key = self._choose_auto_key()
                self.auto_ticks_left = random.randint(4, 18)
            else:
                self.auto_ticks_left -= 1
        if self.auto_key is not None:
            action[self.auto_key] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_human_debug(BalanceGame)
