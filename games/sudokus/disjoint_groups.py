from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase, UniqueGroupRule


class DisjointGroupsSudoku(SudokuBase):
    """Sudoku variant with disjoint-box-position uniqueness."""

    name = "Disjoint Groups Sudoku"

    def choose_target_clues(self) -> int:
        """Use a moderate clue count for the stronger structural rule."""
        return random.randint(21, 28)

    def get_extra_generation_rules(self) -> list:
        """Require matching positions inside each box to stay unique."""
        groups = []
        for local_row in range(self.box_rows):
            for local_col in range(self.box_cols):
                groups.append([(box_row * self.box_rows + local_row, box_col * self.box_cols + local_col) for box_row in range(self.box_cols) for box_col in range(self.box_rows)])
        return [UniqueGroupRule("Cells in the same relative position inside each box must contain each digit at most once.", groups)]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(DisjointGroupsSudoku)
