from __future__ import annotations

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


class MarbleMazeUrsina(UrsinaGameBase):
    name = "Marble Maze 3D"
    variantsPath = "marble_mazes"
    background_color = color.rgb32(18, 20, 28)

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

        camera.position = Vec3(0, 14, -4)
        camera.look_at(Vec3(0, 0, 0))
        camera.fov = 70
        if getattr(self.app, "win", None) is not None:
            self.app.win.setClearColor(self.background_color)

        self._sun = DirectionalLight(shadow_map_resolution=(2048, 2048))
        self._sun.look_at(Vec3(1, -2, 1))
        self._ambient = AmbientLight(color=color.rgba(150, 150, 165, 255))

        self._entities: list[Entity] = []
        self._board: Entity | None = None
        self._marble: Entity | None = None

        self.reset()

    def reset(self) -> None:
        for entity in self._entities:
            destroy(entity)
        self._entities.clear()
        self._board = None
        self._marble = None

        self.tilt_x = 0.0
        self.tilt_z = 0.0
        self.ball_r = 0.0
        self.ball_c = 0.0
        self.vr = 0.0
        self.vc = 0.0

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

        self._create_level()
        self._rebuild_auto_path()
        self._build_scene()

        self.ball_r = self.start_r
        self.ball_c = self.start_c

    def _create_level(self) -> None:
        w, h = 15, 11
        self.grid_w, self.grid_h = w, h
        self.grid = self._generate_maze(w, h)
        self.start_r, self.start_c = 1.5, 1.5

    def _respawn_ball(self) -> None:
        self.ball_r = self.start_r
        self.ball_c = self.start_c
        self.vr = 0.0
        self.vc = 0.0
        self.tilt_x = 0.0
        self.tilt_z = 0.0
        if self._board:
            self._board.rotation_x = 0.0
            self._board.rotation_z = 0.0

    def _is_hole_cell(self, r: int, c: int) -> bool:
        return 0 <= r < self.grid_h and 0 <= c < self.grid_w and self.grid[r][c] == "H"

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

        if self._marble:
            self._marble.position = Vec3(
                (self.ball_c - self.grid_w / 2) * CELL,
                BALL_R,
                (self.ball_r - self.grid_h / 2) * CELL,
            )

        if self._is_hole_cell(int(self.ball_r), int(self.ball_c)):
            self._respawn_ball()
            if self._marble:
                self._marble.position = Vec3(
                    (self.ball_c - self.grid_w / 2) * CELL,
                    BALL_R,
                    (self.ball_r - self.grid_h / 2) * CELL,
                )

        r, c = int(self.ball_r), int(self.ball_c)
        if 0 <= r < self.grid_h and 0 <= c < self.grid_w and self.grid[r][c] == "G" and not self.win:
            self.win = True
            self.end_reported = True
            self.end_event_pending = True
            if self._marble:
                self._marble.color = color.lime

        return False

    def draw(self) -> None:
        pass

    def getPrompt(self) -> str:
        hole_text = ""
        if any("H" in row for row in self.grid):
            hole_text = " Avoid real holes in the board, which reset the marble to the starting position."
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to tilt the board. "
            f"The marble rolls under gravity toward the low side of the board. Navigate the marble through the maze to reach the green goal tile.{hole_text} Press A to restart after winning."
        )

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()
        if self.win:
            if random.random() < 0.05:
                action["A"] = True
            return action

        waypoint = self._get_auto_waypoint()
        if waypoint is None:
            return action

        target_r, target_c = waypoint
        dr = target_r - self.ball_r
        dc = target_c - self.ball_c

        row_threshold = 0.18
        col_threshold = 0.18
        max_row_speed = 0.9
        max_col_speed = 0.9

        if abs(dr) > row_threshold:
            if dr > 0 and self.vr < max_row_speed:
                action["W"] = True
            elif dr < 0 and self.vr > -max_row_speed:
                action["S"] = True

        if abs(dc) > col_threshold:
            if dc > 0 and self.vc < max_col_speed:
                action["D"] = True
            elif dc < 0 and self.vc > -max_col_speed:
                action["A"] = True

        return action

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

        backing = Entity(
            parent=pivot,
            model="cube",
            color=color.rgb(10, 12, 18),
            scale=Vec3(self.grid_w * CELL, BOARD_THICK * 0.2, self.grid_h * CELL),
            position=Vec3(0, -0.38, 0),
            shader=lit_with_shadows_shader,
        )
        self._entities.append(backing)

        for r in range(self.grid_h):
            for c in range(self.grid_w):
                ch = self.grid[r][c]
                wx = (c - self.grid_w / 2 + 0.5) * CELL
                wz = (r - self.grid_h / 2 + 0.5) * CELL

                if ch != "H":
                    floor_tile = Entity(
                        parent=pivot,
                        model="cube",
                        color=color.rgb(55, 55, 70),
                        scale=Vec3(CELL, BOARD_THICK, CELL),
                        position=Vec3(wx, -BOARD_THICK / 2, wz),
                        shader=lit_with_shadows_shader,
                    )
                    self._entities.append(floor_tile)

                if ch == "#":
                    wall = Entity(
                        parent=pivot,
                        model="cube",
                        color=color.azure,
                        scale=Vec3(CELL, WALL_H, CELL),
                        position=Vec3(wx, WALL_H / 2, wz),
                        shader=lit_with_shadows_shader,
                    )
                    self._entities.append(wall)
                elif ch == "H":
                    hole_back = Entity(
                        parent=pivot,
                        model="cube",
                        color=color.black,
                        scale=Vec3(CELL * 0.66, BOARD_THICK * 0.06, CELL * 0.66),
                        position=Vec3(wx, -0.34, wz),
                        shader=lit_with_shadows_shader,
                    )
                    self._entities.append(hole_back)
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

        sx = (self.start_c - self.grid_w / 2 + 0.5) * CELL
        sz = (self.start_r - self.grid_h / 2 + 0.5) * CELL
        marble = Entity(
            parent=pivot,
            model="sphere",
            color=color.orange,
            scale=BALL_R * 2.6,
            position=Vec3(sx, BALL_R, sz),
            shader=lit_with_shadows_shader,
        )
        self._marble = marble
        self._entities.append(marble)

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
