import sys
import os

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase, SumConstraint

class TripletMinesweeper(MinesweeperBase):
    name = "Triplet Minesweeper"

    def __init__(self, headless: bool = False):
        super().__init__(headless=headless)
        self.mine_density = 0.4
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " No three mines can form a straight horizontal, vertical, or diagonal row."
        
    def _has_line_of_3(self) -> bool:
        w, h = self.grid_w, self.grid_h
        for r in range(h):
            for c in range(w):
                if not self.grid[r][c].is_mine: continue
                # Check 4 directions: Right, Down, Diagonal-Right, Diagonal-Left
                dirs = [(0, 1), (1, 0), (1, 1), (1, -1)]
                for dr, dc in dirs:
                    r1, c1 = r + dr, c + dc
                    r2, c2 = r + 2*dr, c + 2*dc
                    if 0 <= r2 < h and 0 <= c2 < w and 0 <= c1 < w:
                        if self.grid[r1][c1].is_mine and self.grid[r2][c2].is_mine:
                            return True
        return False

    def generate_board(self, w: int, h: int) -> bool:
        max_attempts = 100
        for _ in range(max_attempts):
            super().generate_board(w, h)
            if not self._has_line_of_3():
                return True
        return False
        
    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = super().get_active_constraints(revealed_state, flagged_state)
        w, h = self.grid_w, self.grid_h
        for r in range(h):
            for c in range(w):
                dirs = [(0, 1), (1, 0), (1, 1), (1, -1)]
                for dr, dc in dirs:
                    r1, c1 = r + dr, c + dc
                    r2, c2 = r + 2*dr, c + 2*dc
                    if 0 <= r2 < h and 0 <= c2 < w and 0 <= c1 < w:
                        area = {(r, c), (r1, c1), (r2, c2)}
                        constraints.append(SumConstraint(area, {0, 1, 2}))
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_human_debug(TripletMinesweeper)
