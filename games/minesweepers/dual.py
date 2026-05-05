import random
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase, SumConstraint, Cell

class DualMinesweeper(MinesweeperBase):
    name = "Dual Minesweeper"
    def __init__(self, headless: bool = False):
        super().__init__(headless=headless)
        self.mine_density = 0.4
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " Every mine touches exactly one other mine orthogonally."
        
    def generate_board(self, w: int, h: int) -> bool:
        self.grid_w = w
        self.grid_h = h
        self.grid = [[Cell(r, c) for c in range(w)] for r in range(h)]
        
        num_pairs = max(1, int(w * h * self.mine_density / 2))
        cells = [(r, c) for r in range(h) for c in range(w)]
        random.shuffle(cells)
        
        pairs = []
        for r, c in cells:
            if any(abs(r-pr) <= 1 and abs(c-pc) <= 1 for p in pairs for pr, pc in p):
                continue # prevent touching
            # Try to form a pair
            dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]
            random.shuffle(dirs)
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    if not any(abs(nr-pr) <= 1 and abs(nc-pc) <= 1 for p in pairs for pr, pc in p):
                        pairs.append(((r, c), (nr, nc)))
                        self.grid[r][c].is_mine = True
                        self.grid[nr][nc].is_mine = True
                        break
            if len(pairs) >= num_pairs:
                break
        
        self.calculate_clues()
        return True
        
    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = super().get_active_constraints(revealed_state, flagged_state)
        # Dual constraints
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if flagged_state[r][c]:
                    # orthogonal neighbors
                    adj = []
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                            adj.append((nr, nc))
                    constraints.append(SumConstraint(set(adj), {1}))
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(DualMinesweeper)
