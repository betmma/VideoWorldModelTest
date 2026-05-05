from __future__ import annotations

import os
import sys
import random
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048


class GamePower3_5x5_3way(Game2048):
    name = "Power of 3 (5x5 Triple Merge)"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.grid_size = 5
        self.target_tile = 59049
        self.reset()

    def _can_multi_merge(self, values: list[Any]) -> bool:
        return len(values) == 3 and values[0] == values[1] == values[2]

    def _get_multi_merge_result(self, values: list[Any]) -> tuple[Any, int]:
        new_val = values[0] * 3
        return new_val, new_val

    def _get_spawn_value(self) -> Any:
        return 3 if random.random() < 0.8 else 9

    def getPrompt(self) -> str:
        return f"This is 5x5 Power of 3 Triple Merge. Use W/A/S/D or Arrow keys to slide all tiles in one direction. Exactly three adjacent equal-numbered tiles merge into one tile with triple value. After each valid move, a new 3 tile appears most of the time, and a 9 tile appears occasionally. The game ends when there are no valid moves left. Reach the {self.target_tile} tile to win!"


if __name__ == "__main__":
    from pygameRunner import run_human_debug

    run_human_debug(GamePower3_5x5_3way)
