from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import TintedGroupRule


class SudokuX(SudokuBase):
    """Sudoku variant with diagonal uniqueness."""

    name = "Sudoku X"

    def choose_target_clues(self) -> int:
        """Use a moderate clue count for the stronger diagonal constraint."""
        return random.randint(21, 28)

    def get_extra_generation_rules(self) -> list:
        """Require both diagonals to contain each digit at most once."""
        main_diagonal = [(index, index) for index in range(self.side)]
        anti_diagonal = [(index, self.side - 1 - index) for index in range(self.side)]
        return [TintedGroupRule("Each blue diagonal must contain each digit at most once.", [main_diagonal, anti_diagonal], (110, 170, 230, 56))]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(SudokuX)
