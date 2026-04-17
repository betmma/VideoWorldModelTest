from __future__ import annotations
import os
import sys
import importlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.g2048 import Game2048

class Game2048_3x3(Game2048):
    name = "256"

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.grid_size = 3
        self.target_tile = 256
        self.reset()
        
if __name__ == "__main__":
    from gameRunner import run_human_debug
    run_human_debug(Game2048_3x3)
