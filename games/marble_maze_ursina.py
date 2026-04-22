from __future__ import annotations

import colorsys
import math
import os
import random
import sys
from collections import deque

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ursina import (
    AmbientLight,
    DirectionalLight,
    Entity,
    Vec3,
    camera,
    color,
    destroy,
    window,
)
from ursina.shaders import lit_with_shadows_shader

from engineBase import ActionState
from ursinaBase import UrsinaGameBase


CELL = 1.0
WALL_H = 0.6
BOARD_THICK = 0.1
BALL_R = 0.22
GRAVITY = 36.0
FRICTION = 0.985
ELASTICITY = 0.35
MAX_TILT = 25.0
TILT_SPEED = 16.0
TILT_RETURN = 0.0
FPS = 30
FALL_SPEED = 6.0
FALL_RESPAWN_Y = -3.0

SPEED_BAR_X = -0.7
SPEED_BAR_Y = 0.43
SPEED_BAR_W = 0.3
SPEED_BAR_H = 0.03
SPEED_BAR_MAX = 9.0

TRAIL_COUNT = 12

LIVES_MAX = 3
LIVES_X = 0.55
LIVES_Y = 0.43
LIVES_SIZE = 0.045
LIVES_SPACING = 0.08


class MarbleMazeUrsina(UrsinaGameBase):
    name = "Marble Maze 3D"
    variantsPath = "marble_mazes"
    background_color = color.rgba32(18, 20, 28)

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

        camera.position = Vec3(0, 14, -4)
        camera.look_at(Vec3(0, 0, 0))
        camera.fov = 70
        if getattr(self.app, "win", None) is not None:
            self.app.win.setClearColor(self.background_color)

        self._sun = DirectionalLight(shadow_map_resolution=(2048, 2048))
        self._sun.look_at(Vec3(1, -2, 1))
        self._ambient = AmbientLight(color=color.rgba32(150, 150, 165, 255))

        self._entities: list[Entity] = []
        self._board: Entity | None = None
        self._marble: Entity | None = None
        self._trail_entities: list[Entity] = []

        self._speed_bar_bg = Entity(
            parent=camera.ui,
            model="quad",
            color=color.rgba32(20, 20, 28, 220),
            position=Vec3(SPEED_BAR_X, SPEED_BAR_Y, 0),
            scale=Vec3(SPEED_BAR_W, SPEED_BAR_H, 1),
        )
        self._speed_bar_fill = Entity(
            parent=camera.ui,
            model="quad",
            color=color.rgba32(220, 180, 60, 255),
            position=Vec3(SPEED_BAR_X - SPEED_BAR_W / 2, SPEED_BAR_Y, -0.01),
            scale=Vec3(1e-4, SPEED_BAR_H * 0.75, 1),
        )

        self._life_icons: list[Entity] = []
        for i in range(LIVES_MAX):
            icon = Entity(
                parent=camera.ui,
                model="circle",
                color=color.rgba32(230, 90, 90, 255),
                position=Vec3(LIVES_X + i * LIVES_SPACING, LIVES_Y, 0),
                scale=LIVES_SIZE,
            )
            self._life_icons.append(icon)

        self.lives = LIVES_MAX

        self.reset()

    def reset(self) -> None:
        for entity in self._entities:
            destroy(entity)
        self._entities.clear()
        self._board = None
        self._marble = None
        self._trail_entities = []

        self.tilt_x = 0.0
        self.tilt_z = 0.0
        self.ball_r = 0.0
        self.ball_c = 0.0
        self.ball_y = BALL_R
        self.vr = 0.0
        self.vc = 0.0
        self.falling = False

        self.win = False
        self.win_frames = 0
        self.frame_index = 0
        self.end_reported = False
        self.end_event_pending = False

        self.grid: list[list[str]] = []
        self.grid_h = 0
        self.grid_w = 0
        self.start_r = 1.0
        self.start_c = 1.0
        self.goal_cell = (0, 0)
        self._auto_path: list[tuple[int, int]] = []

        self.wall_color = self._pick_vivid_color()
        self.marble_color = self._pick_vivid_color()

        self._create_level()
        self._rebuild_auto_path()
        self._build_scene()

        self.ball_r = self.start_r
        self.ball_c = self.start_c

        self.lives = LIVES_MAX
        self._refresh_life_icons()

    def _create_level(self) -> None:
        w, h = 15, 11
        self.grid_w, self.grid_h = w, h
        self.grid = self._generate_maze(w, h)
        self.start_r, self.start_c = 1.5, 1.5

    def _respawn_ball(self) -> None:
        # Each respawn consumes one life. When none remain, swap to a new map
        # instead of respawning on the same one.
        self.lives -= 1
        if self.lives <= 0:
            self.reset()
            return
        self._refresh_life_icons()
        self.ball_r = self.start_r
        self.ball_c = self.start_c
        self.ball_y = BALL_R
        self.vr = 0.0
        self.vc = 0.0
        self.tilt_x = 0.0
        self.tilt_z = 0.0
        self.falling = False
        if self._board:
            self._board.rotation_x = 0.0
            self._board.rotation_z = 0.0
        if self._trail_entities:
            new_pos = Vec3(
                (self.ball_c - self.grid_w / 2) * CELL,
                self.ball_y,
                (self.ball_r - self.grid_h / 2) * CELL,
            )
            for trail in self._trail_entities:
                trail.position = new_pos

    def _refresh_life_icons(self) -> None:
        has_holes = any("H" in row for row in self.grid)
        for i, icon in enumerate(self._life_icons):
            icon.visible = has_holes and (i < self.lives)

    def _is_hole_cell(self, r: int, c: int) -> bool:
        return 0 <= r < self.grid_h and 0 <= c < self.grid_w and self.grid[r][c] == "H"

    @staticmethod
    def _pick_vivid_color():
        h = random.random()
        l = random.uniform(0.5, 0.7)
        s = random.uniform(0.25, 0.5)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return color.rgba32(int(r * 255), int(g * 255), int(b * 255))

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1
        dt = 1.0 / FPS

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.win:
            self.win_frames += 1
            if self.win_frames > 90 or action["A"]:
                self.reset()
            return False

        if action["W"] or action["LU"]:
            self.tilt_x = min(MAX_TILT, self.tilt_x + TILT_SPEED * dt)
        elif action["S"] or action["LD"]:
            self.tilt_x = max(-MAX_TILT, self.tilt_x - TILT_SPEED * dt)
        else:
            self.tilt_x -= math.copysign(min(abs(self.tilt_x), TILT_RETURN * dt), self.tilt_x)

        if action["D"] or action["LR"]:
            self.tilt_z = min(MAX_TILT, self.tilt_z + TILT_SPEED * dt)
        elif action["A"] or action["LL"]:
            self.tilt_z = max(-MAX_TILT, self.tilt_z - TILT_SPEED * dt)
        else:
            self.tilt_z -= math.copysign(min(abs(self.tilt_z), TILT_RETURN * dt), self.tilt_z)

        if self._board:
            self._board.rotation_x = self.tilt_x
            self._board.rotation_z = self.tilt_z

        ax = GRAVITY * math.sin(math.radians(self.tilt_x))
        ac = GRAVITY * math.sin(math.radians(self.tilt_z))

        self.vr += ax * dt
        self.vc += ac * dt
        self.vr *= FRICTION
        self.vc *= FRICTION

        for _ in range(4):
            self.ball_r += self.vr * dt / 4
            self._resolve_collision_axis("r")
            self.ball_c += self.vc * dt / 4
            self._resolve_collision_axis("c")

        if self.falling:
            self.ball_y -= FALL_SPEED * dt
            if self._marble:
                self._marble.position = Vec3(
                    (self.ball_c - self.grid_w / 2) * CELL,
                    self.ball_y,
                    (self.ball_r - self.grid_h / 2) * CELL,
                )
            if self.ball_y <= FALL_RESPAWN_Y:
                self._respawn_ball()
                if self._marble:
                    self._marble.position = Vec3(
                        (self.ball_c - self.grid_w / 2) * CELL,
                        self.ball_y,
                        (self.ball_r - self.grid_h / 2) * CELL,
                    )
            return False
        
        if self._marble:
            self._marble.position = Vec3(
                (self.ball_c - self.grid_w / 2) * CELL,
                self.ball_y,
                (self.ball_r - self.grid_h / 2) * CELL,
            )

        if self._is_hole_cell(int(self.ball_r), int(self.ball_c)) and ((self.ball_r%1-0.5)**2+(self.ball_c%1-0.5)**2)**0.5 < 0.5:
            self.falling = True
            return False

        r, c = int(self.ball_r), int(self.ball_c)
        if 0 <= r < self.grid_h and 0 <= c < self.grid_w and self.grid[r][c] == "G" and not self.win:
            self.win = True
            self.end_reported = True
            self.end_event_pending = True
            if self._marble:
                self._marble.color = color.lime

        return False

    def draw(self) -> None:
        if self._marble is not None and self._trail_entities:
            for i in range(len(self._trail_entities) - 1, 0, -1):
                self._trail_entities[i].position = self._trail_entities[i - 1].position
            self._trail_entities[0].position = self._marble.position

        if self._speed_bar_fill is None:
            return
        speed = math.sqrt(self.vr * self.vr + self.vc * self.vc)
        frac = min(1.0, speed / SPEED_BAR_MAX)
        bar_w = max(1e-4, frac * SPEED_BAR_W)
        self._speed_bar_fill.position = Vec3(
            SPEED_BAR_X - SPEED_BAR_W / 2 + bar_w / 2,
            SPEED_BAR_Y,
            -0.01,
        )
        self._speed_bar_fill.scale_x = bar_w

    def getPrompt(self) -> str:
        hole_text = ""
        if any("H" in row for row in self.grid):
            hole_text = (
                f" Avoid holes in the board. You have {LIVES_MAX} chances per map: "
                "each fall uses one chance and respawns the marble at the start, and after all chances are spent a new map is generated. The red dots at the top of the screen show the remaining chances."
            )
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to tilt the board. "
            f"The marble rolls under gravity toward the low side of the board. Navigate the marble through the maze to reach the green goal tile.{hole_text} Press A to restart after winning."
            "There is a speed bar at the top left that indicates how fast the marble is rolling."
        )

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()
        if self.win:
            if random.random() < 0.05:
                action["A"] = True
            return action

        # Occasional reaction-delay frame: imitates human latency and breaks
        # the deterministic respawn->same-trajectory->same-hole loops that
        # otherwise trap the marble on trickier mazes.
        if random.random() < 0.05:
            return action

        waypoint = self._get_auto_waypoint()
        if waypoint is None:
            return action

        target_r, target_c = waypoint
        cautious = self._hole_near()
        max_speed = 0.3 if cautious else 0.9
        threshold = 0.15 if cautious else 0.18

        self._steer_axis(target_r - self.ball_r, self.vr, max_speed, threshold, "W", "S", action, cautious)
        self._steer_axis(target_c - self.ball_c, self.vc, max_speed, threshold, "D", "A", action, cautious)
        return action

    @staticmethod
    def _steer_axis(delta: float, v: float, max_speed: float, threshold: float,
                    pos_key: str, neg_key: str, action: dict, aggressive_brake: bool) -> None:
        # Aggressive mode actively tilts against velocity once it breaks the cap.
        # TILT_RETURN is 0, so a passive "stop pressing" does not decelerate —
        # only tilting the other way does.
        if aggressive_brake:
            if v > max_speed:
                action[neg_key] = True
                return
            if v < -max_speed:
                action[pos_key] = True
                return
        if abs(delta) > threshold:
            if delta > 0 and v < max_speed:
                action[pos_key] = True
            elif delta < 0 and v > -max_speed:
                action[neg_key] = True

    def _hole_near(self) -> bool:
        cr = int(self.ball_r)
        cc = int(self.ball_c)
        # Plus pattern (cardinal neighbours only): diagonals can't cause a
        # drift-fall since the marble can only slide along r or c axes.
        for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            if self._is_hole_cell(cr + dr, cc + dc):
                return True
        # Braking takes many frames to bite, so the faster the marble is going
        # the further we scan along the velocity direction for holes.
        speed_sq = self.vr * self.vr + self.vc * self.vc
        if speed_sq < 0.04:
            return False
        speed = math.sqrt(speed_sq)
        dir_r = self.vr / speed
        dir_c = self.vc / speed
        max_look = min(5.0, 2.0 + speed * 1.5)
        d = 1.5
        while d <= max_look:
            if self._is_hole_cell(int(self.ball_r + dir_r * d), int(self.ball_c + dir_c * d)):
                return True
            d += 0.5
        return False

    def _rebuild_auto_path(self) -> None:
        start = (int(self.start_r), int(self.start_c))
        goal = None
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c] == "G":
                    goal = (r, c)
                    break
            if goal is not None:
                break

        self.goal_cell = goal if goal is not None else start
        self._auto_path = self._find_path(start, self.goal_cell)

    def _find_path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        if start == goal:
            return [start]

        queue: deque[tuple[int, int]] = deque([start])
        prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

        while queue:
            r, c = queue.popleft()
            if (r, c) == goal:
                break

            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.grid_h and 0 <= nc < self.grid_w):
                    continue
                if self.grid[nr][nc] in ("#", "H"):
                    continue
                if (nr, nc) in prev:
                    continue
                prev[(nr, nc)] = (r, c)
                queue.append((nr, nc))

        if goal not in prev:
            return [start]

        path: list[tuple[int, int]] = []
        node: tuple[int, int] | None = goal
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        return path

    def _get_auto_waypoint(self) -> tuple[float, float] | None:
        if not self._auto_path:
            return None

        cell_r = min(max(int(self.ball_r), 0), self.grid_h - 1)
        cell_c = min(max(int(self.ball_c), 0), self.grid_w - 1)
        current = (cell_r, cell_c)

        try:
            path_index = self._auto_path.index(current)
        except ValueError:
            best_index = 0
            best_dist = float("inf")
            for i, (r, c) in enumerate(self._auto_path):
                dist = abs((r + 0.5) - self.ball_r) + abs((c + 0.5) - self.ball_c)
                if dist < best_dist:
                    best_dist = dist
                    best_index = i
            path_index = best_index

        next_index = min(path_index + 1, len(self._auto_path) - 1)
        target_cell = self._auto_path[next_index]
        return (target_cell[0] + 0.5, target_cell[1] + 0.5)

    def _resolve_collision_axis(self, axis: str) -> None:
        r0 = int(self.ball_r - BALL_R / CELL) - 1
        r1 = int(self.ball_r + BALL_R / CELL) + 1
        c0 = int(self.ball_c - BALL_R / CELL) - 1
        c1 = int(self.ball_c + BALL_R / CELL) + 1

        for r in range(max(0, r0), min(self.grid_h, r1 + 1)):
            for c in range(max(0, c0), min(self.grid_w, c1 + 1)):
                if self.grid[r][c] != "#":
                    continue
                nr = max(float(r), min(self.ball_r, float(r + 1)))
                nc = max(float(c), min(self.ball_c, float(c + 1)))
                dr = self.ball_r - nr
                dc = self.ball_c - nc
                dist = math.sqrt(dr * dr + dc * dc)
                if dist < BALL_R / CELL and dist > 1e-9:
                    overlap = BALL_R / CELL - dist
                    pen_r = dr / dist * overlap
                    pen_c = dc / dist * overlap
                    if axis == "r":
                        self.ball_r += pen_r
                        if abs(pen_r) > abs(pen_c) * 0.5:
                            self.vr *= -ELASTICITY
                    else:
                        self.ball_c += pen_c
                        if abs(pen_c) > abs(pen_r) * 0.5:
                            self.vc *= -ELASTICITY

    def _build_scene(self) -> None:
        pivot = Entity()
        self._board = pivot
        self._entities.append(pivot)

        for r in range(self.grid_h):
            for c in range(self.grid_w):
                ch = self.grid[r][c]
                wx = (c - self.grid_w / 2 + 0.5) * CELL
                wz = (r - self.grid_h / 2 + 0.5) * CELL

                if ch == "H":
                    continue

                backing_tile = Entity(
                    parent=pivot,
                    model="cube",
                    color=color.rgba32(10, 12, 18),
                    scale=Vec3(CELL, BOARD_THICK * 0.2, CELL),
                    position=Vec3(wx, -0.38, wz),
                    shader=lit_with_shadows_shader,
                )
                self._entities.append(backing_tile)

                floor_tile = Entity(
                    parent=pivot,
                    model="cube",
                    color=color.rgba32(55, 55, 70),
                    scale=Vec3(CELL, BOARD_THICK, CELL),
                    position=Vec3(wx, -BOARD_THICK / 2, wz),
                    shader=lit_with_shadows_shader,
                )
                self._entities.append(floor_tile)

                if ch == "#":
                    wall = Entity(
                        parent=pivot,
                        model="cube",
                        color=self.wall_color,
                        scale=Vec3(CELL, WALL_H, CELL),
                        position=Vec3(wx, WALL_H / 2, wz),
                        shader=lit_with_shadows_shader,
                    )
                    self._entities.append(wall)
                elif ch == "G":
                    goal = Entity(
                        parent=pivot,
                        model="cube",
                        color=color.lime,
                        scale=Vec3(CELL * 0.85, 0.06, CELL * 0.85),
                        position=Vec3(wx, 0.03, wz),
                        shader=lit_with_shadows_shader,
                    )
                    self._entities.append(goal)

        sx = (self.start_c - self.grid_w / 2) * CELL
        sz = (self.start_r - self.grid_h / 2) * CELL
        marble = Entity(
            parent=pivot,
            model="sphere",
            color=self.marble_color,
            scale=BALL_R * 2.6,
            position=Vec3(sx, BALL_R, sz),
            shader=lit_with_shadows_shader,
        )
        self._marble = marble
        self._entities.append(marble)

        start_pos = Vec3(sx, BALL_R, sz)
        self._trail_entities = []
        for i in range(TRAIL_COUNT):
            age_frac = 1.0 - i / TRAIL_COUNT
            trail = Entity(
                parent=pivot,
                model="sphere",
                color=self.marble_color,
                alpha=1 * age_frac,
                scale=BALL_R * 2.6 * (0.3 + 0.6 * age_frac),
                position=start_pos,
            )
            self._trail_entities.append(trail)
            self._entities.append(trail)

    def _generate_maze(self, w: int, h: int) -> list[list[str]]:
        w = w if w % 2 == 1 else w + 1
        h = h if h % 2 == 1 else h + 1
        maze = [["#"] * w for _ in range(h)]
        directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        maze[1][1] = " "
        stack = [(1, 1)]

        while stack:
            r, c = stack[-1]
            random.shuffle(directions)
            carved = False
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 1 <= nr < h - 1 and 1 <= nc < w - 1 and maze[nr][nc] == "#":
                    maze[r + dr // 2][c + dc // 2] = " "
                    maze[nr][nc] = " "
                    stack.append((nr, nc))
                    carved = True
                    break
            if not carved:
                stack.pop()

        maze[h - 2][w - 2] = "G"
        return maze


if __name__ == "__main__":
    from ursinaRunner import run_human_debug

    run_human_debug(MarbleMazeUrsina)
