import random
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.minesweeper import MinesweeperBase, SumConstraint

class HorizontalMinesweeper(MinesweeperBase):
    name = "Horizontal Minesweeper"
    
    def __init__(self, headless: bool = False):
        super().__init__(headless=headless)
        self.mine_density = 0.4
        
    def getPrompt(self) -> str:
        return super().getPrompt() + " Every mine has at least one mine immediately to its left or right."
        
    def generate_board(self, w: int, h: int) -> bool:
        self.grid_w = w
        self.grid_h = h
        from games.minesweeper import Cell
        self.grid = [[Cell(r, c) for c in range(w)] for r in range(h)]
        
        num_mines = max(2, int(w * h * self.mine_density))
        cells = [(r, c) for r in range(h) for c in range(w-1)]
        random.shuffle(cells)
        mines_placed = 0
        for r, c in cells:
            if not self.grid[r][c].is_mine and not self.grid[r][c+1].is_mine:
                self.grid[r][c].is_mine = True
                self.grid[r][c+1].is_mine = True
                mines_placed += 2
            if mines_placed >= num_mines:
                break
        self.calculate_clues()
        return True
        
    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = super().get_active_constraints(revealed_state, flagged_state)
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if flagged_state[r][c]:
                    adj = []
                    if c - 1 >= 0: adj.append((r, c - 1))
                    if c + 1 < self.grid_w: adj.append((r, c + 1))
                    constraints.append(SumConstraint(set(adj), {1, 2}))
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(HorizontalMinesweeper)
