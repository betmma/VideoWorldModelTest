from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import ConsecutiveBarsRule, orthogonal_pairs


class ConsecutiveSudoku(SudokuBase):
    """Sudoku variant with marked consecutive neighbors."""

    name = "Consecutive Sudoku"
    require_unique_solution = False

    def choose_target_clues(self) -> int:
        """Use a moderate clue count because the bars add information."""
        return random.randint(21, 28)

    def generate_solution_board(self) -> list[list[int]]:
        """Keep generating solved boards until enough consecutive pairs appear."""
        while True:
            solution = super().generate_solution_board()
            pairs = []
            for left_cell, right_cell in orthogonal_pairs(self.side):
                left_value = solution[left_cell[0]][left_cell[1]]
                right_value = solution[right_cell[0]][right_cell[1]]
                if abs(left_value - right_value) == 1:
                    pairs.append((left_cell, right_cell))
            if len(pairs) >= 20:
                self.consecutive_pairs = pairs
                return solution

    def get_extra_puzzle_rules(self, solution: list[list[int]]) -> list:
        """Select a visible subset of consecutive bars for the puzzle."""
        pairs = self.consecutive_pairs[:]
        random.shuffle(pairs)
        count = random.randint(18, min(26, len(pairs)))
        return [ConsecutiveBarsRule("Cells connected by a white bar must be consecutive.", pairs[:count])]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(ConsecutiveSudoku)
