import random
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase, SumConstraint

class QuadMinesweeper(MinesweeperBase):
    name = "Quad Minesweeper"
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " [Rule: Quad - At least 1 mine in every 2x2 area.]"
        
    def generate_board(self, w: int, h: int) -> bool:
        super().generate_board(w, h)
        # Enforce Quad constraint
        for r in range(h - 1):
            for c in range(w - 1):
                area = [(r, c), (r+1, c), (r, c+1), (r+1, c+1)]
                mines = sum(1 for ar, ac in area if self.grid[ar][ac].is_mine)
                if mines == 0:
                    mr, mc = random.choice(area)
                    self.grid[mr][mc].is_mine = True
        self.calculate_clues()
        return True
        
    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = super().get_active_constraints(revealed_state, flagged_state)
        # Add Quad constraints
        for r in range(self.grid_h - 1):
            for c in range(self.grid_w - 1):
                area = {(r, c), (r+1, c), (r, c+1), (r+1, c+1)}
                constraints.append(SumConstraint(area, {1, 2, 3, 4}))
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from gameRunner import run_human_debug, run_autoplay
    run_human_debug(QuadMinesweeper)