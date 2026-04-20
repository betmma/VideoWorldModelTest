import random
import pygame
import math,sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


from games.maze import MazeGame, Tile, EmptyTile, WallTile, GoalTile


class JumpPadTile(Tile):
    def __init__(self, r: int, c: int, new_step_size: int) -> None:
        super().__init__(r, c)
        self.new_step_size = new_step_size

    def on_enter(self, game: 'JumpMazeGame', from_r: int, from_c: int) -> None:
        game.player_step_size = self.new_step_size

    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        # Distinct background color (light gold/yellow)
        pygame.draw.rect(screen, (255, 230, 150), rect)
        pygame.draw.rect(screen, (200, 180, 100), rect, 1)

        # Draw the number
        font = pygame.font.SysFont("consolas", int(size * 0.6), bold=True)
        txt = font.render(str(self.new_step_size), True, (100, 80, 20))
        tr = txt.get_rect(center=(x + size // 2, y + size // 2))
        screen.blit(txt, tr)


class JumpMazeGame(MazeGame):
    name = "Jump Maze"

    def reset(self) -> None:
        self.player_step_size = 1
        super().reset()
        
    def try_move(self, dr: int, dc: int) -> bool:
        if self.is_moving or self.win:
            return False

        # Jumps exactly step_size tiles
        target_r = self.player_r + dr * self.player_step_size
        target_c = self.player_c + dc * self.player_step_size

        if target_r < 0 or target_r >= self.grid_h or target_c < 0 or target_c >= self.grid_w:
            return False

        target_tile = self.grid[target_r][target_c]
        if target_tile.can_enter(self, self.player_r, self.player_c):
            self.player_start_r = self.player_r
            self.player_start_c = self.player_c
            self.player_r = target_r
            self.player_c = target_c
            self.player_target_r = target_r
            self.player_target_c = target_c

            self.last_move_dr = dr
            self.last_move_dc = dc

            self.is_moving = True
            self.move_anim_frame = 0
            return True
        else:
            target_tile.on_collide(self, self.player_r, self.player_c)
            return False

    def draw(self) -> None:
        self.screen.fill((40, 40, 45))

        tile_size, offset_x, offset_y = self.get_draw_info()

        for r in range(self.grid_h):
            for c in range(self.grid_w):
                x = offset_x + c * tile_size
                y = offset_y + r * tile_size
                self.grid[r][c].draw(self.screen, x, y, tile_size)

        px = offset_x + self.player_display_c * tile_size
        py = offset_y + self.player_display_r * tile_size
        
        # Parabolic jump offset
        height_offset = 0
        if self.is_moving:
            t = self.move_anim_frame / self.move_anim_total_frames
            t = max(0.0, min(1.0, t))
            # 4 * t * (1 - t) gives a parabola from 0 to 1 to 0
            # Scale height by distance jumped to make long jumps higher
            distance = max(abs(self.player_target_r - self.player_start_r), abs(self.player_target_c - self.player_start_c))
            if distance > 1:
                max_height = distance * tile_size * 0.5
                height_offset = 4 * t * (1 - t) * max_height

        py -= height_offset

        # Player character
        pygame.draw.circle(
            self.screen,
            (50, 150, 255),
            (px + tile_size / 2, py + tile_size / 2),
            tile_size / 2.5
        )
        
        # Draw current step size on player
        font = pygame.font.SysFont("consolas", int(tile_size * 0.5), bold=True)
        txt = font.render(str(self.player_step_size), True, (255, 255, 255))
        tr = txt.get_rect(center=(px + tile_size // 2, py + tile_size // 2))
        self.screen.blit(txt, tr)

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
            "You jump exactly a number of tiles equal to your step size (shown on the player). "
            "Step on numbered gold tiles to change your step size. Reach the green goal to win."
        )

    def _create_level(self) -> None:
        width = random.randint(16,24)
        height = random.randint(12,15)
        
        start_r, start_c = 1, 1
        
        self.player_r = start_r
        self.player_c = start_c
        self.player_start_r = start_r
        self.player_start_c = start_c
        self.player_target_r = start_r
        self.player_target_c = start_c
        self.player_display_r = float(start_r)
        self.player_display_c = float(start_c)
        self.player_step_size = 1
        
        attempts = 0
        min_change_step_size = 4
        
        while True:
            attempts += 1
            if attempts > 200:
                min_change_step_size = max(1, min_change_step_size - 1)
                attempts = 0
                
            maze = [[' ' for _ in range(width)] for _ in range(height)]
            for c in range(width):
                maze[0][c] = '#'
                maze[height - 1][c] = '#'
            for r in range(height):
                maze[r][0] = '#'
                maze[r][width - 1] = '#'
                
            # Random physical walls
            for _ in range(int(width * height * 0.42)):
                r = random.randint(1, height - 2)
                c = random.randint(1, width - 2)
                if (r, c) not in [(start_r, start_c)]:
                    maze[r][c] = '#'

            self.grid_h = height
            self.grid_w = width
            self.grid = [[None for _ in range(width)] for _ in range(height)]
            
            for r in range(height):
                for c in range(width):
                    if maze[r][c] == '#':
                        self.grid[r][c] = WallTile(r, c)
                    else:
                        if random.random() < 0.18 and (r, c) != (start_r, start_c):
                            self.grid[r][c] = JumpPadTile(r, c, random.randint(1, 4))
                        else:
                            self.grid[r][c] = EmptyTile(r, c)
                            
            farthest_tile, plan = self.find_farthest_tile_and_path()
            
            if plan and self.count_step_changes(plan) >= min_change_step_size:
                fr, fc = farthest_tile
                old_tile = self.grid[fr][fc]
                self.grid[fr][fc] = GoalTile(fr, fc)
                
                actual_plan = self._build_auto_plan()
                
                if actual_plan and self.count_step_changes(actual_plan) >= min_change_step_size:
                    self.auto_plan = actual_plan
                    break
                else:
                    self.grid[fr][fc] = old_tile

    def count_step_changes(self, plan: list[str]) -> int:
        r, c = self.player_start_r, self.player_start_c
        step = 1
        changes = 0
        for move in plan:
            dr, dc = 0, 0
            if move == 'W': dr = -1
            elif move == 'S': dr = 1
            elif move == 'A': dc = -1
            elif move == 'D': dc = 1
            
            r += dr * step
            c += dc * step
            
            tile = self.grid[r][c]
            if isinstance(tile, JumpPadTile):
                if tile.new_step_size != step:
                    changes += 1
                    step = tile.new_step_size
        return changes

    def find_farthest_tile_and_path(self) -> tuple[tuple[int, int], list[str]]:
        queue = [(self.player_start_r, self.player_start_c, 1, [])]
        visited = set([(self.player_start_r, self.player_start_c, 1)])
        
        farthest_tile = (self.player_start_r, self.player_start_c)
        longest_path = []

        while queue:
            r, c, step, path = queue.pop(0)
            
            if len(path) > len(longest_path):
                longest_path = path
                farthest_tile = (r, c)

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                nr = r + dr * step
                nc = c + dc * step
                
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    target_tile = self.grid[nr][nc]
                    
                    if not isinstance(target_tile, WallTile):
                        next_step = step
                        if isinstance(target_tile, JumpPadTile):
                            next_step = target_tile.new_step_size
                            
                        if (nr, nc, next_step) not in visited:
                            visited.add((nr, nc, next_step))
                            queue.append((nr, nc, next_step, path + [move_str]))
                            
        return farthest_tile, longest_path

    def _build_auto_plan(self) -> list[str]:
        queue = [(self.player_r, self.player_c, self.player_step_size, [])]
        visited = set([(self.player_r, self.player_c, self.player_step_size)])

        while queue:
            r, c, step, path = queue.pop(0)
            
            if isinstance(self.grid[r][c], GoalTile):
                return path

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                nr = r + dr * step
                nc = c + dc * step
                
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    target_tile = self.grid[nr][nc]
                    if target_tile.can_enter(self, r, c):
                        next_step = step
                        if isinstance(target_tile, JumpPadTile):
                            next_step = target_tile.new_step_size
                            
                        if (nr, nc, next_step) not in visited:
                            visited.add((nr, nc, next_step))
                            queue.append((nr, nc, next_step, path + [move_str]))
                            
        return []

if __name__ == "__main__":
    # Allow testing directly
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(JumpMazeGame)