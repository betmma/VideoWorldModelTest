from __future__ import annotations

import os, sys, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import TintedGroupRule

WINDOKU_TEMPLATE = [
    [4, 1, 5, 2, 3, 9, 7, 6, 8],
    [7, 2, 9, 1, 6, 8, 5, 3, 4],
    [3, 6, 8, 4, 5, 7, 9, 1, 2],
    [8, 5, 7, 3, 1, 4, 6, 2, 9],
    [1, 9, 4, 6, 7, 2, 3, 8, 5],
    [2, 3, 6, 9, 8, 5, 1, 4, 7],
    [5, 4, 1, 8, 9, 6, 2, 7, 3],
    [6, 7, 2, 5, 4, 3, 8, 9, 1],
    [9, 8, 3, 7, 2, 1, 4, 5, 6],
]


def rotate_board(board: list[list[int]]) -> list[list[int]]:
    """Rotate one solved board ninety degrees clockwise."""
    side = len(board)
    return [[board[side - 1 - col][row] for col in range(side)] for row in range(side)]


def flip_board(board: list[list[int]]) -> list[list[int]]:
    """Mirror one solved board left to right."""
    return [list(reversed(row)) for row in board]


def transform_board(board: list[list[int]], transform_index: int) -> list[list[int]]:
    """Apply one of eight board symmetries to the solved template."""
    transformed = [row[:] for row in board]
    if transform_index >= 4:
        transformed = flip_board(transformed)
    for _ in range(transform_index % 4):
        transformed = rotate_board(transformed)
    return transformed


class WindokuSudoku(SudokuBase):
    """Sudoku variant with four extra 3x3 windows."""

    name = "Windoku"
    require_unique_solution = False

    def choose_target_clues(self) -> int:
        """Use a moderate clue count for the extra windows."""
        return random.randint(21, 28)

    def generate_solution_board(self) -> list[list[int]]:
        """Build a Windoku-valid solution from one transformed template."""
        digit_map = self.digits[:]
        random.shuffle(digit_map)
        transformed = transform_board(WINDOKU_TEMPLATE, random.randint(0, 7))
        return [[digit_map[value - 1] for value in row] for row in transformed]

    def get_extra_generation_rules(self) -> list:
        """Require each highlighted interior window to contain unique digits."""
        windows = []
        for start_row in [1, 5]:
            for start_col in [1, 5]:
                windows.append([(row, col) for row in range(start_row, start_row + 3) for col in range(start_col, start_col + 3)])
        return [TintedGroupRule("Each blue window must contain each digit at most once.", windows, (102, 208, 214, 50))]


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(WindokuSudoku)
