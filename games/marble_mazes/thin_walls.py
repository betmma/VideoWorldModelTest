from __future__ import annotations

import os
import random
import sys
from collections import deque

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ursina import Entity, Vec3, color
from ursina.shaders import lit_with_shadows_shader

from games.marble_maze_ursina import (
    BALL_R,
    BOARD_THICK,
    CELL,
    ELASTICITY,
    MarbleMazeUrsina,
    TRAIL_COUNT,
    WALL_H,
)


WALL_THICKNESS = 0.12


class ThinWallMarbleMaze(MarbleMazeUrsina):
    name = "Thin-Wall Marble Maze"

    def _create_level(self) -> None:
        self.grid_w = 8
        self.grid_h = 6
        # Every cell is playable; the goal sits in the far corner.
        self.grid = [[" "] * self.grid_w for _ in range(self.grid_h)]
        self.grid[self.grid_h - 1][self.grid_w - 1] = "G"
        # Interior walls as an edge set. Outer boundary is always walled
        # and handled separately.
        self._walls: set[frozenset] = self._generate_walls()
        self.start_r, self.start_c = 0.5, 0.5

    def _generate_walls(self) -> set[frozenset]:
        walls: set[frozenset] = set()
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if c < self.grid_w - 1:
                    walls.add(frozenset({(r, c), (r, c + 1)}))
                if r < self.grid_h - 1:
                    walls.add(frozenset({(r, c), (r + 1, c)}))

        visited = {(0, 0)}
        stack = [(0, 0)]
        while stack:
            r, c = stack[-1]
            neighbors = []
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w and (nr, nc) not in visited:
                    neighbors.append((nr, nc))
            if neighbors:
                nr, nc = random.choice(neighbors)
                walls.discard(frozenset({(r, c), (nr, nc)}))
                visited.add((nr, nc))
                stack.append((nr, nc))
            else:
                stack.pop()
        return walls

    def _has_wall(self, r1: int, c1: int, r2: int, c2: int) -> bool:
        return frozenset({(r1, c1), (r2, c2)}) in self._walls

    def _find_path(self, start, goal):
        if start == goal:
            return [start]
        queue: deque = deque([start])
        prev: dict = {start: None}
        while queue:
            r, c = queue.popleft()
            if (r, c) == goal:
                break
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.grid_h and 0 <= nc < self.grid_w):
                    continue
                if (nr, nc) in prev:
                    continue
                if self._has_wall(r, c, nr, nc):
                    continue
                if self.grid[nr][nc] == "H":
                    continue
                prev[(nr, nc)] = (r, c)
                queue.append((nr, nc))
        if goal not in prev:
            return [start]
        path = []
        node = goal
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        return path

    def _resolve_collision_axis(self, axis: str) -> None:
        radius = BALL_R / CELL

        # Outer boundary (the perimeter is always walled).
        if self.ball_r < radius:
            self.ball_r = radius
            if self.vr < 0:
                self.vr *= -ELASTICITY
        elif self.ball_r > self.grid_h - radius:
            self.ball_r = self.grid_h - radius
            if self.vr > 0:
                self.vr *= -ELASTICITY
        if self.ball_c < radius:
            self.ball_c = radius
            if self.vc < 0:
                self.vc *= -ELASTICITY
        elif self.ball_c > self.grid_w - radius:
            self.ball_c = self.grid_w - radius
            if self.vc > 0:
                self.vc *= -ELASTICITY

        cell_r = int(self.ball_r)
        cell_c = int(self.ball_c)

        # Interior thin walls are line segments. Use circle-vs-segment collision
        # so the ball wraps each segment's endpoints smoothly instead of
        # snagging against an axis-aligned "cap".
        for dr in (-1, 0, 1):
            wall_r = cell_r + dr
            if wall_r < 1 or wall_r >= self.grid_h:
                continue
            for dc in (-1, 0, 1):
                c = cell_c + dc
                if c < 0 or c >= self.grid_w:
                    continue
                if self._has_wall(wall_r - 1, c, wall_r, c):
                    self._collide_segment(float(wall_r), float(c), float(wall_r), float(c + 1))

        for dc in (-1, 0, 1):
            wall_c = cell_c + dc
            if wall_c < 1 or wall_c >= self.grid_w:
                continue
            for dr in (-1, 0, 1):
                r = cell_r + dr
                if r < 0 or r >= self.grid_h:
                    continue
                if self._has_wall(r, wall_c - 1, r, wall_c):
                    self._collide_segment(float(r), float(wall_c), float(r + 1), float(wall_c))

    def _collide_segment(self, ar: float, ac: float, br: float, bc: float) -> None:
        radius = BALL_R / CELL
        abr = br - ar
        abc = bc - ac
        ab_len_sq = abr * abr + abc * abc
        if ab_len_sq < 1e-12:
            cr, cc = ar, ac
        else:
            t = ((self.ball_r - ar) * abr + (self.ball_c - ac) * abc) / ab_len_sq
            t = max(0.0, min(1.0, t))
            cr = ar + t * abr
            cc = ac + t * abc
        dr = self.ball_r - cr
        dc = self.ball_c - cc
        dist_sq = dr * dr + dc * dc
        if dist_sq >= radius * radius or dist_sq < 1e-12:
            return
        dist = dist_sq ** 0.5
        overlap = radius - dist
        nr = dr / dist
        nc = dc / dist
        self.ball_r += nr * overlap
        self.ball_c += nc * overlap
        v_dot_n = self.vr * nr + self.vc * nc
        if v_dot_n < 0:
            impulse = -(1 + ELASTICITY) * v_dot_n
            self.vr += impulse * nr
            self.vc += impulse * nc

    def _build_scene(self) -> None:
        pivot = Entity()
        self._board = pivot
        self._entities.append(pivot)

        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c] == "H":
                    continue
                wx = (c - self.grid_w / 2 + 0.5) * CELL
                wz = (r - self.grid_h / 2 + 0.5) * CELL

                backing = Entity(
                    parent=pivot,
                    model="cube",
                    color=color.rgba32(10, 12, 18),
                    scale=Vec3(CELL, BOARD_THICK * 0.2, CELL),
                    position=Vec3(wx, -0.38, wz),
                    shader=lit_with_shadows_shader,
                )
                self._entities.append(backing)

                floor = Entity(
                    parent=pivot,
                    model="cube",
                    color=color.rgba32(55, 55, 70),
                    scale=Vec3(CELL, BOARD_THICK, CELL),
                    position=Vec3(wx, -BOARD_THICK / 2, wz),
                    shader=lit_with_shadows_shader,
                )
                self._entities.append(floor)

                if self.grid[r][c] == "G":
                    goal = Entity(
                        parent=pivot,
                        model="cube",
                        color=color.lime,
                        scale=Vec3(CELL * 0.85, 0.06, CELL * 0.85),
                        position=Vec3(wx, 0.03, wz),
                        shader=lit_with_shadows_shader,
                    )
                    self._entities.append(goal)

        # Outer boundary walls — always rendered along the perimeter.
        for c in range(self.grid_w):
            wx = (c - self.grid_w / 2 + 0.5) * CELL
            for wall_r in (0, self.grid_h):
                wz = (wall_r - self.grid_h / 2) * CELL
                self._entities.append(Entity(
                    parent=pivot,
                    model="cube",
                    color=self.wall_color,
                    scale=Vec3(CELL + WALL_THICKNESS, WALL_H, WALL_THICKNESS),
                    position=Vec3(wx, WALL_H / 2, wz),
                    shader=lit_with_shadows_shader,
                ))
        for r in range(self.grid_h):
            wz = (r - self.grid_h / 2 + 0.5) * CELL
            for wall_c in (0, self.grid_w):
                wx = (wall_c - self.grid_w / 2) * CELL
                self._entities.append(Entity(
                    parent=pivot,
                    model="cube",
                    color=self.wall_color,
                    scale=Vec3(WALL_THICKNESS, WALL_H, CELL + WALL_THICKNESS),
                    position=Vec3(wx, WALL_H / 2, wz),
                    shader=lit_with_shadows_shader,
                ))

        # Interior walls at cell edges.
        for wall_set in self._walls:
            (r1, c1), (r2, c2) = sorted(wall_set)
            if r1 == r2:
                # Horizontal neighbors -> vertical wall at the shared column boundary.
                wall_c = max(c1, c2)
                wx = (wall_c - self.grid_w / 2) * CELL
                wz = (r1 - self.grid_h / 2 + 0.5) * CELL
                self._entities.append(Entity(
                    parent=pivot,
                    model="cube",
                    color=self.wall_color,
                    scale=Vec3(WALL_THICKNESS, WALL_H, CELL + WALL_THICKNESS),
                    position=Vec3(wx, WALL_H / 2, wz),
                    shader=lit_with_shadows_shader,
                ))
            else:
                # Vertical neighbors -> horizontal wall at the shared row boundary.
                wall_r = max(r1, r2)
                wx = (c1 - self.grid_w / 2 + 0.5) * CELL
                wz = (wall_r - self.grid_h / 2) * CELL
                self._entities.append(Entity(
                    parent=pivot,
                    model="cube",
                    color=self.wall_color,
                    scale=Vec3(CELL + WALL_THICKNESS, WALL_H, WALL_THICKNESS),
                    position=Vec3(wx, WALL_H / 2, wz),
                    shader=lit_with_shadows_shader,
                ))

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
                alpha=0.55 * age_frac,
                scale=BALL_R * 2.6 * (0.3 + 0.6 * age_frac),
                position=start_pos,
            )
            self._trail_entities.append(trail)
            self._entities.append(trail)

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to tilt the board. "
            "The marble rolls under gravity. Navigate through the narrow corridors separated by thin walls at cell edges to reach the green goal tile. Press A to restart after winning."
        )


if __name__ == "__main__":
    from ursinaRunner import run_human_debug, run_autoplay

    run_human_debug(ThinWallMarbleMaze)
