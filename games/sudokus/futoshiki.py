from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import InequalitySignsRule, orthogonal_pairs


class FutoshikiSudoku(SudokuBase):
    """Sudoku variant with inequality signs between adjacent cells."""

    name = "Futoshiki Sudoku"
    require_unique_solution = False

    def choose_target_clues(self) -> int:
        """Use a slightly lower clue count because the inequalities add information."""
        return random.randint(10, 18)

    def get_extra_puzzle_rules(self, solution: list[list[int]]) -> list:
        """Derive a random set of inequality clues from the solved board."""
        pairs = orthogonal_pairs(self.side)
        random.shuffle(pairs)
        greater_pairs = []
        count = random.randint(40, 48)
        for left_cell, right_cell in pairs[:count]:
            left_value = solution[left_cell[0]][left_cell[1]]
            right_value = solution[right_cell[0]][right_cell[1]]
            if left_value > right_value:
                greater_pairs.append((left_cell, right_cell))
            else:
                greater_pairs.append((right_cell, left_cell))
        return [InequalitySignsRule("Inequality signs point toward the smaller digit.", greater_pairs)]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(FutoshikiSudoku)
