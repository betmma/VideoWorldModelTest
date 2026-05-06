from __future__ import annotations

import bisect
import math
import os
import random
import sys
from dataclasses import dataclass

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    token: int
    radius: int
    expected_hit_chain: bool = True


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: int
    max_life: int
    color: tuple[int, int, int]
    radius: float


@dataclass
class ChainBall:
    distance: float
    token: int
    insert_t: float = 1.0
    insert_from_x: float = 0.0
    insert_from_y: float = 0.0
    auto_targeted: bool = False


@dataclass
class ChainBallView:
    index: int
    distance: float
    x: float
    y: float
    token: int


@dataclass
class MatchResolution:
    removed_count: int
    combo_count: int
    remaining_tokens: list[int]


@dataclass
class SlotCandidate:
    insert_index: int
    insert_distance: float
    x: float
    y: float
    token: int
    removed_count: int
    combo_count: int
    setup: bool = False


@dataclass
class ShotPlan:
    aim_angle: float
    token: int
    hits_chain: bool
    removed_count: int = 0
    combo_count: int = 0
    insert_distance: float = 0.0


class ZumaBase(GameBase):
    name = "Zuma"
    variantsPath = "zumas"
    moveInterval = 4

    def __init__(self, headless: bool = False) -> None:
        self.shooter_x = self.width * 0.5
        self.shooter_y = self.height * 0.57

        self.ball_radius = 15
        self.projectile_radius = 12
        self.ball_spacing = 28.0
        self.projectile_speed = 14.0
        self.rotation_speed = math.radians(3.8)
        self.track_margin = 70
        self.track_width = 34
        self.base_chain_speed = 1.1
        self.chain_close_speed = 3.4
        self.chain_push_speed = 5.0
        self.insert_anim_speed = 0.2
        self.end_screen_auto_reset = 160
        self.max_projectiles = 7
        self.tip_frames = 240
        self.hud_height = 46

        self.color_libraries: list[list[tuple[int, int, int]]] = [
            [(233, 88, 65), (246, 190, 59), (86, 182, 111), (75, 157, 236), (164, 103, 225), (236, 110, 167)],
            [(245, 119, 93), (255, 208, 93), (114, 204, 155), (95, 175, 255), (140, 121, 230), (255, 134, 163)],
            [(247, 99, 132), (250, 186, 73), (73, 203, 161), (88, 150, 250), (167, 117, 255), (255, 140, 92)],
        ]
        self.theme_presets = [
            {
                "bg_top": (18, 27, 48),
                "bg_bottom": (8, 14, 24),
                "fog": (68, 114, 168, 45),
                "panel": (16, 21, 36),
                "panel_text": (240, 242, 247),
                "track_shadow": (6, 8, 12, 110),
                "track_outer": (95, 77, 60),
                "track_inner": (174, 142, 98),
                "track_core": (216, 186, 130),
                "hole_outer": (26, 18, 15),
                "hole_inner": (9, 6, 5),
                "shooter_body": (102, 146, 112),
                "shooter_ring": (59, 88, 64),
                "shooter_eye": (247, 250, 245),
                "shooter_pupil": (34, 37, 28),
            },
            {
                "bg_top": (44, 18, 58),
                "bg_bottom": (20, 9, 25),
                "fog": (161, 88, 181, 40),
                "panel": (34, 15, 41),
                "panel_text": (247, 239, 250),
                "track_shadow": (8, 4, 10, 120),
                "track_outer": (78, 62, 89),
                "track_inner": (144, 108, 157),
                "track_core": (198, 153, 214),
                "hole_outer": (19, 11, 22),
                "hole_inner": (5, 3, 8),
                "shooter_body": (84, 104, 150),
                "shooter_ring": (48, 58, 86),
                "shooter_eye": (247, 247, 255),
                "shooter_pupil": (24, 26, 38),
            },
            {
                "bg_top": (14, 45, 44),
                "bg_bottom": (7, 20, 21),
                "fog": (48, 167, 145, 38),
                "panel": (10, 31, 33),
                "panel_text": (236, 248, 244),
                "track_shadow": (4, 9, 8, 110),
                "track_outer": (66, 90, 73),
                "track_inner": (118, 162, 131),
                "track_core": (168, 214, 174),
                "hole_outer": (10, 19, 15),
                "hole_inner": (4, 7, 6),
                "shooter_body": (118, 132, 81),
                "shooter_ring": (72, 77, 49),
                "shooter_eye": (252, 251, 240),
                "shooter_pupil": (46, 40, 24),
            },
        ]

        super().__init__(headless=headless)

        pygame.font.init()
        self.title_font = pygame.font.SysFont("consolas", 40, bold=True)
        self.hud_font = pygame.font.SysFont("consolas", 22, bold=True)
        self.body_font = pygame.font.SysFont("consolas", 20)
        self.small_font = pygame.font.SysFont("consolas", 18)

        self.best_score = 0
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

    def reset(self) -> None:
        self.frame_index = 0
        self.score = 0
        self.cleared_groups = 0
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.win = False
        self.game_over = False
        self.result_text = ""
        self.tip_timer = self.tip_frames
        self.combo_flash_frames = 0
        self.combo_label = ""
        self.combo_chain_count = 0
        self.swap_flash = 0
        self.shooter_recoil = 0.0
        self.next_shot_hits_chain = True
        self.prev_action = self.BLANK_ACTION.copy()

        self.projectiles: list[Projectile] = []
        self.particles: list[Particle] = []
        self.chain_balls: list[ChainBall] = []
        self.track_points: list[tuple[float, float]] = []
        self.track_lengths: list[float] = []
        self.track_total_length = 0.0
        self.exit_distance = 0.0

        self.theme = random.choice(self.theme_presets)
        self.background_surface = self._render_background_surface()

        self.chain_speed = self.base_chain_speed * random.uniform(0.95, 1.08)
        self._build_random_track()
        self.track_surface = self._render_track_surface()
        self.exit_distance = self.track_total_length - self.ball_radius * 1.65
        self._choose_shooter_position()

        self.active_colors = self._choose_active_colors()

        tokens = self._build_starting_chain_tokens()
        front_distance = random.uniform(350.0, 426.0)
        for index, token in enumerate(tokens):
            distance = front_distance - (len(tokens) - 1 - index) * self.ball_spacing
            self.chain_balls.append(ChainBall(distance=distance, token=token))

        anchor_distance = min(self.track_total_length * 0.22, max(48.0, front_distance + 34.0))
        anchor_pos, _ = self._sample_track(anchor_distance)
        self.shooter_angle = self._angle_to_point(anchor_pos[0], anchor_pos[1])

        self.loaded_token = self._random_ammo_token()
        self.reserve_token = self._random_ammo_token(exclude=self.loaded_token)
        self._on_round_reset()

    def _render_background_surface(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height))
        top = self.theme["bg_top"]
        bottom = self.theme["bg_bottom"]
        for y in range(self.height):
            t = y / (self.height - 1)
            color = (
                int(top[0] * (1.0 - t) + bottom[0] * t),
                int(top[1] * (1.0 - t) + bottom[1] * t),
                int(top[2] * (1.0 - t) + bottom[2] * t),
            )
            pygame.draw.line(surface, color, (0, y), (self.width, y))

        fog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        fog_color = self.theme["fog"]
        for _ in range(12):
            radius = random.randint(50, 150)
            cx = random.randint(-20, self.width + 20)
            cy = random.randint(-10, self.height + 10)
            pygame.draw.circle(fog_surface, fog_color, (cx, cy), radius)
        surface.blit(fog_surface, (0, 0))
        return surface

    def _render_track_surface(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self._paint_track_band(surface, self.theme["track_shadow"], self.track_width // 2 + 9)
        self._paint_track_band(surface, self.theme["track_outer"], self.track_width // 2 + 5)
        self._paint_track_band(surface, self.theme["track_inner"], self.track_width // 2 + 2)
        self._paint_track_band(surface, self.theme["track_core"], max(4, self.track_width // 2 - 5))

        marker_color = tuple(channel + 22 for channel in self.theme["track_core"])
        for distance in range(36, int(self.track_total_length), 118):
            (x, y), _ = self._sample_track(distance)
            pygame.draw.circle(surface, marker_color, (int(x), int(y)), 4)

        exit_x, exit_y = self.track_points[-1]
        pygame.draw.circle(surface, self.theme["hole_outer"], (int(exit_x), int(exit_y)), 28)
        pygame.draw.circle(surface, self.theme["hole_inner"], (int(exit_x), int(exit_y)), 16)
        return surface

    def _paint_track_band(
        self,
        surface: pygame.Surface,
        color: tuple[int, ...],
        radius: int,
    ) -> None:
        for x, y in self.track_points:
            pygame.draw.circle(surface, color, (int(x), int(y)), radius)

    def _build_random_track(self) -> None:
        builders = [
            self._build_spiral_track_controls,
            self._build_serpentine_track_controls,
            self._build_hook_track_controls,
        ]

        controls = random.choice(builders)()
        raw_points = self._catmull_rom_path(controls, steps_per_segment=28)
        deduped = self._dedupe_track_points(raw_points, min_step=2.0)
        resampled = self._resample_polyline(deduped, step=4.0)
        self.track_points = self._dedupe_track_points(resampled, min_step=3.0)
        self._rebuild_track_lengths()
        self._ensure_track_entry_offscreen()

    def _build_spiral_track_controls(self) -> list[tuple[float, float]]:
        quadrant_centers = [
            (self.width * 0.34, self.height * 0.36),
            (self.width * 0.67, self.height * 0.35),
            (self.width * 0.33, self.height * 0.68),
            (self.width * 0.67, self.height * 0.7),
        ]
        center_x, center_y = random.choice(quadrant_centers)
        center_x += random.uniform(-24.0, 24.0)
        center_y += random.uniform(-20.0, 20.0)
        direction = random.choice([-1.0, 1.0])
        start_angle = random.uniform(-math.pi, math.pi)
        turns = random.uniform(1.1, 1.75)
        anchor_count = random.randint(8, 10)
        outer_rx = random.uniform(210.0, 285.0)
        outer_ry = random.uniform(132.0, 188.0)
        inner_rx = random.uniform(82.0, 118.0)
        inner_ry = random.uniform(54.0, 86.0)
        wobble_phase = random.uniform(0.0, math.tau)
        wobble_amp = random.uniform(8.0, 22.0)

        anchors: list[tuple[float, float]] = []
        for index in range(anchor_count):
            t = index / (anchor_count - 1)
            angle = start_angle + direction * turns * math.tau * t
            rx = outer_rx + (inner_rx - outer_rx) * t
            ry = outer_ry + (inner_ry - outer_ry) * t
            wobble = math.sin(t * math.pi * 2.8 + wobble_phase) * wobble_amp * (1.0 - 0.42 * t)
            x = center_x + math.cos(angle) * (rx + wobble)
            y = center_y + math.sin(angle) * (ry - wobble * 0.24)
            anchors.append(self._clamp_track_point(x, y))

        return self._expand_track_endpoints(anchors, start_extension=170.0, end_extension=48.0)

    def _build_serpentine_track_controls(self) -> list[tuple[float, float]]:
        horizontal = random.random() < 0.6
        if horizontal:
            secondary_values = [
                random.uniform(92.0, 146.0),
                self.height - random.uniform(92.0, 136.0),
                random.uniform(self.height * 0.44, self.height * 0.62),
            ]
            secondary_values.extend([secondary_values[0] + 24.0, secondary_values[1] - 20.0])
            primary_values = [-150.0, 96.0, self.width * 0.33, self.width * 0.62, self.width - 110.0, self.width + 120.0]
            jitter = 24.0
        else:
            secondary_values = [
                random.uniform(94.0, 160.0),
                self.width - random.uniform(94.0, 160.0),
                random.uniform(self.width * 0.42, self.width * 0.58),
            ]
            secondary_values.extend([secondary_values[0] + 20.0, secondary_values[1] - 26.0])
            primary_values = [-140.0, 90.0, self.height * 0.32, self.height * 0.6, self.height - 110.0, self.height + 110.0]
            jitter = 28.0

        if random.random() < 0.5:
            secondary_values.reverse()

        return self._build_axis_serpentine_controls(primary_values, secondary_values, jitter=jitter, horizontal=horizontal)

    def _build_hook_track_controls(self) -> list[tuple[float, float]]:
        side = random.choice(["left", "right", "top", "bottom"])
        primary_extent = self.width if side in ("left", "right") else self.height
        lateral_extent = self.height if side in ("left", "right") else self.width
        anchors = [
            (-150.0, random.uniform(lateral_extent * 0.2, lateral_extent * 0.38)),
            (random.uniform(84.0, 92.0), random.uniform(110.0, 200.0)),
            (random.uniform(primary_extent * 0.7, primary_extent * 0.74), random.uniform(108.0, 180.0)),
            (primary_extent * 0.76, lateral_extent * 0.72),
            (primary_extent * 0.42, lateral_extent * 0.82),
            (primary_extent * 0.18, lateral_extent * 0.58),
        ]

        controls = [self._hook_side_point(anchors[0][0], anchors[0][1], side=side)]
        for primary, lateral in anchors[1:]:
            x, y = self._hook_side_point(primary, lateral, side=side)
            controls.append(self._clamp_track_point(x, y))
        return controls

    def _build_axis_serpentine_controls(
        self,
        primary_values: list[float],
        secondary_values: list[float],
        *,
        jitter: float,
        horizontal: bool,
    ) -> list[tuple[float, float]]:
        controls = [self._axis_track_point(primary_values[0], secondary_values[0], horizontal=horizontal, clamp=False)]
        for index, primary in enumerate(primary_values[1:-1]):
            secondary = secondary_values[index] + random.uniform(-jitter, jitter)
            controls.append(self._axis_track_point(primary, secondary, horizontal=horizontal, clamp=True))
        controls.append(self._axis_track_point(primary_values[-1], secondary_values[-2], horizontal=horizontal, clamp=False))
        return controls

    def _axis_track_point(
        self,
        primary: float,
        secondary: float,
        *,
        horizontal: bool,
        clamp: bool,
    ) -> tuple[float, float]:
        x, y = (primary, secondary) if horizontal else (secondary, primary)
        return self._clamp_track_point(x, y) if clamp else (x, y)

    def _hook_side_point(
        self,
        primary: float,
        lateral: float,
        *,
        side: str,
    ) -> tuple[float, float]:
        if side == "left":
            return primary, lateral
        if side == "right":
            return self.width - primary, lateral
        if side == "top":
            return lateral, primary
        return lateral, self.height - primary

    def _expand_track_endpoints(
        self,
        anchors: list[tuple[float, float]],
        start_extension: float,
        end_extension: float,
    ) -> list[tuple[float, float]]:
        start_dx = anchors[1][0] - anchors[0][0]
        start_dy = anchors[1][1] - anchors[0][1]
        start_len = math.hypot(start_dx, start_dy)
        entry = (
            anchors[0][0] - start_dx / start_len * start_extension,
            anchors[0][1] - start_dy / start_len * start_extension,
        )

        end_dx = anchors[-1][0] - anchors[-2][0]
        end_dy = anchors[-1][1] - anchors[-2][1]
        end_len = math.hypot(end_dx, end_dy)
        exit_point = (
            anchors[-1][0] + end_dx / end_len * end_extension,
            anchors[-1][1] + end_dy / end_len * end_extension,
        )

        return [entry] + anchors + [exit_point]

    def _ensure_track_entry_offscreen(self) -> None:
        offscreen_margin = self.track_width * 0.55 + self.ball_radius * 1.5

        def is_offscreen(point: tuple[float, float]) -> bool:
            return (
                point[0] < -offscreen_margin
                or point[0] > self.width + offscreen_margin
                or point[1] < -offscreen_margin
                or point[1] > self.height + offscreen_margin
            )

        start = self.track_points[0]
        if is_offscreen(start):
            return

        next_point = self.track_points[1]
        dx = next_point[0] - start[0]
        dy = next_point[1] - start[1]
        seg_len = math.hypot(dx, dy)
        ux = dx / seg_len
        uy = dy / seg_len

        extra_step = self.ball_spacing * 0.45
        distance = extra_step
        prepended: list[tuple[float, float]] = []
        while True:
            point = (start[0] - ux * distance, start[1] - uy * distance)
            prepended.append(point)
            if is_offscreen(point):
                break
            distance += extra_step
            if distance > max(self.width, self.height) + 420.0:
                break

        prepended.reverse()
        self.track_points = prepended + self.track_points
        self._rebuild_track_lengths()

    def _clamp_track_point(self, x: float, y: float) -> tuple[float, float]:
        return (
            max(self.track_margin, min(self.width - self.track_margin, x)),
            max(self.track_margin + 8, min(self.height - self.track_margin, y)),
        )

    def _choose_shooter_position(self) -> None:
        min_clearance = self.track_width * 0.5 + 30
        max_clearance = min_clearance * 3.5
        exit_x, exit_y = self.track_points[-1]
        candidates: list[tuple[float, float, float]] = []

        for _ in range(120):
            x = random.uniform(92.0, self.width - 92.0)
            y = random.uniform(108.0, self.height - 86.0)
            _, track_sq = self._nearest_track_distance(x, y)
            clearance = math.sqrt(track_sq)
            if clearance < min_clearance or clearance > max_clearance:
                continue
            if math.hypot(x - exit_x, y - exit_y) < 118.0:
                continue
            center_bonus = -math.hypot(x - self.width * 0.5, y - self.height * 0.58)
            score = clearance + center_bonus * 0.5 + random.uniform(0.0, 14.0)
            candidates.append((score, x, y))

        if not candidates:
            for gx in (0.18, 0.34, 0.5, 0.66, 0.82):
                for gy in (0.24, 0.42, 0.58, 0.74):
                    x = self.width * gx
                    y = self.height * gy
                    _, track_sq = self._nearest_track_distance(x, y)
                    clearance = math.sqrt(track_sq)
                    candidates.append((clearance, x, y))

        candidates.sort(reverse=True)
        top = candidates[:5]
        _, self.shooter_x, self.shooter_y = random.choice(top)

    @staticmethod
    def _catmull_rom_path(
        points: list[tuple[float, float]],
        steps_per_segment: int,
    ) -> list[tuple[float, float]]:
        padded = [points[0]] + points + [points[-1]]
        sampled: list[tuple[float, float]] = []
        for index in range(1, len(padded) - 2):
            p0, p1, p2, p3 = padded[index - 1], padded[index], padded[index + 1], padded[index + 2]
            for step in range(steps_per_segment):
                t = step / steps_per_segment
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * (
                    (2.0 * p1[0])
                    + (-p0[0] + p2[0]) * t
                    + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
                    + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
                )
                y = 0.5 * (
                    (2.0 * p1[1])
                    + (-p0[1] + p2[1]) * t
                    + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
                    + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
                )
                sampled.append((x, y))
        sampled.append(points[-1])
        return sampled

    @staticmethod
    def _dedupe_track_points(
        points: list[tuple[float, float]],
        min_step: float,
    ) -> list[tuple[float, float]]:
        deduped = [points[0]]
        for point in points[1:]:
            prev = deduped[-1]
            if math.hypot(point[0] - prev[0], point[1] - prev[1]) >= min_step:
                deduped.append(point)
        if len(deduped) == 1 and len(points) > 1:
            deduped.append(points[-1])
        return deduped

    @staticmethod
    def _resample_polyline(
        points: list[tuple[float, float]],
        step: float,
    ) -> list[tuple[float, float]]:
        lengths = [0.0]
        total = 0.0
        for index in range(1, len(points)):
            ax, ay = points[index - 1]
            bx, by = points[index]
            total += math.hypot(bx - ax, by - ay)
            lengths.append(total)

        sampled: list[tuple[float, float]] = []
        distance = 0.0
        while distance < total:
            segment_index = bisect.bisect_right(lengths, distance) - 1
            start_length = lengths[segment_index]
            end_length = lengths[segment_index + 1]
            segment_length = end_length - start_length
            t = (distance - start_length) / segment_length
            ax, ay = points[segment_index]
            bx, by = points[segment_index + 1]
            sampled.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            distance += step

        sampled.append(points[-1])
        return sampled

    def _rebuild_track_lengths(self) -> None:
        self.track_lengths = [0.0]
        total = 0.0
        for index in range(1, len(self.track_points)):
            ax, ay = self.track_points[index - 1]
            bx, by = self.track_points[index]
            total += math.hypot(bx - ax, by - ay)
            self.track_lengths.append(total)
        self.track_total_length = total

    def _autoplay_token_options(self) -> list[int]:
        return list(range(len(self.active_colors)))

    def _choose_active_colors(self) -> list[tuple[int, int, int]]:
        return random.sample(
            random.choice(self.color_libraries),
            random.randint(4, 5),
        )

    def _on_round_reset(self) -> None:
        return None

    def _starting_chain_token_candidates(self, tokens: list[int]) -> list[int]:
        insert_index = len(tokens)
        candidates = self._autoplay_token_options()
        random.shuffle(candidates)
        return [
            token
            for token in candidates
            if self._find_match_group(tokens + [token], insert_index) is None
        ]

    def _build_starting_chain_tokens(self) -> list[int]:
        count = random.randint(25, 31)
        tokens: list[int] = []
        candidate_stack: list[list[int]] = []

        while len(tokens) < count:
            depth = len(tokens)
            if depth == len(candidate_stack):
                candidate_stack.append(self._starting_chain_token_candidates(tokens))

            if candidate_stack[depth]:
                tokens.append(candidate_stack[depth].pop())
                continue

            candidate_stack.pop()
            if not tokens:
                raise RuntimeError("Unable to build a starting chain without immediate matches")
            tokens.pop()
        return tokens

    def _chain_token_list(self) -> list[int]:
        return [ball.token for ball in self.chain_balls]

    def _available_ammo_tokens(self) -> list[int]:
        choices = sorted(set(self._chain_token_list()))
        if not choices:
            return self._autoplay_token_options()
        return choices

    def _random_ammo_token(self, exclude: int | None = None) -> int:
        choices = self._available_ammo_tokens()
        if exclude is not None and len(choices) > 1:
            filtered = [choice for choice in choices if choice != exclude]
            if filtered:
                choices = filtered
        return random.choice(choices)

    def _ensure_ammo_tokens(self) -> None:
        if not self.chain_balls:
            return
        choices = set(self._available_ammo_tokens())
        if self.loaded_token not in choices:
            self.loaded_token = self._random_ammo_token()
        if self.reserve_token not in choices:
            self.reserve_token = self._random_ammo_token(exclude=self.loaded_token)

    def _sample_track(self, distance: float) -> tuple[tuple[float, float], float]:
        if distance <= 0.0:
            p0 = self.track_points[0]
            p1 = self.track_points[1]
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            seg_len = math.hypot(dx, dy)
            ux = dx / seg_len
            uy = dy / seg_len
            return (p0[0] + ux * distance, p0[1] + uy * distance), math.atan2(uy, ux)

        if distance >= self.track_total_length:
            p0 = self.track_points[-2]
            p1 = self.track_points[-1]
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            seg_len = math.hypot(dx, dy)
            ux = dx / seg_len
            uy = dy / seg_len
            extra = distance - self.track_total_length
            return (p1[0] + ux * extra, p1[1] + uy * extra), math.atan2(uy, ux)

        segment_index = bisect.bisect_right(self.track_lengths, distance) - 1
        start_length = self.track_lengths[segment_index]
        end_length = self.track_lengths[segment_index + 1]
        segment_length = end_length - start_length
        t = (distance - start_length) / segment_length

        ax, ay = self.track_points[segment_index]
        bx, by = self.track_points[segment_index + 1]
        return (ax + (bx - ax) * t, ay + (by - ay) * t), math.atan2(by - ay, bx - ax)

    def _nearest_track_distance(self, x: float, y: float) -> tuple[float, float]:
        best_distance = 0.0
        best_sq = math.inf

        for index in range(len(self.track_points) - 1):
            ax, ay = self.track_points[index]
            bx, by = self.track_points[index + 1]
            dx = bx - ax
            dy = by - ay
            seg_sq = dx * dx + dy * dy
            t = ((x - ax) * dx + (y - ay) * dy) / seg_sq
            t = max(0.0, min(1.0, t))
            px = ax + dx * t
            py = ay + dy * t
            dist_sq = (x - px) * (x - px) + (y - py) * (y - py)
            if dist_sq < best_sq:
                best_sq = dist_sq
                best_distance = self.track_lengths[index] + math.sqrt(seg_sq) * t

        return best_distance, best_sq

    def _angle_to_point(self, x: float, y: float) -> float:
        return math.atan2(y - self.shooter_y, x - self.shooter_x)

    @staticmethod
    def _wrap_angle(angle: float) -> float:
        return (angle + math.pi) % (math.tau) - math.pi

    def _chain_snapshot(self, chain_balls: list[ChainBall] | None = None) -> list[ChainBallView]:
        balls = self.chain_balls if chain_balls is None else chain_balls
        snapshot: list[ChainBallView] = []
        for index, ball in enumerate(balls):
            (track_x, track_y), _ = self._sample_track(ball.distance)
            if ball.insert_t < 1.0:
                draw_x = ball.insert_from_x + (track_x - ball.insert_from_x) * ball.insert_t
                draw_y = ball.insert_from_y + (track_y - ball.insert_from_y) * ball.insert_t
            else:
                draw_x = track_x
                draw_y = track_y
            snapshot.append(
                ChainBallView(
                    index=index,
                    distance=ball.distance,
                    x=draw_x,
                    y=draw_y,
                    token=ball.token,
                )
            )
        return snapshot

    def _is_on_screen(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            margin <= x <= self.width - margin
            and margin+self.hud_height <= y <= self.height - margin
        )

    def _press_actions(self, action: ActionState) -> ActionState:
        pressed = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action[key]:
                pressed[key] = True
        self.prev_action = action.copy()
        return pressed

    def _swap_ammo(self) -> None:
        if self.loaded_token == self.reserve_token and len(set(self._available_ammo_tokens())) < 2:
            return
        self.loaded_token, self.reserve_token = self.reserve_token, self.loaded_token
        self.swap_flash = 10

    def _make_projectile(
        self,
        token: int,
        angle: float,
        *,
        expected_hit_chain: bool = True,
    ) -> Projectile:
        muzzle_distance = 30.0
        return Projectile(
            self.shooter_x + math.cos(angle) * muzzle_distance,
            self.shooter_y + math.sin(angle) * muzzle_distance,
            math.cos(angle) * self.projectile_speed,
            math.sin(angle) * self.projectile_speed,
            token,
            self.projectile_radius,
            expected_hit_chain=expected_hit_chain,
        )

    def _has_pending_chain_shot(self) -> bool:
        if any(projectile.expected_hit_chain for projectile in self.projectiles):
            return True
        return any(ball.auto_targeted and ball.insert_t < 1.0 for ball in self.chain_balls) or len(self._segment_ranges()) > 1

    def _shoot(self) -> None:
        if len(self.projectiles) >= self.max_projectiles:
            return

        shot_token = self.loaded_token
        self.projectiles.append(
            self._make_projectile(
                shot_token,
                self.shooter_angle,
                expected_hit_chain=self.next_shot_hits_chain,
            )
        )
        self.next_shot_hits_chain = True
        self.shooter_recoil = 5.5
        self.loaded_token = self.reserve_token
        self.reserve_token = self._random_ammo_token(exclude=self.loaded_token)
        self.combo_chain_count = 0

    def _mark_end_state(self, text: str, win: bool) -> None:
        self.win = win
        self.game_over = not win
        self.result_text = text
        self.end_reported = True
        self.end_event_pending = True
        self.best_score = max(self.best_score, self.score)

    def _spawn_particles(self, x: float, y: float, color: tuple[int, int, int], count: int) -> None:
        for _ in range(count):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(1.4, 3.9)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed - random.uniform(0.2, 1.0),
                    life=random.randint(16, 28),
                    max_life=28,
                    color=color,
                    radius=random.uniform(2.2, 4.8),
                )
            )

    def _copy_chain_balls(self, chain_balls: list[ChainBall] | None = None) -> list[ChainBall]:
        source = self.chain_balls if chain_balls is None else chain_balls
        return [
            ChainBall(
                distance=ball.distance,
                token=ball.token,
                insert_t=ball.insert_t,
                insert_from_x=ball.insert_from_x,
                insert_from_y=ball.insert_from_y,
                auto_targeted=ball.auto_targeted,
            )
            for ball in source
        ]

    def _segment_ranges(self, chain_balls: list[ChainBall] | None = None) -> list[tuple[int, int]]:
        balls = self.chain_balls if chain_balls is None else chain_balls
        if not balls:
            return []

        segments: list[tuple[int, int]] = []
        start = 0
        for index in range(len(balls) - 1):
            gap = balls[index + 1].distance - balls[index].distance - self.ball_spacing
            if gap > 1.2:
                segments.append((start, index))
                start = index + 1
        segments.append((start, len(balls) - 1))
        return segments

    def _advance_chain_front(self, chain_balls: list[ChainBall] | None = None) -> None:
        balls = self.chain_balls if chain_balls is None else chain_balls
        segments = self._segment_ranges(balls)
        if len(segments) != 1:
            return

        for ball in balls:
            ball.distance += self.chain_speed

    def _push_chain_forward_overlaps(self, chain_balls: list[ChainBall] | None = None) -> None:
        balls = self.chain_balls if chain_balls is None else chain_balls
        for index in range(1, len(balls)):
            min_distance = balls[index - 1].distance + self.ball_spacing
            if balls[index].distance < min_distance:
                balls[index].distance = min(
                    min_distance,
                    balls[index].distance + self.chain_push_speed,
                )

    def _close_chain_gaps(self, chain_balls: list[ChainBall] | None = None) -> None:
        balls = self.chain_balls if chain_balls is None else chain_balls
        segments = self._segment_ranges(balls)
        if len(segments) <= 1:
            return

        # Each head-side segment retracts toward the segment behind it.
        # Rear segments stay put while the front closes the gap.
        for segment_index in range(1, len(segments)):
            prev_end = segments[segment_index - 1][1]
            start, end = segments[segment_index]
            gap = balls[start].distance - balls[prev_end].distance - self.ball_spacing
            if gap <= 0.0:
                continue

            retract = min(gap, self.chain_close_speed)
            for head_index in range(start, end + 1):
                balls[head_index].distance -= retract

    def _update_insert_animation(self) -> None:
        for ball in self.chain_balls:
            if ball.insert_t < 1.0:
                ball.insert_t = min(1.0, ball.insert_t + self.insert_anim_speed)
            if ball.insert_t >= 1.0:
                ball.auto_targeted = False

    @staticmethod
    def _group_bounds(tokens: list[int], center_index: int) -> tuple[int, int]:
        token = tokens[center_index]
        left = center_index
        right = center_index
        while left > 0 and tokens[left - 1] == token:
            left -= 1
        while right + 1 < len(tokens) and tokens[right + 1] == token:
            right += 1
        return left, right

    def _segment_for_index(
        self,
        chain_balls: list[ChainBall],
        index: int,
    ) -> tuple[int, int] | None:
        for start, end in self._segment_ranges(chain_balls):
            if start <= index <= end:
                return start, end
        return None

    @staticmethod
    def _segment_tokens(
        chain_balls: list[ChainBall],
        segment_start: int,
        segment_end: int,
    ) -> list[int]:
        return [ball.token for ball in chain_balls[segment_start : segment_end + 1]]

    def _find_match_group(self, tokens: list[int], focus_index: int | None) -> tuple[int, int] | None:
        if focus_index is not None and 0 <= focus_index < len(tokens):
            left, right = self._group_bounds(tokens, focus_index)
            if right - left + 1 >= 3:
                return left, right

        index = 0
        while index < len(tokens):
            left, right = self._group_bounds(tokens, index)
            if right - left + 1 >= 3:
                return left, right
            index = right + 1
        return None

    def _is_setup_after_insert(self, tokens: list[int], insert_index: int) -> bool:
        left, right = self._group_bounds(tokens, insert_index)
        return right - left + 1 == 2

    def _resolve_rule_chain(self, tokens: list[int], focus_index: int | None) -> MatchResolution:
        working = tokens[:]
        removed_count = 0
        combo_count = 0
        next_focus = focus_index

        while working:
            group = self._find_match_group(working, next_focus)
            if group is None:
                break

            left, right = group
            removed_count += right - left + 1
            combo_count += 1
            del working[left : right + 1]
            if not working:
                break
            next_focus = min(left, len(working) - 1)

        return MatchResolution(
            removed_count=removed_count,
            combo_count=combo_count,
            remaining_tokens=working,
        )

    def _clear_group(self, left: int, right: int) -> None:
        snapshot = self._chain_snapshot()
        removed = right - left + 1
        color = self._token_fill_color(self.chain_balls[left].token)
        for ball in snapshot[left : right + 1]:
            self._spawn_particles(ball.x, ball.y, color, 5)

        del self.chain_balls[left : right + 1]
        self.cleared_groups += 1
        self.combo_chain_count += 1
        self.score += removed * 12 * self.combo_chain_count
        self.best_score = max(self.best_score, self.score)
        self.combo_flash_frames = 20 + self.combo_chain_count * 6
        self.combo_label = f"{removed} clear" if self.combo_chain_count == 1 else f"{self.combo_chain_count}x chain"
        self._ensure_ammo_tokens()

        if not self.chain_balls:
            self._mark_end_state("Path Cleared", win=True)

    def _segment_match_group(
        self,
        chain_balls: list[ChainBall],
        segment_start: int,
        segment_end: int,
        focus_index: int | None,
    ) -> tuple[int, int] | None:
        tokens = self._segment_tokens(chain_balls, segment_start, segment_end)
        local_focus = None if focus_index is None else focus_index - segment_start
        match = self._find_match_group(tokens, local_focus)
        if match is None:
            return None
        left, right = match
        return segment_start + left, segment_start + right

    def _clear_matching_group(self, center_index: int | None = None) -> bool:
        segments = self._segment_ranges(self.chain_balls)
        if center_index is not None:
            segment = self._segment_for_index(self.chain_balls, center_index)
            match = self._segment_match_group(self.chain_balls, segment[0], segment[1], center_index)
            if match is None:
                return False
            self._clear_group(match[0], match[1])
            return True

        for start, end in segments:
            match = self._segment_match_group(self.chain_balls, start, end, None)
            if match is not None:
                self._clear_group(match[0], match[1])
                return True
        return False

    def _advance_chain_state(self, chain_balls: list[ChainBall]) -> None:
        self._advance_chain_front(chain_balls)
        self._push_chain_forward_overlaps(chain_balls)
        self._close_chain_gaps(chain_balls)

    def _slot_line_blocked(
        self,
        slot_x: float,
        slot_y: float,
        snapshot: list[ChainBallView],
        insert_index: int,
    ) -> bool:
        angle = self._angle_to_point(slot_x, slot_y)
        distance = math.hypot(slot_x - self.shooter_x, slot_y - self.shooter_y)
        for ball in snapshot:
            if insert_index-1 <= ball.index <= insert_index:
                continue
            angle2=self._angle_to_point(ball.x, ball.y)
            distance2=math.hypot(ball.x - self.shooter_x, ball.y - self.shooter_y)
            if distance2 >= distance:
                continue
            if abs(self._wrap_angle(angle2 - angle)) < math.asin(self.ball_radius / distance2)*1.5:
                return True
        return False

    def _evaluate_slot_candidate(
        self,
        insert_index: int,
        insert_distance: float,
        slot_x: float,
        slot_y: float,
        token: int,
    ) -> SlotCandidate | None:
        chain_balls = self._copy_chain_balls()
        chain_balls.insert(insert_index, ChainBall(distance=insert_distance, token=token))
        self._push_chain_forward_overlaps(chain_balls)

        segment = self._segment_for_index(chain_balls, insert_index)
        segment_tokens = self._segment_tokens(chain_balls, segment[0], segment[1])
        local_focus = insert_index - segment[0]
        resolution = self._resolve_rule_chain(segment_tokens, local_focus)
        if resolution.combo_count > 0:
            return SlotCandidate(
                insert_index=insert_index,
                insert_distance=insert_distance,
                x=slot_x,
                y=slot_y,
                token=token,
                removed_count=resolution.removed_count,
                combo_count=resolution.combo_count,
            )
        if self._is_setup_after_insert(segment_tokens, local_focus):
            return SlotCandidate(
                insert_index=insert_index,
                insert_distance=insert_distance,
                x=slot_x,
                y=slot_y,
                token=token,
                removed_count=0,
                combo_count=0,
                setup=True,
            )
        return None

    def _enumerate_slot_candidates(self) -> list[SlotCandidate]:
        snapshot = [
            ball
            for ball in self._chain_snapshot()
            if self._is_on_screen(ball.x, ball.y, margin=self.ball_radius)
        ]
        candidates: list[SlotCandidate] = []
        for insert_index in range(len(self.chain_balls) + 1):
            insert_distance = self._insert_distance_for_slot(insert_index)
            (slot_x, slot_y), _ = self._sample_track(insert_distance)
            if not self._is_on_screen(slot_x, slot_y, margin=self.ball_radius):
                continue
            if self._slot_line_blocked(slot_x, slot_y, snapshot, insert_index):
                continue

            for token in self._autoplay_token_options():
                candidate = self._evaluate_slot_candidate(insert_index, insert_distance, slot_x, slot_y, token)
                if candidate is not None:
                    candidates.append(candidate)
        candidates.sort(
            key=lambda candidate: (
                -candidate.combo_count,
                abs(self._wrap_angle(self._angle_to_point(candidate.x, candidate.y) - self.shooter_angle)),
                -candidate.removed_count,
                -candidate.insert_distance,
            )
        )
        return candidates

    def _predict_future_slot_geometry(
        self,
        insert_index: int,
        travel_time: float,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        future_distance = self._insert_distance_for_slot(insert_index) + self.chain_speed * travel_time
        future_slot_point, angle = self._sample_track(future_distance)
        angle=angle+math.pi/2*(math.sin(angle-self._angle_to_point(future_slot_point[0], future_slot_point[1]))>0 and 1 or -1)
        future_slot_point = (
            future_slot_point[0] + math.cos(angle) * (self.ball_radius+self.projectile_radius)*0.8,
            future_slot_point[1] + math.sin(angle) * (self.ball_radius+self.projectile_radius)*0.8,
        )
        front_distance = self.chain_balls[-1].distance + self.chain_speed * travel_time
        future_front_point = self._sample_track(front_distance)[0]
        return future_slot_point, future_front_point

    def _front_ball_blocks_target(
        self,
        aim_angle: float,
        target_point: tuple[float, float],
        front_point: tuple[float, float],
    ) -> bool:
        ux = math.cos(aim_angle)
        uy = math.sin(aim_angle)
        target_dx = target_point[0] - self.shooter_x
        target_dy = target_point[1] - self.shooter_y
        target_proj = target_dx * ux + target_dy * uy
        if target_proj <= self.projectile_radius:
            return False

        dx = front_point[0] - self.shooter_x
        dy = front_point[1] - self.shooter_y
        proj = dx * ux + dy * uy
        if proj <= self.projectile_radius or proj >= target_proj:
            return False

        perp = abs(-uy * dx + ux * dy)
        return perp <= self.ball_radius + self.projectile_radius - 1

    def _plan_chain_shot(self, candidate: SlotCandidate) -> ShotPlan | None:
        current_distance = math.hypot(candidate.x - self.shooter_x, candidate.y - self.shooter_y)
        travel_time = current_distance / self.projectile_speed
        future_slot_point, future_front_point = self._predict_future_slot_geometry(candidate.insert_index, travel_time)
        aim_angle = self._angle_to_point(future_slot_point[0], future_slot_point[1])
        if self._front_ball_blocks_target(aim_angle, future_slot_point, future_front_point):
            return None

        return ShotPlan(
            aim_angle=aim_angle,
            token=candidate.token,
            hits_chain=True,
            removed_count=candidate.removed_count,
            combo_count=candidate.combo_count,
            insert_distance=candidate.insert_distance,
        )

    def _best_discard_plan(self) -> ShotPlan | None:
        snapshot = [
            ball
            for ball in self._chain_snapshot()
            if self._is_on_screen(ball.x, ball.y, margin=self.ball_radius)
        ]
        if not snapshot:
            return ShotPlan(
                aim_angle=self.shooter_angle,
                token=self.loaded_token,
                hits_chain=False,
            )

        safety_radius = self.ball_radius*6
        last_angle=None
        interval=None
        for ball in snapshot:
            dx = ball.x - self.shooter_x
            dy = ball.y - self.shooter_y
            distance = math.hypot(dx, dy)
            if distance <= safety_radius:
                return None
            angle = self._wrap_angle(self._angle_to_point(ball.x, ball.y)-self.shooter_angle)
            spread = math.asin(safety_radius / distance)
            if last_angle is None:
                interval=[angle-spread, angle+spread]
            else:
                angle=self._wrap_angle(angle-last_angle)+last_angle
                interval[0]=min(interval[0], angle-spread)
                interval[1]=max(interval[1], angle+spread)
            last_angle=angle
        if interval[1]>math.tau:
            interval=[i-math.tau for i in interval]
        if interval[0]<-math.tau:
            interval=[i+math.tau for i in interval]
        if interval[0]<0<interval[1]:
            return ShotPlan(
                aim_angle=(interval[0]if abs(interval[0])<abs(interval[1]) else interval[1])+self.shooter_angle,
                token=self.loaded_token,
                hits_chain=False,
            )
        return ShotPlan(
            aim_angle=self.shooter_angle,
            token=self.loaded_token,
            hits_chain=False,
        )

    def _insert_distance_for_slot(
        self,
        insert_index: int,
        chain_balls: list[ChainBall] | None = None,
    ) -> float:
        balls = self.chain_balls if chain_balls is None else chain_balls
        if insert_index <= 0:
            return balls[0].distance - self.ball_spacing * 0.5
        if insert_index >= len(balls):
            return balls[-1].distance + self.ball_spacing * 0.5
        return (balls[insert_index - 1].distance + balls[insert_index].distance) * 0.5

    def _advance_projectile(self, projectile: Projectile) -> bool:
        projectile.x += projectile.vx
        projectile.y += projectile.vy
        return (
            -40 <= projectile.x <= self.width + 40
            and -40 <= projectile.y <= self.height + 40
        )

    def _projectile_impact(
        self,
        projectile: Projectile,
        chain_balls: list[ChainBall] | None = None,
    ) -> tuple[int, float] | None:
        balls = self.chain_balls if chain_balls is None else chain_balls
        snapshot = self._chain_snapshot(balls)
        hit_ball: ChainBallView | None = None
        hit_sq = math.inf
        collision_radius = self.ball_radius + projectile.radius - 1

        for ball in snapshot:
            dx = projectile.x - ball.x
            dy = projectile.y - ball.y
            dist_sq = dx * dx + dy * dy
            if dist_sq <= collision_radius * collision_radius and dist_sq < hit_sq:
                hit_ball = ball
                hit_sq = dist_sq

        if hit_ball is None:
            return None

        hit_distance, track_dist_sq = self._nearest_track_distance(projectile.x, projectile.y)
        if track_dist_sq > (self.ball_radius * 1.7) ** 2:
            return None

        insert_index = hit_ball.index if hit_distance < hit_ball.distance else hit_ball.index + 1
        insert_distance = self._insert_distance_for_slot(insert_index, chain_balls=balls)
        return insert_index, insert_distance

    def _update_projectiles(self) -> None:
        index = 0
        while index < len(self.projectiles):
            projectile = self.projectiles[index]
            if not self._advance_projectile(projectile):
                self.projectiles.pop(index)
                continue

            impact = self._projectile_impact(projectile)
            if impact is None:
                index += 1
                continue

            insert_index, insert_distance = impact
            self.chain_balls.insert(
                insert_index,
                ChainBall(
                    distance=insert_distance,
                    token=projectile.token,
                    insert_t=0.0,
                    insert_from_x=projectile.x,
                    insert_from_y=projectile.y,
                    auto_targeted=projectile.expected_hit_chain,
                ),
            )
            self._spawn_particles(projectile.x, projectile.y, self._token_fill_color(projectile.token), 6)
            self.projectiles.pop(index)
            self._push_chain_forward_overlaps()
            self._clear_matching_group(insert_index)
            self._ensure_ammo_tokens()
            continue

    def _update_particles(self) -> None:
        index = 0
        while index < len(self.particles):
            particle = self.particles[index]
            particle.x += particle.vx
            particle.y += particle.vy
            particle.vx *= 0.96
            particle.vy = particle.vy * 0.96 + 0.08
            particle.life -= 1
            if particle.life <= 0:
                self.particles.pop(index)
                continue
            index += 1

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1
        if self.tip_timer > 0:
            self.tip_timer -= 1
        if self.combo_flash_frames > 0:
            self.combo_flash_frames -= 1
        if self.swap_flash > 0:
            self.swap_flash -= 1
        self.shooter_recoil *= 0.78

        pressed_action = self._press_actions(action)

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        self._update_particles()

        if self.win or self.game_over:
            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        if action["A"] or action["LL"]:
            self.shooter_angle -= self.rotation_speed
        if action["D"] or action["LR"]:
            self.shooter_angle += self.rotation_speed
        self.shooter_angle = self._wrap_angle(self.shooter_angle)

        if pressed_action["S"] or pressed_action["LD"]:
            self._swap_ammo()

        if pressed_action["W"] or pressed_action["LU"]:
            self._shoot()

        self._advance_chain_front()
        self._update_projectiles()
        self._push_chain_forward_overlaps()
        self._close_chain_gaps()
        self._update_insert_animation()

        if self.chain_balls and self.chain_balls[-1].distance >= self.exit_distance:
            self._mark_end_state("Track Breached", win=False)
            return False

        if self.chain_balls:
            self._clear_matching_group()

        return False

    def _token_fill_color(self, token: int) -> tuple[int, int, int]:
        return self.active_colors[token]

    def _draw_ball_overlay(self, x: float, y: float, radius: float, token: int) -> None:
        return None

    def _draw_hud_rule(self, hud_color: tuple[int, int, int]) -> None:
        return None

    @staticmethod
    def _scale_color(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
        return (
            max(0, min(255, int(color[0] * factor))),
            max(0, min(255, int(color[1] * factor))),
            max(0, min(255, int(color[2] * factor))),
        )

    def _draw_ball(self, x: float, y: float, radius: float, token: int, rim: bool = True) -> None:
        color = self._token_fill_color(token)
        rim_color = self._scale_color(color, 0.56)
        highlight = self._scale_color(color, 1.18)
        pygame.draw.circle(self.screen, rim_color, (int(x + 2), int(y + 2)), int(radius))
        pygame.draw.circle(self.screen, color, (int(x), int(y)), int(radius))
        pygame.draw.circle(self.screen, highlight, (int(x - radius * 0.32), int(y - radius * 0.34)), int(radius * 0.34))
        if rim:
            pygame.draw.circle(self.screen, self._scale_color(color, 0.42), (int(x), int(y)), int(radius), 2)
        self._draw_ball_overlay(x, y, radius, token)

    def _draw_chain(self) -> None:
        for ball in self._chain_snapshot():
            pulse = 1.0 + math.sin(self.frame_index * 0.18 + ball.distance * 0.05) * 0.04
            self._draw_ball(ball.x, ball.y, self.ball_radius * pulse, ball.token)

    def _draw_projectiles(self) -> None:
        for projectile in self.projectiles:
            self._draw_ball(projectile.x, projectile.y, projectile.radius, projectile.token, rim=False)

    def _draw_particles(self) -> None:
        for particle in self.particles:
            alpha = int(255 * particle.life / particle.max_life)
            surface = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.circle(
                surface,
                (*particle.color, alpha),
                (8, 8),
                int(particle.radius),
            )
            self.screen.blit(surface, (particle.x - 8, particle.y - 8))

    def _draw_shooter(self) -> None:
        base_x = self.shooter_x - math.cos(self.shooter_angle) * self.shooter_recoil
        base_y = self.shooter_y - math.sin(self.shooter_angle) * self.shooter_recoil

        shadow_surface = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surface, (0, 0, 0, 70), pygame.Rect(14, 72, 92, 26))
        self.screen.blit(shadow_surface, (base_x - 60, base_y - 60))

        turret_len = 38
        mouth_x = base_x + math.cos(self.shooter_angle) * turret_len
        mouth_y = base_y + math.sin(self.shooter_angle) * turret_len

        pygame.draw.line(
            self.screen,
            self.theme["shooter_ring"],
            (int(base_x), int(base_y)),
            (int(mouth_x), int(mouth_y)),
            18,
        )
        pygame.draw.circle(self.screen, self.theme["shooter_body"], (int(base_x), int(base_y)), 34)
        pygame.draw.circle(self.screen, self.theme["shooter_ring"], (int(base_x), int(base_y)), 34, 5)

        eye_offset_x = math.cos(self.shooter_angle + math.pi / 2.0) * 12.0
        eye_offset_y = math.sin(self.shooter_angle + math.pi / 2.0) * 12.0
        for direction in (-1.0, 1.0):
            ex = base_x + eye_offset_x * direction - math.cos(self.shooter_angle) * 5.0
            ey = base_y + eye_offset_y * direction - math.sin(self.shooter_angle) * 5.0
            pygame.draw.circle(self.screen, self.theme["shooter_eye"], (int(ex), int(ey)), 7)
            pygame.draw.circle(
                self.screen,
                self.theme["shooter_pupil"],
                (int(ex + math.cos(self.shooter_angle) * 2.0), int(ey + math.sin(self.shooter_angle) * 2.0)),
                3,
            )

        pygame.draw.circle(
            self.screen,
            self._scale_color(self.theme["shooter_ring"], 0.72),
            (int(mouth_x), int(mouth_y)),
            12,
        )

        self._draw_ball(mouth_x, mouth_y, self.projectile_radius + 1, self.loaded_token)

        reserve_angle = self.shooter_angle + math.pi * 0.8
        reserve_distance = 42.0
        reserve_x = base_x + math.cos(reserve_angle) * reserve_distance
        reserve_y = base_y + math.sin(reserve_angle) * reserve_distance
        reserve_ring = 2 + (1 if self.swap_flash > 0 else 0)
        pygame.draw.circle(self.screen, (242, 244, 248), (int(reserve_x), int(reserve_y)), self.projectile_radius + 5, reserve_ring)
        self._draw_ball(reserve_x, reserve_y, self.projectile_radius - 2, self.reserve_token, rim=False)

    def _draw_hud(self) -> None:
        panel = pygame.Rect(0, 0, self.width, self.hud_height)
        pygame.draw.rect(self.screen, self.theme["panel"], panel)
        pygame.draw.line(self.screen, (255, 255, 255, 30), (0, self.hud_height), (self.width, self.hud_height), 1)

        remaining = len(self.chain_balls)
        hud_color = self.theme["panel_text"]
        left_text = self.hud_font.render(
            f"{self.name}   Score {self.score}   Best {self.best_score}",
            True,
            hud_color,
        )
        right_text = self.hud_font.render(
            f"Balls {remaining}   Groups {self.cleared_groups}",
            True,
            hud_color,
        )
        self.screen.blit(left_text, (14, 11))
        self.screen.blit(right_text, right_text.get_rect(topright=(self.width - 14, 11)))

        bar_w = 180
        bar_h = 10
        bar_x = self.width - bar_w - 18
        bar_y = 54
        pygame.draw.rect(self.screen, (20, 20, 24), pygame.Rect(bar_x, bar_y, bar_w, bar_h), border_radius=5)
        front_distance = self.chain_balls[-1].distance if self.chain_balls else 0.0
        pressure = front_distance / self.exit_distance
        fill_color = (90, 205, 132) if pressure < 0.6 else (246, 186, 78) if pressure < 0.84 else (234, 91, 91)
        pygame.draw.rect(
            self.screen,
            fill_color,
            pygame.Rect(bar_x, bar_y, int(bar_w * pressure), bar_h),
            border_radius=5,
        )

        pressure_text = self.small_font.render("Track Pressure", True, hud_color)
        self.screen.blit(pressure_text, (bar_x, bar_y + 19))
        self._draw_hud_rule(hud_color)

        if self.combo_flash_frames > 0:
            combo = self.body_font.render(self.combo_label, True, (255, 244, 214))
            self.screen.blit(combo, combo.get_rect(center=(self.width // 2, 72)))

        if self.tip_timer > 0 and not (self.win or self.game_over):
            tip = self.small_font.render(
                "A/D rotate   W shoot   S swap   Arrow keys mirror the same controls",
                True,
                (232, 235, 240),
            )
            self.screen.blit(tip, tip.get_rect(center=(self.width // 2, self.height - 24)))

    def draw(self) -> None:
        self.screen.blit(self.background_surface, (0, 0))
        self.screen.blit(self.track_surface, (0, 0))

        exit_x, exit_y = self.track_points[-1]
        pulse = 18 + int(3 * math.sin(self.frame_index * 0.18))
        glow = pygame.Surface((90, 90), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 120, 90, 45), (45, 45), pulse)
        self.screen.blit(glow, (exit_x - 45, exit_y - 45))

        self._draw_particles()
        self._draw_chain()
        self._draw_projectiles()
        self._draw_shooter()
        self._draw_hud()

        if self.win or self.game_over:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 132))
            self.screen.blit(overlay, (0, 0))

            title_color = (122, 245, 146) if self.win else (245, 113, 113)
            title = self.title_font.render(self.result_text, True, title_color)
            detail = self.body_font.render(
                f"Score {self.score}   Groups {self.cleared_groups}",
                True,
                (240, 242, 246),
            )
            restart = self.small_font.render(
                "Press A / Left Arrow to restart",
                True,
                (238, 238, 244),
            )

            self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 34)))
            self.screen.blit(detail, detail.get_rect(center=(self.width // 2, self.height // 2 + 6)))
            self.screen.blit(restart, restart.get_rect(center=(self.width // 2, self.height // 2 + 40)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. A or Left rotates the stone frog left, and D or Right rotates it right. "
            "Press W or Up Arrow to shoot the loaded colored ball into the moving chain. Press S or Down Arrow to swap the loaded ball with the reserve ball. If three or more adjacent touching balls of the same color meet, they disappear and can trigger chain reactions after the gap closes. Clear the whole chain before the front reaches the tunnel at the end of the track. After winning or losing, press A or Left Arrow to restart on a newly generated random track."
        )

    def getAutoAction(self, frame_index: int) -> ActionState:
        action = self.BLANK_ACTION.copy()
        self.next_shot_hits_chain = True

        if self.win or self.game_over:
            if frame_index % self.moveInterval == 0 and random.random() < 0.18:
                action["A"] = True
            return action

        if not self.chain_balls:
            return action

        if self._has_pending_chain_shot():
            return action

        self._ensure_ammo_tokens()
        slot_candidates = self._enumerate_slot_candidates()
        current_plan: ShotPlan | None = None
        reserve_plan: ShotPlan | None = None
        current_rank: int | None = None
        reserve_rank: int | None = None

        for rank, candidate in enumerate(slot_candidates):
            if current_plan is None and candidate.token == self.loaded_token:
                plan = self._plan_chain_shot(candidate)
                if plan is not None:
                    current_plan = plan
                    current_rank = rank
            if reserve_plan is None and candidate.token == self.reserve_token:
                plan = self._plan_chain_shot(candidate)
                if plan is not None:
                    reserve_plan = plan
                    reserve_rank = rank
            if current_plan is not None and reserve_plan is not None:
                break

        use_swap = (
            reserve_plan is not None
            and self.reserve_token != self.loaded_token
            and (current_plan is None or reserve_rank < current_rank)
        )
        plan = reserve_plan if use_swap else current_plan

        if use_swap:
            if frame_index % self.moveInterval == 0:
                action["S"] = True
            return action

        if plan is None:
            plan = self._best_discard_plan()
            if plan is None:
                return action

        target_angle = plan.aim_angle
        angle_diff = self._wrap_angle(target_angle - self.shooter_angle)

        if abs(angle_diff) > 0.038:
            if angle_diff < 0.0:
                action["A"] = True
            else:
                action["D"] = True

        if frame_index % self.moveInterval != 0:
            return action

        if abs(angle_diff) < 0.035 and len(self.projectiles) < self.max_projectiles:
            self.next_shot_hits_chain = plan.hits_chain
            action["W"] = True

        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(ZumaBase)
