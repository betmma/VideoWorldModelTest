from __future__ import annotations

import os, sys, random, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import SudokuBase
from games.sudokus.rules import region_groups_from_map

TEMPLATE_REGION_MAP = [
    [2, 2, 2, 5, 5, 5, 8, 8, 8],
    [2, 2, 2, 5, 5, 5, 8, 8, 8],
    [2, 2, 1, 5, 5, 4, 8, 8, 7],
    [2, 1, 1, 5, 4, 4, 8, 7, 7],
    [1, 1, 1, 4, 4, 4, 7, 7, 7],
    [1, 1, 0, 4, 4, 3, 7, 7, 6],
    [1, 0, 0, 4, 3, 3, 7, 6, 6],
    [0, 0, 0, 3, 3, 3, 6, 6, 6],
    [0, 0, 0, 3, 3, 3, 6, 6, 6],
]

JIGSAW_TEMPLATE = [
    [7, 8, 1, 9, 5, 4, 6, 3, 2],
    [5, 6, 3, 1, 7, 2, 9, 4, 8],
    [2, 9, 4, 3, 8, 1, 7, 5, 6],
    [4, 5, 7, 6, 3, 8, 1, 2, 9],
    [1, 3, 6, 5, 2, 9, 4, 8, 7],
    [9, 2, 8, 4, 6, 7, 5, 1, 3],
    [8, 4, 2, 7, 9, 5, 3, 6, 1],
    [3, 1, 9, 8, 4, 6, 2, 7, 5],
    [6, 7, 5, 2, 1, 3, 8, 9, 4],
]


def rotate_region_map(region_map: list[list[int]]) -> list[list[int]]:
    """Rotate a region-id map ninety degrees clockwise."""
    side = len(region_map)
    return [[region_map[side - 1 - col][row] for col in range(side)] for row in range(side)]


def flip_region_map(region_map: list[list[int]]) -> list[list[int]]:
    """Mirror a region-id map left to right."""
    return [list(reversed(row)) for row in region_map]


def rotate_board(board: list[list[int]]) -> list[list[int]]:
    """Rotate one solved board ninety degrees clockwise."""
    side = len(board)
    return [[board[side - 1 - col][row] for col in range(side)] for row in range(side)]


def flip_board(board: list[list[int]]) -> list[list[int]]:
    """Mirror one solved board left to right."""
    return [list(reversed(row)) for row in board]


def transform_region_map(region_map: list[list[int]], transform_index: int) -> list[list[int]]:
    """Apply one of eight board symmetries to the region map."""
    transformed = [row[:] for row in region_map]
    if transform_index >= 4:
        transformed = flip_region_map(transformed)
    for _ in range(transform_index % 4):
        transformed = rotate_region_map(transformed)
    return transformed


def transform_board(board: list[list[int]], transform_index: int) -> list[list[int]]:
    """Apply the same board symmetry used by the region map."""
    transformed = [row[:] for row in board]
    if transform_index >= 4:
        transformed = flip_board(transformed)
    for _ in range(transform_index % 4):
        transformed = rotate_board(transformed)
    return transformed


class JigsawSudoku(SudokuBase):
    """Sudoku variant with irregular outlined regions."""

    name = "Jigsaw Sudoku"
    require_unique_solution = False

    def prepare_puzzle_layout(self) -> None:
        """Choose one symmetry of the irregular region map for this puzzle."""
        self.transform_index = random.randint(0, 7)
        self.region_map = transform_region_map(TEMPLATE_REGION_MAP, self.transform_index)

    def choose_target_clues(self) -> int:
        """Use a moderate clue count for the irregular-region constraint."""
        return random.randint(21, 28)

    def generate_solution_board(self) -> list[list[int]]:
        """Build a Jigsaw-valid solution from the transformed template."""
        digit_map = self.digits[:]
        random.shuffle(digit_map)
        transformed = transform_board(JIGSAW_TEMPLATE, self.transform_index)
        return [[digit_map[value - 1] for value in row] for row in transformed]

    def get_region_groups(self) -> list:
        """Return the irregular connected regions for this puzzle."""
        return region_groups_from_map(self.region_map)

    def get_region_prompt_text(self) -> str:
        """Describe the irregular region rule for the prompt."""
        return "Each outlined irregular region must contain each digit at most once."

    def draw_grid_lines(self, cell_size: int, board_left: int, board_top: int) -> None:
        """Draw thin cell lines and thick irregular region borders."""
        board_width = cell_size * self.side
        board_height = cell_size * self.side
        for index in range(self.side + 1):
            y = board_top + index * cell_size
            x = board_left + index * cell_size
            pygame.draw.line(self.screen, (129, 134, 146), (board_left, y), (board_left + board_width, y), 1)
            pygame.draw.line(self.screen, (129, 134, 146), (x, board_top), (x, board_top + board_height), 1)

        for row in range(self.side):
            for col in range(self.side):
                rect = pygame.Rect(board_left + col * cell_size, board_top + row * cell_size, cell_size, cell_size)
                region_id = self.region_map[row][col]
                if row == 0 or self.region_map[row - 1][col] != region_id:
                    pygame.draw.line(self.screen, (63, 68, 79), (rect.left, rect.top), (rect.right, rect.top), 3)
                if col == 0 or self.region_map[row][col - 1] != region_id:
                    pygame.draw.line(self.screen, (63, 68, 79), (rect.left, rect.top), (rect.left, rect.bottom), 3)
                if row == self.side - 1 or self.region_map[row + 1][col] != region_id:
                    pygame.draw.line(self.screen, (63, 68, 79), (rect.left, rect.bottom), (rect.right, rect.bottom), 3)
                if col == self.side - 1 or self.region_map[row][col + 1] != region_id:
                    pygame.draw.line(self.screen, (63, 68, 79), (rect.right, rect.top), (rect.right, rect.bottom), 3)


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    run_autoplay(JigsawSudoku)
