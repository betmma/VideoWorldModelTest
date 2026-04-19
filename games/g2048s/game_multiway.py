from __future__ import annotations

import os
import sys
import random
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048


class GameMultiway(Game2048):
    name = "144"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.grid_size = 5
        self.target_tile = 144
        self.reset()

    def _can_multi_merge(self, values: list[Any]) -> bool:
        return len(values) >=2 and all(v == values[0] for v in values)

    def _get_multi_merge_result(self, values: list[Any]) -> tuple[Any, int]:
        new_val = sum(values)
        return new_val, new_val

    def _get_spawn_value(self) -> Any:
        return 1
    
    def _get_tile_color(self, value):
        if self.target_tile%value!=0: # cannot merge into target tile, use gray color
            return (120,120,120)
        return super()._get_tile_color(value)
    
    def getPrompt(self) -> str:
        return f"This is {self.target_tile}. Use W/A/S/D or Arrow keys to slide all tiles in one direction. Arbitrary number of adjacent equal-numbered tiles merge into one tile with sum value. After each valid move, a new 1 tile appears in an empty cell. The game ends when there are no valid moves left. Reach the {self.target_tile} tile to win! Tiles not able to merge into the {self.target_tile} tile will be displayed in gray."
    
    def _evaluate_board(self, board, gained, direction):
        gray_tiles = sum(1 for row in board for val in row if val > 0 and self.target_tile % val != 0)
        return super()._evaluate_board(board, gained, direction) - gray_tiles * 90000


if __name__ == "__main__":
    from gameRunner import run_human_debug,run_autoplay

    run_human_debug(GameMultiway)
