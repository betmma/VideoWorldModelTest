from __future__ import annotations

import os
import sys
import random

import pygame

# Allow importing from root directory and games package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from games.maze import MazeGame, Tile, GoalTile


class IceTile(Tile):
    def on_enter(self, game: MazeGame, from_r: int, from_c: int) -> None:
        """Keep sliding in the same direction we were moving."""
        dr = game.last_move_dr
        dc = game.last_move_dc
        
        if dr != 0 or dc != 0:
            game.try_move(dr, dc)
            
    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(screen, (160, 230, 255), rect)  # Bright ice blue
        pygame.draw.rect(screen, (130, 200, 255), rect, 1)


class IceMazeGame(MazeGame):
    name = "Ice Maze"
    
    def create_tile_from_char(self, char: str, r: int, c: int) -> Tile:
        """Map 'I' to IceTile, fallback to base logic for others."""
        if char == 'I':
            return IceTile(r, c)
        return super().create_tile_from_char(char, r, c)

    def _create_level(self) -> None:
        """Generates a mostly ice floor with some safe spots and structured walls, requiring a long path."""
        width = 21
        height = 15
        
        attempts = 0
        min_moves = 13
        
        while True:
            attempts += 1
            if attempts > 200:
                min_moves = max(3, min_moves - 1)
                attempts = 0
                
            # Start with solid ice bordered by walls
            maze = [['I' for _ in range(width)] for _ in range(height)]
            for c in range(width):
                maze[0][c] = '#'
                maze[height - 1][c] = '#'
            for r in range(height):
                maze[r][0] = '#'
                maze[r][width - 1] = '#'
                
            # Place a few "safe spots" (normal empty floor)
            # This satisfies "not all ice" but keeps sliding as the primary mechanic
            for _ in range(6):
                r = random.randint(1, height - 2)
                c = random.randint(1, width - 2)
                maze[r][c] = ' '
                                
            # Place walls as lines (boulders) rather than purely random dots.
            # Fewer obstacles, but they block more, making the puzzle harder.
            num_wall_lines = random.randint(8, 14)
            for _ in range(num_wall_lines):
                r = random.randint(1, height - 2)
                c = random.randint(1, width - 2)
                length = random.randint(1, 4)
                dr, dc = random.choice([(0, 1), (1, 0)])
                for i in range(length):
                    nr, nc = r + dr * i, c + dc * i
                    if 1 <= nr < height - 1 and 1 <= nc < width - 1:
                        if (nr, nc) not in [(1, 1), (1, 2), (2, 1), (2, 2)]:
                            maze[nr][nc] = '#'
                    
            maze[1][1] = 'P'
            
            self.load_from_map(["".join(row) for row in maze])
            
            # Find a candidate farthest tile based on resting spots
            farthest_tile, plan = self.find_farthest_tile_and_path()
            
            fr, fc = farthest_tile
            if (fr, fc) != (1, 1):
                # Place it temporarily to test actual solvability
                old_tile = self.grid[fr][fc]
                self.grid[fr][fc] = GoalTile(fr, fc)
                
                # Check actual shortest path, since the GoalTile might intercept a shorter slide!
                actual_plan = self._build_auto_plan()
                
                # Require the true path to be sufficiently long
                if len(actual_plan) >= min_moves:
                    self.auto_plan = actual_plan
                    break
                else:
                    # Goal could be reached faster by intercepting a slide. Revert and try again!
                    self.grid[fr][fc] = old_tile

    def find_farthest_tile_and_path(self) -> tuple[tuple[int, int], list[str]]:
        """BFS to find the farthest tile taking sliding into account."""
        queue: list[tuple[int, int, list[str]]] = [(self.player_r, self.player_c, [])]
        visited = set([(self.player_r, self.player_c)])
        
        farthest_tile = (self.player_r, self.player_c)
        longest_path = []

        while queue:
            r, c, path = queue.pop(0)
            
            if len(path) > len(longest_path):
                longest_path = path
                farthest_tile = (r, c)

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                cr, cc = r, c
                
                while True:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                        if self.grid[nr][nc].can_enter(self, cr, cc):
                            cr, cc = nr, nc
                            if not isinstance(self.grid[cr][cc], IceTile):
                                break  
                        else:
                            break  
                    else:
                        break  
                        
                if (cr, cc) != (r, c) and (cr, cc) not in visited:
                    visited.add((cr, cc))
                    queue.append((cr, cc, path + [move_str]))
                    
        return farthest_tile, longest_path

    def _build_auto_plan(self) -> list[str]:
        """
        Custom BFS that understands sliding mechanics to find the solution.
        """
        queue: list[tuple[int, int, list[str]]] = [(self.player_r, self.player_c, [])]
        visited = set([(self.player_r, self.player_c)])

        while queue:
            r, c, path = queue.pop(0)
            if isinstance(self.grid[r][c], GoalTile):
                return path

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                cr, cc = r, c
                
                # Simulate sliding in the chosen direction
                while True:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                        if self.grid[nr][nc].can_enter(self, cr, cc):
                            cr, cc = nr, nc
                            if isinstance(self.grid[cr][cc], GoalTile):
                                break  # We stop if we hit the goal
                            if not isinstance(self.grid[cr][cc], IceTile):
                                break  # We stop sliding if we land on a non-ice tile (e.g. EmptyTile)
                        else:
                            break  # Hit a wall, stop sliding
                    else:
                        break  # Out of bounds
                        
                # Only add to queue if we actually moved to a new resting spot
                if (cr, cc) != (r, c) and (cr, cc) not in visited:
                    visited.add((cr, cc))
                    queue.append((cr, cc, path + [move_str]))
                    
        return []

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move. "
            "You will slide continuously on the ice until you hit a wall or reach the green goal!"
        )


if __name__ == "__main__":
    # Allow testing directly
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from gameRunner import run_human_debug, run_autoplay
    run_autoplay(IceMazeGame)
