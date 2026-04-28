from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import SkyscraperClueRule


class SkyscraperSudoku(SudokuBase):
    """Sudoku variant with outer visibility clues."""

    name = "Skyscraper Sudoku"
    require_unique_solution = False

    def prepare_puzzle_layout(self) -> None:
        """Leave extra margin for the outside clue numbers."""
        self.margin = 38

    def choose_target_clues(self) -> int:
        """Use fewer givens because the outside clues add information."""
        return random.randint(21, 28)

    def count_visible(self, values: list[int]) -> int:
        """Count how many heights are visible from the start of the line."""
        visible = 0
        tallest = 0
        for value in values:
            if value > tallest:
                tallest = value
                visible += 1
        return visible

    def get_extra_puzzle_rules(self, solution: list[list[int]]) -> list:
        """Derive top, bottom, left, and right visibility clues."""
        entries = []
        for row in range(self.side):
            left_line = [(row, col) for col in range(self.side)]
            right_line = list(reversed(left_line))
            left_values = [solution[cell[0]][cell[1]] for cell in left_line]
            right_values = [solution[cell[0]][cell[1]] for cell in right_line]
            entries.append((left_line, self.count_visible(left_values), "left"))
            entries.append((right_line, self.count_visible(right_values), "right"))

        for col in range(self.side):
            top_line = [(row, col) for row in range(self.side)]
            bottom_line = list(reversed(top_line))
            top_values = [solution[cell[0]][cell[1]] for cell in top_line]
            bottom_values = [solution[cell[0]][cell[1]] for cell in bottom_line]
            entries.append((top_line, self.count_visible(top_values), "top"))
            entries.append((bottom_line, self.count_visible(bottom_values), "bottom"))

        return [SkyscraperClueRule("Numbers outside the grid show how many heights are visible from that side.", entries)]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(SkyscraperSudoku)
