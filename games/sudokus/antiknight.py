from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import DifferentPairRule, knight_pairs


class AntiKnightSudoku(SudokuBase):
    """Sudoku variant with anti-knight chess movement."""

    name = "Anti-Knight Sudoku"

    def choose_target_clues(self) -> int:
        """Use a moderate clue count for the stronger movement rule."""
        return random.randint(21, 28)

    def get_extra_generation_rules(self) -> list:
        """Forbid equal digits at a knight's move distance."""
        return [DifferentPairRule("Cells a knight's move apart cannot contain the same digit.", knight_pairs(self.side))]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(AntiKnightSudoku)
