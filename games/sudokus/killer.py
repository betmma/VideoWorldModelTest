from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import CageSumRule


class KillerSudoku(SudokuBase):
    """Sudoku variant with sum cages."""

    name = "Killer Sudoku"
    require_unique_solution = False

    def prepare_puzzle_layout(self) -> None:
        """Clear the cage rule before a new puzzle is generated."""
        self.cage_rule = None

    def choose_target_clues(self) -> int:
        """Use fewer givens because the cages add strong information."""
        return random.randint(6, 11)

    def get_cell_neighbors(self, row: int, col: int) -> list[tuple[int, int]]:
        """Return orthogonal in-bounds neighbors for cage growth."""
        neighbors = []
        for row_step, col_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            next_row = row + row_step
            next_col = col + col_step
            if 0 <= next_row < self.side and 0 <= next_col < self.side:
                neighbors.append((next_row, next_col))
        return neighbors

    def get_cage_frontier(self, group: list[tuple[int, int]], unused: set[tuple[int, int]], used_digits: set[int], solution: list[list[int]]) -> list[tuple[int, int]]:
        """Return unused neighboring cells that keep cage digits distinct."""
        frontier = []
        for row, col in group:
            for next_row, next_col in self.get_cell_neighbors(row, col):
                if (next_row, next_col) not in unused:
                    continue
                if solution[next_row][next_col] in used_digits:
                    continue
                if (next_row, next_col) not in frontier:
                    frontier.append((next_row, next_col))
        return frontier

    def build_cages(self, solution: list[list[int]]) -> tuple[list[list[tuple[int, int]]], list[int]]:
        """Partition the board into connected cages with distinct solved digits."""
        unused = {(row, col) for row in range(self.side) for col in range(self.side)}
        groups = []
        targets = []

        while len(unused) > 0:
            start = random.choice(list(unused))
            target_size = random.choice([1, 2, 2, 3, 3, 4])
            group = [start]
            used_digits = {solution[start[0]][start[1]]}
            unused.remove(start)

            while len(group) < target_size:
                frontier = self.get_cage_frontier(group, unused, used_digits, solution)
                if len(frontier) == 0:
                    break
                next_cell = random.choice(frontier)
                group.append(next_cell)
                used_digits.add(solution[next_cell[0]][next_cell[1]])
                unused.remove(next_cell)

            groups.append(group)
            targets.append(sum(solution[row][col] for row, col in group))

        return groups, targets

    def get_extra_puzzle_rules(self, solution: list[list[int]]) -> list:
        """Build the connected cage sums from the solved board."""
        groups, targets = self.build_cages(solution)
        self.cage_rule = CageSumRule("Digits in each cage must add to the small corner total, and digits cannot repeat inside a cage.", groups, targets)
        return [self.cage_rule]

    def draw_rule_overlays(self, cell_rects) -> None:
        """Skip the default pre-grid rule draw so cages can be painted after the grid."""
        return None

    def draw_grid_lines(self, cell_size: int, board_left: int, board_top: int) -> None:
        """Draw the normal grid first, then the darker cage boundaries."""
        super().draw_grid_lines(cell_size, board_left, board_top)
        if self.cage_rule is not None:
            cell_rects = self.get_cell_rects(cell_size, board_left, board_top)
            self.cage_rule.draw_overlay(self, cell_rects)


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(KillerSudoku)
