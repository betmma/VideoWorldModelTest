from __future__ import annotations

import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.marble_mazes.thin_walls import ThinWallMarbleMaze


class ThinWallMarbleMazeWithHoles(ThinWallMarbleMaze):
    name = "Thin-Wall Marble Maze With Holes"

    def _create_level(self) -> None:
        self.grid_w = 8
        self.grid_h = 6
        self.start_r, self.start_c = 0.5, 0.5

        start_cell = (0, 0)
        goal_cell = (self.grid_h - 1, self.grid_w - 1)

        protected = {start_cell, goal_cell}
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for base in (start_cell, goal_cell):
                nr, nc = base[0] + dr, base[1] + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    protected.add((nr, nc))

        candidates = [
            (r, c)
            for r in range(self.grid_h)
            for c in range(self.grid_w)
            if (r, c) not in protected
        ]

        holes: set[tuple[int, int]] = set()
        for _ in range(32):
            random.shuffle(candidates)
            hole_count = random.randint(3, 6)
            candidate_holes = set(candidates[:hole_count])
            if self._cells_connected(start_cell, goal_cell, candidate_holes):
                holes = candidate_holes
                break

        self.grid = [[" "] * self.grid_w for _ in range(self.grid_h)]
        for (hr, hc) in holes:
            self.grid[hr][hc] = "H"
        self.grid[goal_cell[0]][goal_cell[1]] = "G"

        self._walls = self._generate_walls_avoiding(holes)
        self._open_walls_to_holes(holes)

    def _cells_connected(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        holes: set[tuple[int, int]],
    ) -> bool:
        if start in holes or goal in holes:
            return False
        visited = {start}
        stack = [start]
        while stack:
            r, c = stack.pop()
            if (r, c) == goal:
                return True
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.grid_h and 0 <= nc < self.grid_w):
                    continue
                if (nr, nc) in holes or (nr, nc) in visited:
                    continue
                visited.add((nr, nc))
                stack.append((nr, nc))
        return False

    def _generate_walls_avoiding(self, holes: set[tuple[int, int]]) -> set[frozenset]:
        walls: set[frozenset] = set()
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if c < self.grid_w - 1:
                    walls.add(frozenset({(r, c), (r, c + 1)}))
                if r < self.grid_h - 1:
                    walls.add(frozenset({(r, c), (r + 1, c)}))

        # DFS carves a spanning tree over non-hole cells only, so holes stay
        # surrounded by walls after this pass.
        visited = set(holes)
        visited.add((0, 0))
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

    def _open_walls_to_holes(self, holes: set[tuple[int, int]]) -> None:
        # Knock out 1-2 walls per hole so the marble can actually roll into it.
        # Only open to non-hole neighbours; hole-to-hole openings would be
        # unreachable.
        for (hr, hc) in holes:
            adjacent = []
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = hr + dr, hc + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w and (nr, nc) not in holes:
                    adjacent.append((nr, nc))
            if not adjacent:
                continue
            random.shuffle(adjacent)
            opens = random.randint(1, min(2, len(adjacent)))
            for (nr, nc) in adjacent[:opens]:
                self._walls.discard(frozenset({(hr, hc), (nr, nc)}))

    def getPrompt(self) -> str:
        from games.marble_maze_ursina import LIVES_MAX

        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to tilt the board. "
            "The marble rolls under gravity. Navigate through the narrow corridors "
            "separated by thin walls at cell edges to reach the green goal tile. "
            "Avoid the open holes in the board; rolling into one drops the marble "
            "into the void. "
            f"You have {LIVES_MAX} chances per map: each fall uses one chance and "
            "respawns the marble at the start, and after all chances are spent a "
            "new map is generated. The red dots at the top of the screen show the "
            "remaining chances. Press A to restart after winning."
        )


if __name__ == "__main__":
    from ursinaRunner import run_human_debug, run_autoplay

    run_autoplay(ThinWallMarbleMazeWithHoles)
