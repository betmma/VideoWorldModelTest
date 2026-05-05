import random
import pygame
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.minesweeper import MinesweeperBase, PatternConstraint

class ClassMinesweeper(MinesweeperBase):
    name = "Class Minesweeper"
    
    def getPrompt(self) -> str:
        return super().getPrompt() + " Mines belong to two color groups. Each clue shows the two adjacent mine counts as smaller-larger, ordered by count rather than by color."
        
    def generate_board(self, w: int, h: int) -> bool:
        self.color_map = [[random.choice([0, 1]) for c in range(w)] for r in range(h)]
        return super().generate_board(w, h)
        
    def calculate_clues(self) -> None:
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c].is_mine: continue
                adj = self.get_adjacent(r, c)
                c0 = sum(1 for nr, nc in adj if self.grid[nr][nc].is_mine and self.color_map[nr][nc] == 0)
                c1 = sum(1 for nr, nc in adj if self.grid[nr][nc].is_mine and self.color_map[nr][nc] == 1)
                self.grid[r][c].clue = sorted([c0, c1])
                
    def is_empty_clue(self, clue) -> bool:
        return isinstance(clue, list) and sum(clue) == 0

    def format_clue(self, clue) -> str:
        return f"{clue[0]}-{clue[1]}"

    def is_clue_satisfied(self, r: int, c: int) -> bool:
        adj = self.get_fast_open_adjacent(r, c)
        c0 = sum(1 for nr, nc in adj if self.grid[nr][nc].flagged and self.color_map[nr][nc] == 0)
        c1 = sum(1 for nr, nc in adj if self.grid[nr][nc].flagged and self.color_map[nr][nc] == 1)
        return sorted([c0, c1]) == self.grid[r][c].clue

    def get_active_constraints(self, revealed_state, flagged_state):
        constraints = []
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if revealed_state[r][c] and not self.is_empty_clue(self.grid[r][c].clue):
                    clue = self.grid[r][c].clue
                    adj = self.get_adjacent(r, c)
                    valid_states = []
                    n = len(adj)
                    for i in range(1 << n):
                        state = tuple(bool((i >> j) & 1) for j in range(n))
                        c0 = sum(1 for j, (nr, nc) in enumerate(adj) if state[j] and self.color_map[nr][nc] == 0)
                        c1 = sum(1 for j, (nr, nc) in enumerate(adj) if state[j] and self.color_map[nr][nc] == 1)
                        if sorted([c0, c1]) == clue:
                            valid_states.append(state)
                    constraints.append(PatternConstraint(adj, valid_states))
        return constraints
        
    def draw(self) -> None:
        super().draw()
        board_w = self.grid_w * self.tile_size
        board_h = self.grid_h * self.tile_size
        offset_x = (self.width - board_w) // 2
        offset_y = (self.height - board_h) // 2
        
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.color_map[r][c] == 1:
                    x = offset_x + c * self.tile_size
                    y = offset_y + r * self.tile_size
                    rect = pygame.Rect(x+4, y+4, self.tile_size-8, self.tile_size-8)
                    surf = pygame.Surface((self.tile_size-8, self.tile_size-8), pygame.SRCALPHA)
                    surf.fill((255, 150, 100, 60))
                    self.screen.blit(surf, rect.topleft)

    def get_clue_font(self, clue):
        if not hasattr(self, 'small_font'):
            self.small_font = pygame.font.SysFont("consolas", 14, bold=True)
        return self.small_font

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(ClassMinesweeper)
