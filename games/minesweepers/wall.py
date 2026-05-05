import pygame
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase, PatternConstraint

class WallMinesweeper(MinesweeperBase):
    name = "Wall Minesweeper"
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " Each clue lists the lengths of contiguous mine blocks around its eight neighboring cells in circular order."
        
    def get_ordered_neighbors(self, r: int, c: int):
        dirs = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
        adj = []
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                adj.append((nr, nc))
        return adj
        
    def get_blocks(self, mines: list[bool]):
        if not mines: return []
        if sum(mines) == 0: return []
        if sum(mines) == len(mines): return [len(mines)]
        
        idx = mines.index(False)
        shifted = mines[idx:] + mines[:idx]
        
        blocks = []
        count = 0
        for m in shifted:
            if m:
                count += 1
            elif count > 0:
                blocks.append(count)
                count = 0
        if count > 0:
            blocks.append(count)
        
        return sorted(blocks)

    def calculate_clues(self) -> None:
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c].is_mine: continue
                adj = self.get_ordered_neighbors(r, c)
                mines = [self.grid[nr][nc].is_mine for nr, nc in adj]
                blocks = self.get_blocks(mines)
                self.grid[r][c].clue = blocks
                
    def is_empty_clue(self, clue) -> bool:
        return isinstance(clue, list) and len(clue) == 0

    def is_clue_satisfied(self, r: int, c: int) -> bool:
        adj = self.get_ordered_neighbors(r, c)
        flags = [self.grid[nr][nc].flagged for nr, nc in adj]
        return self.get_blocks(flags) == self.grid[r][c].clue

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
                        if self.get_blocks(list(state)) == clue:
                            valid_states.append(state)
                    constraints.append(PatternConstraint(adj, valid_states))
        return constraints
        
    def format_clue(self, clue) -> str:
        return ",".join(map(str, clue))

    def get_clue_font(self, clue):
        if hasattr(self, 'small_font'):
            return self.small_font
        self.small_font = pygame.font.SysFont("consolas", 14, bold=True)
        return self.small_font

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_human_debug(WallMinesweeper)
