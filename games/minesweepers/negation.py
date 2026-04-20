import pygame
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.minesweeper import MinesweeperBase, LinearConstraint

class NegationMinesweeper(MinesweeperBase):
    name = "Negation Minesweeper"
    
    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. "
            "Use Arrow keys to move the cursor. "
            "Press W to reveal a tile. Press S to flag a mine. "
            "When game ends, press A or left arrow key to restart. "
            "[Rule: Negation - Clues equal exact difference in mine counts between colored (+1) and uncolored (-1) cells.]"
        )
        
    def generate_board(self, w: int, h: int) -> bool:
        self.colored = [[(r + c) % 2 == 0 for c in range(w)] for r in range(h)]
        return super().generate_board(w, h)
        
    def calculate_clues(self) -> None:
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c].is_mine: continue
                clue = 0
                for nr, nc in self.get_adjacent(r, c):
                    if self.grid[nr][nc].is_mine:
                        clue += 1 if self.colored[nr][nc] else -1
                self.grid[r][c].clue = clue
                
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
                    weights = {}
                    for nr, nc in adj:
                        weights[(nr, nc)] = 1 if self.colored[nr][nc] else -1
                    constraints.append(LinearConstraint(weights, {self.grid[r][c].clue}))
        return constraints
        
    def draw(self) -> None:
        super().draw()
        board_w = self.grid_w * self.tile_size
        board_h = self.grid_h * self.tile_size
        offset_x = (self.width - board_w) // 2
        offset_y = (self.height - board_h) // 2
        
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.colored[r][c]:
                    x = offset_x + c * self.tile_size
                    y = offset_y + r * self.tile_size
                    rect = pygame.Rect(x+2, y+2, self.tile_size-4, self.tile_size-4)
                    surf = pygame.Surface((self.tile_size-4, self.tile_size-4), pygame.SRCALPHA)
                    surf.fill((255, 100, 100, 40))
                    self.screen.blit(surf, rect.topleft)

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(NegationMinesweeper)