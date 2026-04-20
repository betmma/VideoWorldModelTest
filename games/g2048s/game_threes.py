from __future__ import annotations
import os
import sys
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048
from typing import Any

class GameThrees(Game2048):
    name = "Threes"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.target_tile = 0 # No specific win condition by value

    def _can_merge(self, val1: Any, val2: Any) -> bool:
        if (val1 == 1 and val2 == 2) or (val1 == 2 and val2 == 1):
            return True
        if isinstance(val1, int) and val1 >= 3 and val1 == val2:
            return True
        return False

    def _get_merge_result(self, val1: Any, val2: Any) -> tuple[Any, int]:
        if isinstance(val1, int) and isinstance(val2, int):
            new_val = val1 + val2
            return new_val, new_val
        return val1, 0

    def _get_spawn_value(self) -> Any:
        return 1 if random.random() < 0.5 else 2

    def getPrompt(self) -> str:
        return "This is Threes. Use W/A/S/D or Arrow keys to slide all tiles in one direction. 1 and 2 merge to 3. 3 and 3 merge to 6. Pairs of numbers >= 3 can merge if they are the same.The game ends when there are no valid moves left."

if __name__ == "__main__":
    from pygameRunner import run_human_debug
    run_human_debug(GameThrees)
