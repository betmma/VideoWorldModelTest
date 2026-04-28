from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import WhispersLineRule


class GermanWhispersSudoku(SudokuBase):
    """Sudoku variant with a green line requiring large differences."""

    name = "German Whispers Sudoku"
    require_unique_solution = False

    def choose_target_clues(self) -> int:
        """Use a slightly lower clue count because the line adds structure."""
        return random.randint(21, 28)

    def generate_solution_board(self) -> list[list[int]]:
        """Keep generating solved boards until a long whispers path is available."""
        while True:
            solution = super().generate_solution_board()
            line = self.find_whispers_line(solution, random.randint(6, 8))
            if line is not None:
                self.whispers_line = line
                return solution

    def get_whispers_adjacency(self, solution: list[list[int]]) -> dict:
        """Return orthogonal neighbors whose solved digits differ by at least five."""
        adjacency = {}
        for row in range(self.side):
            for col in range(self.side):
                cell = (row, col)
                neighbors = []
                for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    next_row = row + row_step
                    next_col = col + col_step
                    if 0 <= next_row < self.side and 0 <= next_col < self.side:
                        if abs(solution[row][col] - solution[next_row][next_col]) >= 5:
                            neighbors.append((next_row, next_col))
                adjacency[cell] = neighbors
        return adjacency

    def find_whispers_line(self, solution: list[list[int]], min_length: int) -> list | None:
        """Search for a simple path long enough to become the green line."""
        adjacency = self.get_whispers_adjacency(solution)
        starts = list(adjacency.keys())
        random.shuffle(starts)
        best_line: list = []

        def dfs(cell: tuple[int, int], path: list[tuple[int, int]], visited: set[tuple[int, int]]) -> list | None:
            """Grow one self-avoiding whispers path from the current cell."""
            nonlocal best_line
            if len(path) > len(best_line):
                best_line = path[:]
            if len(path) >= min_length:
                return path[:]
            options = adjacency[cell][:]
            random.shuffle(options)
            options.sort(key=lambda option: len(adjacency[option]), reverse=True)
            for next_cell in options:
                if next_cell in visited:
                    continue
                visited.add(next_cell)
                path.append(next_cell)
                found = dfs(next_cell, path, visited)
                if found is not None:
                    return found
                path.pop()
                visited.remove(next_cell)
            return None

        for start in starts:
            found = dfs(start, [start], {start})
            if found is not None:
                return found
        return best_line if len(best_line) >= min_length else None

    def get_extra_puzzle_rules(self, solution: list[list[int]]) -> list:
        """Build the green-line rule from the stored path."""
        return [WhispersLineRule("Adjacent digits on the green line must differ by at least 5.", self.whispers_line)]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(GermanWhispersSudoku)
