from __future__ import annotations

import os
import sys
import random

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class Tile:
    def __init__(self, r: int, c: int) -> None:
        self.r = r
        self.c = c

    def can_enter(self, game: MazeGame, from_r: int, from_c: int) -> bool:
        """Return True if the player can move into this tile."""
        return True

    def on_enter(self, game: MazeGame, from_r: int, from_c: int) -> None:
        """Called immediately after the player finishes moving into this tile."""
        pass

    def on_collide(self, game: MazeGame, from_r: int, from_c: int) -> None:
        """Called when the player tries to move into this tile but can_enter returns False."""
        pass

    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        """Draw the tile onto the screen."""
        pass


class EmptyTile(Tile):
    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(screen, (220, 220, 220), rect)
        pygame.draw.rect(screen, (200, 200, 200), rect, 1)


class WallTile(Tile):
    def can_enter(self, game: MazeGame, from_r: int, from_c: int) -> bool:
        return False

    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(screen, (80, 80, 80), rect)
        pygame.draw.rect(screen, (60, 60, 60), rect, 2)


class GoalTile(Tile):
    def on_enter(self, game: MazeGame, from_r: int, from_c: int) -> None:
        game.win = True

    def draw(self, screen: pygame.Surface, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(screen, (50, 200, 50), rect)
        pygame.draw.rect(screen, (30, 160, 30), rect, 2)


class MazeGame(GameBase):
    name = "Maze"
    variantsPath = "mazes"

    def __init__(self, headless: bool = False) -> None:
        self.tile_size = 40
        self.move_anim_total_frames = 6
        self.end_screen_auto_reset = 120
        super().__init__(headless=headless)
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

    def reset(self) -> None:
        self.grid: list[list[Tile]] = []
        self.player_r = 1
        self.player_c = 1
        self.player_start_r = 1
        self.player_start_c = 1
        self.player_target_r = 1
        self.player_target_c = 1
        self.player_display_r = 1.0
        self.player_display_c = 1.0
        
        self.last_move_dr = 0
        self.last_move_dc = 0

        self.is_moving = False
        self.move_anim_frame = 0
        self.win = False
        self.end_screen_frames = 0
        self.frame_index = 0
        self.end_reported = False
        self.end_event_pending = False
        self.auto_plan: list[str] = []

        self._create_level()

    def _create_level(self) -> None:
        """
        Default simple level. 
        Variants can override this or simply call self.load_from_map(level_map) with custom maps.
        
        NOTE ON PROCEDURAL GENERATION & FAKE DIFFICULTY:
        When implementing procedural generation in subclasses (like IceMazeGame or ColorMazeGame), 
        a great way to ensure high difficulty is to use BFS to find the farthest reachable tile 
        and place the GoalTile there.
        
        However, BEWARE OF "FAKE DIFFICULTY" (The Intercept Bug):
        Since GoalTile typically ignores movement constraints (like sliding mechanics or color matching),
        converting a highly constrained "farthest tile" into a GoalTile can inadvertently create shortcuts.
        For example, an adjacent tile might suddenly become a valid entry point into the GoalTile,
        short-circuiting your complex 40-move puzzle into a 5-move puzzle.
        
        Best Practice:
        1. Find the hardest tile via BFS and temporarily place the GoalTile there.
        2. Re-run your `_build_auto_plan` BFS to calculate the TRUE shortest path with the GoalTile in place.
        3. If the true path is shorter than your minimum difficulty threshold, discard and regenerate!
        """
        level_map = self.generate_maze(21, 15)
        self.load_from_map(level_map)

    def generate_maze(self, width: int, height: int) -> list[str]:
        width = width if width % 2 == 1 else width + 1
        height = height if height % 2 == 1 else height + 1

        maze = [['#' for _ in range(width)] for _ in range(height)]
        directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        
        start_r, start_c = 1, 1
        maze[start_r][start_c] = ' '
        stack = [(start_r, start_c)]
        
        while stack:
            r, c = stack[-1]
            random.shuffle(directions)
            carved = False
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 < nr < height - 1 and 0 < nc < width - 1 and maze[nr][nc] == '#':
                    maze[r + dr // 2][c + dc // 2] = ' '
                    maze[nr][nc] = ' '
                    stack.append((nr, nc))
                    carved = True
                    break
            if not carved:
                stack.pop()

        maze[1][1] = 'P'
        maze[height - 2][width - 2] = 'G'
        return ["".join(row) for row in maze]

    def load_from_map(self, level_map: list[str]) -> None:
        self.grid_h = len(level_map)
        self.grid_w = len(level_map[0]) if self.grid_h > 0 else 0
        self.grid = []
        for r, row in enumerate(level_map):
            grid_row = []
            for c, char in enumerate(row):
                tile = self.create_tile_from_char(char, r, c)
                grid_row.append(tile)
                if char == 'P':
                    self.player_r = r
                    self.player_c = c
                    self.player_start_r = r
                    self.player_start_c = c
                    self.player_target_r = r
                    self.player_target_c = c
                    self.player_display_r = float(r)
                    self.player_display_c = float(c)
            self.grid.append(grid_row)

    def create_tile_from_char(self, char: str, r: int, c: int) -> Tile:
        """Helper to let variants easily add custom tile mappings."""
        if char == '#':
            return WallTile(r, c)
        elif char == 'G':
            return GoalTile(r, c)
        else:
            return EmptyTile(r, c)

    def try_move(self, dr: int, dc: int) -> bool:
        if self.is_moving or self.win:
            return False

        target_r = self.player_r + dr
        target_c = self.player_c + dc

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

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1

        pressed_action = self.BLANK_ACTION.copy()
        if hasattr(self, "prev_action"):
            for k, v in action.items():
                if v and not self.prev_action.get(k, False):
                    pressed_action[k] = True
        self.prev_action = action.copy()

        if self.is_moving:
            self.move_anim_frame += 1
            t = self.move_anim_frame / self.move_anim_total_frames
            t = max(0.0, min(1.0, t))

            self.player_display_r = self.player_start_r + (self.player_target_r - self.player_start_r) * t
            self.player_display_c = self.player_start_c + (self.player_target_c - self.player_start_c) * t

            if self.move_anim_frame >= self.move_anim_total_frames:
                self.is_moving = False
                self.player_display_r = float(self.player_r)
                self.player_display_c = float(self.player_c)
                
                self.grid[self.player_r][self.player_c].on_enter(self, self.player_start_r, self.player_start_c)

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.win and not self.is_moving:
            if not self.end_reported:
                self.end_reported = True
                self.end_event_pending = True

            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        if not self.is_moving and not self.win:
            dr, dc = 0, 0
            if action["W"] or action["LU"]:
                dr = -1
            elif action["S"] or action["LD"]:
                dr = 1
            elif action["A"] or action["LL"]:
                dc = -1
            elif action["D"] or action["LR"]:
                dc = 1

            if dr != 0 or dc != 0:
                if self.try_move(dr, dc):
                    self.auto_plan = []

        return False

    def get_draw_info(self) -> tuple[int, int, int]:
        tile_size = self.tile_size
        board_w = self.grid_w * tile_size
        board_h = self.grid_h * tile_size

        max_w = self.width - 40
        max_h = self.height - 40
        if board_w > max_w or board_h > max_h:
            tile_size = min(max_w // self.grid_w, max_h // self.grid_h)
            board_w = self.grid_w * tile_size
            board_h = self.grid_h * tile_size

        offset_x = (self.width - board_w) // 2
        offset_y = (self.height - board_h) // 2
        return tile_size, offset_x, offset_y

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
        pygame.draw.circle(
            self.screen,
            (50, 150, 255),
            (px + tile_size / 2, py + tile_size / 2),
            tile_size / 2.5
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
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player. "
            "Navigate through the maze and reach the green goal tile to win."
        )

    def getAutoAction(self, frame_index: int) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if frame_index % self.moveInterval != 0:
            return action

        if self.win and not self.is_moving:
            if random.random()<0.2:
                action["A"] = True
            return action

        if self.is_moving:
            return action

        if not self.auto_plan:
            self.auto_plan = self._build_auto_plan()

        if self.auto_plan:
            move = self.auto_plan.pop(0)
            action[move] = True
        else:
            # Random valid move fallback
            moves = ["W", "A", "S", "D"]
            random.shuffle(moves)
            for m in moves:
                dr, dc = 0, 0
                if m == "W": dr = -1
                elif m == "S": dr = 1
                elif m == "A": dc = -1
                elif m == "D": dc = 1
                nr, nc = self.player_r + dr, self.player_c + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    if self.grid[nr][nc].can_enter(self, self.player_r, self.player_c):
                        action[m] = True
                        break

        return action

    def _build_auto_plan(self) -> list[str]:
        queue: list[tuple[int, int, list[str]]] = [(self.player_r, self.player_c, [])]
        visited = set([(self.player_r, self.player_c)])

        while queue:
            r, c, path = queue.pop(0)
            if isinstance(self.grid[r][c], GoalTile):
                return path

            for dr, dc, move_str in [(-1, 0, "W"), (1, 0, "S"), (0, -1, "A"), (0, 1, "D")]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    if (nr, nc) not in visited:
                        if self.grid[nr][nc].can_enter(self, r, c):
                            visited.add((nr, nc))
                            queue.append((nr, nc, path + [move_str]))
        return []


if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(MazeGame)
