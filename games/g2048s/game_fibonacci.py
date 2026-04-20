from __future__ import annotations
import os
import sys
import random
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048


class GameFibonacci(Game2048):
    name = "Fib Merge"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.target_tile = 2584

    def _can_merge(self, val1: Any, val2: Any) -> bool:
        a, b = sorted((val1, val2))
        if a == 1 and b == 2:
            return True
        return self._next_fib(a) == b

    def _get_merge_result(self, val1: Any, val2: Any) -> tuple[Any, int]:
        new_val = val1 + val2
        return new_val, new_val

    def _get_spawn_value(self) -> Any:
        r = random.random()
        if r < 0.45:
            return 1
        if r < 0.9:
            return 2
        return 3

    def _next_fib(self, n: int) -> int:
        if n <= 1:
            return 1
        a = 1
        b = 1
        while b < n:
            a, b = b, a + b
        return a + b

    def getPrompt(self) -> str:
        return f"This is Fibonacci Merge. Use W/A/S/D or Arrow keys to slide all tiles. Two 1 tiles merge into 2. Otherwise, only consecutive Fibonacci numbers can merge (for example 2+3, 3+5, 13+21). Merges produce the sum. After each valid move, a new 1, 2, or 3 appears. The game ends when there are no valid moves left. Reach the {self.target_tile} tile to win!"


if __name__ == "__main__":
    from pygameRunner import run_human_debug

    run_human_debug(GameFibonacci)
