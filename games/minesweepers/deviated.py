import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.minesweeper import MinesweeperBase

class DeviatedMinesweeper(MinesweeperBase):
    name = "Deviated Minesweeper"
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " Each clue counts mines in the 3 by 3 area centered one tile above the clue, excluding the clue tile itself."
        
    def get_adjacent(self, r: int, c: int) -> list[tuple[int, int]]:
        adj = []
        center_r = r - 1
        center_c = c
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                nr, nc = center_r + dr, center_c + dc
                if (nr, nc) != (r, c) and 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    adj.append((nr, nc))
        return adj

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(DeviatedMinesweeper)
