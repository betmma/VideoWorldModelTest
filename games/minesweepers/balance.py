import random
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.minesweeper import MinesweeperBase, SumConstraint

class BalanceMinesweeper(MinesweeperBase):
    name = "Balance Minesweeper"
    
    def __init__(self, headless: bool = False):
        super().__init__(headless=headless)
        self.mine_density = 0.4
        
    def getPrompt(self) -> str:
        return super().getPrompt() + " [Rule: Balance - Square grid, and every row/col has exact same number of mines. Constraints added dynamically.]"
        
    def generate_board(self, w: int, h: int) -> bool:
        self.grid_w = self.grid_h = max(w, h)
        w = h = self.grid_w
        from games.minesweeper import Cell
        
        k = max(1, int(w * self.mine_density))
        self.mines_per_line = k
        
        base = [True] * k + [False] * (w - k)
        random.shuffle(base)
        rowmap = [i for i in range(h)]
        colmap = [i for i in range(w)]
        random.shuffle(rowmap)
        random.shuffle(colmap)
        self.grid = [[Cell(r, c) for c in range(w)] for r in range(h)]
        for r in range(h):
            for c in range(w):
                self.grid[r][c].is_mine = base[(colmap[c] - rowmap[r]) % w]
                
        # shuffle rows
        random.shuffle(self.grid)
        # shuffle columns
        col_indices = list(range(w))
        random.shuffle(col_indices)
        for r in range(h):
            self.grid[r] = [self.grid[r][c] for c in col_indices]
            for c in range(w):
                self.grid[r][c].r = r
                self.grid[r][c].c = c
                
        self.calculate_clues()
        return True

    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = super().get_active_constraints(revealed_state, flagged_state)
        w, h = self.grid_w, self.grid_h
        k = None
        for r in range(h):
            if sum(1 for c in range(w) if revealed_state[r][c] or flagged_state[r][c]) == w:
                k = sum(1 for c in range(w) if flagged_state[r][c])
                break
        if k is None:
            for c in range(w):
                if sum(1 for r in range(h) if revealed_state[r][c] or flagged_state[r][c]) == h:
                    k = sum(1 for r in range(h) if flagged_state[r][c])
                    break
                    
        if k is not None:
            for r in range(h):
                constraints.append(SumConstraint({(r, c) for c in range(w)}, {k}))
            for c in range(w):
                constraints.append(SumConstraint({(r, c) for r in range(h)}, {k}))
                
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(BalanceMinesweeper)
