import random
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase, SumConstraint

class LiarMinesweeper(MinesweeperBase):
    name = "Liar Minesweeper"
    
    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. "
            "Use Arrow keys to move the cursor. "
            "Press W to reveal a tile. Press S to flag a mine. "
            "When game ends, press A or left arrow key to restart. "
            "[Rule: Liar - Clues are exactly +1 or -1 from the true value.]"
        )
        
    def calculate_clues(self) -> None:
        super().calculate_clues()
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c].is_mine: continue
                diff = random.choice([-1, 1])
                self.grid[r][c].clue += diff
                if self.grid[r][c].clue < 0:
                    self.grid[r][c].clue -= diff*2
                
    def can_auto_reveal(self, r: int, c: int) -> bool:
        return False
        
    def can_fast_open(self, r: int, c: int) -> bool:
        return False
        
    def is_empty_clue(self, clue) -> bool:
        return False
        
    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = []
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if revealed_state[r][c]:
                    adj = self.get_adjacent(r, c)
                    clue = self.grid[r][c].clue
                    allowed = {max(0, clue - 1), clue + 1}
                    constraints.append(SumConstraint(set(adj), allowed))
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from gameRunner import run_human_debug, run_autoplay
    run_autoplay(LiarMinesweeper)