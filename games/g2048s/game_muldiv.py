from __future__ import annotations
import os
import sys
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048
from typing import Any

class Game2048_MulDiv(Game2048):
    name = "20x/"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)

    def _can_merge(self, val1: Any, val2: Any) -> bool:
        if val1 == val2 and isinstance(val1, int) and val1 > 0:
            return True
        if isinstance(val1, int) and val1 > 0 and val2 in ("×", "÷"):
            return True
        if isinstance(val2, int) and val2 > 0 and val1 in ("×", "÷"):
            return True
        return False

    def _get_merge_result(self, val1: Any, val2: Any) -> tuple[Any, int]:
        if "×" in (val1, val2): # Multiply tile
            other = val1 if val2 == "×" else val2
            if isinstance(other, int):
                new_val = other * 2
                return new_val, new_val
            
        if "÷" in (val1, val2): # Divide tile
            other = val1 if val2 == "÷" else val2
            if isinstance(other, int):
                if other > 1:
                    return other // 2, 0
                return other, 0
            
        if isinstance(val1, int):
            new_val = val1 * 2
            return new_val, new_val
            
        return val1, 0

    def _get_spawn_value(self) -> Any:
        r = random.random()
        if r < 0.05:
            return "×" # × operator
        if r < 0.10:
            return "÷" # ÷ operator
            
        return 4 if random.random() < 0.1 else 2

    def getPrompt(self) -> str:
        return "This is 2048 with multiply (×) and divide (÷) tiles. Use W/A/S/D or Arrow keys to slide all tiles in one direction. Tiles with the same value merge to double. A × tile merges with any numbered tile and doubles it. A ÷ tile merges with any numbered tile and halves it. The game ends when there are no valid moves left."

if __name__ == "__main__":
    from pygameRunner import run_human_debug
    run_human_debug(Game2048_MulDiv)
