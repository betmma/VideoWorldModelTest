from __future__ import annotations
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048
class Game2048_base(Game2048):
    name = "2048"
        
if __name__ == "__main__":
    from gameRunner import run_human_debug
    run_human_debug(Game2048_base)
