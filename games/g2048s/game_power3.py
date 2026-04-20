from __future__ import annotations
import os
import sys
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048
from typing import Any


class GamePower3(Game2048):
    name = "Power of 3"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.target_tile = 6561

    def _can_merge(self, val1: Any, val2: Any) -> bool:
        return val1 == val2 and val1 > 0

    def _get_merge_result(self, val1: Any, val2: Any) -> tuple[Any, int]:
        new_val = val1 * 3
        return new_val, new_val

    def _get_spawn_value(self) -> Any:
        return 3 if random.random() < 0.8 else 9

    def getPrompt(self) -> str:
        return f"This is Power of 3. Use W/A/S/D or Arrow keys to slide all tiles. Two equal numbered tiles merge into a tile with triple value. After each valid move, a new 3 tile appears most of the time, and a 9 tile appears occasionally. The game ends when there are no valid moves left. Reach the {self.target_tile} tile to win!"


if __name__ == "__main__":
    from pygameRunner import run_human_debug

    run_human_debug(GamePower3)
