import pygame
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.minesweeper import MinesweeperBase, PatternConstraint

class PartitionMinesweeper(MinesweeperBase):
    name = "Partition Minesweeper"
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " [Rule: Partition - Clue counts the number of separate islands of consecutive mines among the 8 neighbors.]"
        
    def get_ordered_neighbors(self, r: int, c: int):
        dirs = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
        adj = []
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                adj.append((nr, nc))
        return adj
        
    def get_groups(self, mines: list[bool]) -> int:
        if not mines or sum(mines) == 0: return 0
        if sum(mines) == len(mines): return 1
        idx = mines.index(False)
        shifted = mines[idx:] + mines[:idx]
        count = 0
        in_group = False
        for m in shifted:
            if m and not in_group:
                count += 1
                in_group = True
            elif not m:
                in_group = False
        return count

    def calculate_clues(self) -> None:
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c].is_mine: continue
                adj = self.get_ordered_neighbors(r, c)
                mines = [self.grid[nr][nc].is_mine for nr, nc in adj]
                self.grid[r][c].clue = self.get_groups(mines)

    def is_clue_satisfied(self, r: int, c: int) -> bool:
        adj = self.get_ordered_neighbors(r, c)
        flags = [self.grid[nr][nc].flagged for nr, nc in adj]
        if self.get_groups(flags) != self.grid[r][c].clue:
            return False
            
        hidden = [i for i, (nr, nc) in enumerate(adj) if not self.grid[nr][nc].revealed and not self.grid[nr][nc].flagged]
        if not hidden:
            return True
            
        for i in range(1, 1 << len(hidden)):
            test_flags = list(flags)
            for j, h_idx in enumerate(hidden):
                if (i >> j) & 1:
                    test_flags[h_idx] = True
            if self.get_groups(test_flags) == self.grid[r][c].clue:
                return False
                
        return True

    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = []
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if revealed_state[r][c]:
                    clue = self.grid[r][c].clue
                    if self.is_empty_clue(clue):
                        continue
                    adj = self.get_ordered_neighbors(r, c)
                    n = len(adj)
                    valid_states = []
                    for i in range(1 << n):
                        state = tuple(bool((i >> j) & 1) for j in range(n))
                        if self.get_groups(list(state)) == clue:
                            valid_states.append(state)
                    constraints.append(PatternConstraint(adj, valid_states))
        return constraints

if __name__ == "__main__":
    # Allow testing directly
    from gameRunner import run_human_debug, run_autoplay
    run_autoplay(PartitionMinesweeper)
