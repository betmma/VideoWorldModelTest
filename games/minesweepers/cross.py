import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase

class CrossMinesweeper(MinesweeperBase):
    name = "Cross Minesweeper"
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " Each clue counts mines in a plus-shaped area up to two tiles away horizontally and vertically."
        
    def get_adjacent(self, r: int, c: int) -> list[tuple[int, int]]:
        adj = []
        for dr, dc in [(-1, 0), (-2, 0), (1, 0), (2, 0), (0, -1), (0, -2), (0, 1), (0, 2)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                adj.append((nr, nc))
        return adj

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(CrossMinesweeper)
