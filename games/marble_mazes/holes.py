from __future__ import annotations

import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.marble_maze_ursina import MarbleMazeUrsina


class MarbleMazeWithHoles(MarbleMazeUrsina):
    name = "Marble Maze With Holes"

    def _create_level(self) -> None:
        self.grid_w, self.grid_h = 15, 11
        self.start_r, self.start_c = 1.5, 1.5

        for _ in range(32):
            grid = self._generate_maze(self.grid_w, self.grid_h)
            path = self._find_path_in_grid(grid, (1, 1), (self.grid_h - 2, self.grid_w - 2))
            if len(path) < 8:
                continue

            hole_count = random.randint(3, 6)
            self._place_random_holes(grid, hole_count)
            if self._find_path_in_grid(grid, (1, 1), (self.grid_h - 2, self.grid_w - 2)):
                self.grid = grid
                return

        self.grid = self._generate_maze(self.grid_w, self.grid_h)

    def _place_random_holes(
        self,
        grid: list[list[str]],
        hole_count: int,
    ) -> None:
        start_cell = (1, 1)
        goal_cell = (self.grid_h - 2, self.grid_w - 2)
        safe_radius = 2

        def _near_endpoint(r: int, c: int) -> bool:
            return (
                abs(r - start_cell[0]) + abs(c - start_cell[1]) <= safe_radius
                or abs(r - goal_cell[0]) + abs(c - goal_cell[1]) <= safe_radius
            )

        candidates: list[tuple[int, int]] = []
        for r in range(1, self.grid_h - 1):
            for c in range(1, self.grid_w - 1):
                if grid[r][c] != "#":
                    continue
                if _near_endpoint(r, c):
                    continue
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w and grid[nr][nc] == " ":
                        candidates.append((r, c))
                        break

        random.shuffle(candidates)

        holes: list[tuple[int, int]] = []
        for r, c in candidates:
            if any(abs(hr - r) + abs(hc - c) < 3 for hr, hc in holes):
                continue
            grid[r][c] = "H"
            holes.append((r, c))
            if len(holes) >= hole_count:
                break

    def _find_path_in_grid(
        self,
        grid: list[list[str]],
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> list[tuple[int, int]]:
        if start == goal:
            return [start]

        queue = [start]
        prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        while queue:
            r, c = queue.pop(0)
            if (r, c) == goal:
                break
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < len(grid) and 0 <= nc < len(grid[0])):
                    continue
                if grid[nr][nc] in ("#", "H"):
                    continue
                if (nr, nc) in prev:
                    continue
                prev[(nr, nc)] = (r, c)
                queue.append((nr, nc))

        if goal not in prev:
            return []

        path: list[tuple[int, int]] = []
        node: tuple[int, int] | None = goal
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        return path


if __name__ == "__main__":
    from ursinaRunner import run_human_debug, run_autoplay

    run_autoplay(MarbleMazeWithHoles)
