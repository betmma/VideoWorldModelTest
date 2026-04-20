from __future__ import annotations

import os
import sys
import random

import pygame

# Allow importing from root directory and games package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from games.maze import MazeGame, Tile, WallTile, GoalTile


class ColoredEmptyTile(Tile):
    def __init__(self, r: int, c: int, color_idx: int) -> None:
        super().__init__(r, c)
        self.color_idx = color_idx

    def can_enter(self, game: ColorMazeGame, from_r: int, from_c: int) -> bool:
        # Player can only enter if their color matches the tile's color
        return game.player_color == self.color_idx

    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        # Pastel colors: Red, Green, Blue
        colors = [(255, 200, 200), (200, 255, 200), (200, 220, 255)] 
        pygame.draw.rect(screen, colors[self.color_idx], rect)
        pygame.draw.rect(screen, (200, 200, 200), rect, 1)


class ColorTransformTile(Tile):
    def on_enter(self, game: ColorMazeGame, from_r: int, from_c: int) -> None:
        # Cycle the player's color
        game.player_color = (game.player_color + 1) % 3

    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(screen, (230, 230, 230), rect) 
        
        # Draw a multicolored symbol (RGB dots)
        pygame.draw.circle(screen, (255, 50, 50), (x + size//2, y + size//3), size//6)
        pygame.draw.circle(screen, (50, 150, 255), (x + size//3, y + 2*size//3), size//6)
        pygame.draw.circle(screen, (50, 255, 50), (x + 2*size//3, y + 2*size//3), size//6)
        
        pygame.draw.rect(screen, (200, 200, 200), rect, 1)


class ColorMazeGame(MazeGame):
    name = "Color Maze"

    def reset(self) -> None:
        self.player_color = 0 
        super().reset()

    def _create_level(self) -> None:
        width = 21
        height = 15
        
        start_r, start_c = 1, 1
        
        self.player_r = start_r
        self.player_c = start_c
        self.player_start_r = start_r
        self.player_start_c = start_c
        self.player_target_r = start_r
        self.player_target_c = start_c
        self.player_display_r = float(start_r)
        self.player_display_c = float(start_c)
        self.player_color = 0
        
        attempts = 0
        transform_chance = random.random()*0.1+0.1
        min_moves = 30
        
        while True:
            attempts += 1
            if attempts > 200:
                transform_chance = min(0.30, transform_chance + 0.01)
                min_moves = max(10, min_moves - 1)
                attempts = 0
                
            # 1. Start with open room bordered by walls
            maze = [[' ' for _ in range(width)] for _ in range(height)]
            for c in range(width):
                maze[0][c] = '#'
                maze[height - 1][c] = '#'
            for r in range(height):
                maze[r][0] = '#'
                maze[r][width - 1] = '#'
                
            # Random physical walls (sparse)
            for _ in range(int(width * height*(random.random()*0.1+0.1))):
                r = random.randint(1, height - 2)
                c = random.randint(1, width - 2)
                if (r, c) not in [(start_r, start_c), (start_r+1, start_c), (start_r, start_c+1)]:
                    maze[r][c] = '#'

            # 2. Random colors for empty spaces
            colors = [[random.randint(0, 2) for _ in range(width)] for _ in range(height)]
            
            # Cellular automata smoothing (2 iterations) to create organic color blobs
            for _ in range(random.randint(0,1)):
                new_colors = [[colors[r][c] for c in range(width)] for r in range(height)]
                for r in range(1, height - 1):
                    for c in range(1, width - 1):
                        if maze[r][c] == '#': continue
                        
                        counts = [0, 0, 0]
                        for dr, dc in [(0,0), (0,1), (1,0), (0,-1), (-1,0), (1,1), (-1,-1), (1,-1), (-1,1)]:
                            nr, nc = r+dr, c+dc
                            if 0 <= nr < height and 0 <= nc < width and maze[nr][nc] != '#':
                                counts[colors[nr][nc]] += 1
                        max_c = max(counts)
                        best_colors = [i for i, cnt in enumerate(counts) if cnt == max_c]
                        new_colors[r][c] = random.choice(best_colors)
                colors = new_colors
                
            # Guarantee start is color 0
            colors[start_r][start_c] = 0
                
            self.grid_h = height
            self.grid_w = width
            self.grid = [[None for _ in range(width)] for _ in range(height)]
            
            # 3. Populate grid with walls, colors, and transform tiles
            for r in range(height):
                for c in range(width):
                    if maze[r][c] == '#':
                        self.grid[r][c] = WallTile(r, c)
                    else:
                        # Sprinkle transform tiles randomly
                        if random.random() < transform_chance and (r, c) != (start_r, start_c):
                            self.grid[r][c] = ColorTransformTile(r, c)
                        else:
                            self.grid[r][c] = ColoredEmptyTile(r, c, colors[r][c])
                            
            # 4. Use BFS to find the hardest (farthest) tile to reach
            farthest_tile, plan = self.find_farthest_tile_and_path()
            
            fr, fc = farthest_tile
            old_tile = self.grid[fr][fc]
            self.grid[fr][fc] = GoalTile(fr, fc)
            
            # The GoalTile ignores colors! Check the TRUE shortest path 
            # to make sure it didn't create a shortcut from an adjacent mismatched tile.
            actual_plan = self._build_auto_plan()
            
            if actual_plan and len(actual_plan) >= min_moves:
                self.auto_plan = actual_plan
                break
            else:
                self.grid[fr][fc] = old_tile

    def find_farthest_tile_and_path(self) -> tuple[tuple[int, int], list[str]]:
        """Color-aware BFS to find the hardest-to-reach tile."""
        queue = [(self.player_start_r, self.player_start_c, 0, [])]
        visited = set([(self.player_start_r, self.player_start_c, 0)])
        
        farthest_tile = (self.player_start_r, self.player_start_c)
        longest_path = []

        while queue:
            r, c, color, path = queue.pop(0)
            
            if len(path) > len(longest_path):
                longest_path = path
                farthest_tile = (r, c)

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    target_tile = self.grid[nr][nc]
                    
                    if isinstance(target_tile, ColoredEmptyTile):
                        can_enter = (target_tile.color_idx == color)
                    elif isinstance(target_tile, WallTile):
                        can_enter = False
                    else:
                        can_enter = True  # TransformTile
                        
                    if can_enter:
                        next_color = color
                        if isinstance(target_tile, ColorTransformTile):
                            next_color = (color + 1) % 3
                            
                        if (nr, nc, next_color) not in visited:
                            visited.add((nr, nc, next_color))
                            queue.append((nr, nc, next_color, path + [move_str]))
                            
        return farthest_tile, longest_path

    def _build_auto_plan(self) -> list[str]:
        """Color-aware BFS to find the solution for autoplay."""
        queue = [(self.player_r, self.player_c, self.player_color, [])]
        visited = set([(self.player_r, self.player_c, self.player_color)])

        while queue:
            r, c, color, path = queue.pop(0)
            if isinstance(self.grid[r][c], GoalTile):
                return path

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    target_tile = self.grid[nr][nc]
                    
                    # Test if the simulated color can enter the tile
                    if isinstance(target_tile, ColoredEmptyTile):
                        can_enter = (target_tile.color_idx == color)
                    elif isinstance(target_tile, WallTile):
                        can_enter = False
                    else:
                        can_enter = True  # TransformTile, GoalTile, etc.
                        
                    if can_enter:
                        next_color = color
                        if isinstance(target_tile, ColorTransformTile):
                            next_color = (color + 1) % 3
                            
                        if (nr, nc, next_color) not in visited:
                            visited.add((nr, nc, next_color))
                            queue.append((nr, nc, next_color, path + [move_str]))
                            
        return []

    def draw(self) -> None:
        self.screen.fill((40, 40, 45))

        tile_size, offset_x, offset_y = self.get_draw_info()

        # Draw Tiles
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                x = offset_x + c * tile_size
                y = offset_y + r * tile_size
                self.grid[r][c].draw(self.screen, x, y, tile_size)

        # Draw Player
        px = offset_x + self.player_display_c * tile_size
        py = offset_y + self.player_display_r * tile_size
        
        player_colors = [(255, 50, 50), (50, 255, 50), (50, 150, 255)] # Red, Green, Blue
        p_color = player_colors[self.player_color]
        
        pygame.draw.circle(
            self.screen,
            p_color,
            (px + tile_size / 2, py + tile_size / 2),
            tile_size / 2.5
        )
        
        # Draw a little white outline on the player so it stands out
        pygame.draw.circle(
            self.screen,
            (255, 255, 255),
            (px + tile_size / 2, py + tile_size / 2),
            tile_size / 2.5,
            2
        )

        if self.win and not self.is_moving:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))

            font = pygame.font.SysFont("consolas", 42, bold=True)
            txt = font.render("You Win", True, (245, 245, 245))
            self.screen.blit(txt, txt.get_rect(center=(self.width // 2, self.height // 2 - 20)))

            tip_font = pygame.font.SysFont("consolas", 22)
            tip_txt = tip_font.render("Press A / Left Arrow to restart", True, (220, 220, 220))
            self.screen.blit(tip_txt, tip_txt.get_rect(center=(self.width // 2, self.height // 2 + 28)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move. "
            "You can only walk on floors that match your current color. "
            "Step on the multi-colored transform tiles to cycle your color. "
            "Reach the green goal to win!"
        )


if __name__ == "__main__":
    # Allow testing directly
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(ColorMazeGame)
