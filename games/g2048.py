'''It's forbidden to check a tile's value if the variant is not introducing the possibility of otherwise case. Like do not check if it's integer if the variant isn't adding string tiles. Do not check if the value is larger than zero if the variant isn't adding negative or zero tiles.'''

from __future__ import annotations

import os
import random
import sys
import math
import colorsys
from collections import defaultdict
from typing import Literal, Any

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gameBase import ActionState, GameBase


Direction = Literal["up", "down", "left", "right"]


class Tile:
    def __init__(self, value: Any, r: int, c: int) -> None:
        self.value = value
        self.r = float(r)
        self.c = float(c)
        self.start_r = float(r)
        self.start_c = float(c)
        self.target_r = float(r)
        self.target_c = float(c)

        self.spawn_anim = 0
        self.merge_anim = 0

        self.to_delete = False
        self.is_visible = True
        self.is_moving = False

    def move_to(self, r: int, c: int) -> None:
        self.start_r = self.r
        self.start_c = self.c
        self.target_r = float(r)
        self.target_c = float(c)
        if self.start_r != self.target_r or self.start_c != self.target_c:
            self.is_moving = True

    def update_movement(self, t: float) -> None:
        if not self.is_moving:
            self.r = self.target_r
            self.c = self.target_c
            return

        self.r = self.start_r + (self.target_r - self.start_r) * t
        self.c = self.start_c + (self.target_c - self.start_c) * t

        if t >= 1.0:
            self.r = self.target_r
            self.c = self.target_c
            self.is_moving = False

    def update_animations(self) -> None:
        if self.spawn_anim > 0 and self.is_visible:
            self.spawn_anim -= 1
        if self.merge_anim > 0 and self.is_visible:
            self.merge_anim -= 1

    def draw(
        self,
        screen: pygame.Surface,
        board_x: int,
        board_y: int,
        tile_size: int,
        padding: int,
        palette: dict[str, tuple[int, int, int] | float | bool],
        tile_color: tuple[int, int, int],
    ) -> None:
        if not self.is_visible:
            return

        x = board_x + padding + self.c * (tile_size + padding)
        y = board_y + padding + self.r * (tile_size + padding)

        anim_val = max(self.spawn_anim, self.merge_anim)
        scale = 1.0 + 0.15 * (anim_val / 8.0) if anim_val > 0 else 1.0

        tw = int(tile_size * scale)
        th = int(tile_size * scale)
        tx = x + (tile_size - tw) / 2
        ty = y + (tile_size - th) / 2

        tile_rect = pygame.Rect(int(tx), int(ty), tw, th)
        pygame.draw.rect(screen, tile_color, tile_rect, border_radius=8)

        font_size = 42 if isinstance(self.value, int) and self.value < 100 else 36 if isinstance(self.value, int) and self.value < 1000 else 28
        font = pygame.font.SysFont("consolas", font_size, bold=True)
        
        display_text = str(self.value)
        text = font.render(display_text, True, palette["text"])
        text_rect = text.get_rect(center=tile_rect.center)
        screen.blit(text, text_rect)


class Game2048(GameBase):
    name = "2048"
    variantsPath= "g2048s"
    def __init__(self, headless: bool = False) -> None:
        # Configuration & Constants
        self.grid_size = 4
        self.padding = 18
        self.end_screen_auto_reset = 120
        self.target_tile = 2048
        self.move_anim_total_frames = 6
        self.high_score = 0  # Must be initialized before reset() uses it
        
        # Initialization
        super().__init__(headless=headless)
        self.palette = self._make_palette()
        self.prev_action = self.BLANK_ACTION.copy()
        
        # All state variables (board, score, tiles, etc.) are set here
        self.reset()

    def reset(self) -> None:
        self.board = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.tiles = []
        self.score = 0
        self.display_info_text = f"{self.name}  Score: 0  High Score: {self.high_score}"
        self.pending_display_info_text = None
        self.high_score = max(self.high_score, self.score)
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.is_move_animating = False
        self.move_anim_frame = 0
        self.auto_plan = []
        self.auto_wait_frames = 0
        self.auto_last_direction = None
        self.auto_last_signature = None
        self.auto_restart_wait_steps = -1
        self._spawn_tile()
        self._spawn_tile()

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1

        pressed_action = self.BLANK_ACTION.copy()
        if hasattr(self, "prev_action"):
            for k, v in action.items():
                if v and not self.prev_action.get(k, False):
                    pressed_action[k] = True
        self.prev_action = action.copy()

        for tile in self.tiles:
            tile.update_animations()

        incoming_direction = self._action_to_direction(pressed_action)

        if self.is_move_animating:
            if incoming_direction is None:
                self.move_anim_frame += 1
                t = self.move_anim_frame / self.move_anim_total_frames
                t = max(0.0, min(1.0, t))
                eased = 1.0 - (1.0 - t) * (1.0 - t)

                for tile in self.tiles:
                    tile.update_movement(eased)

                if self.move_anim_frame >= self.move_anim_total_frames:
                    self._finish_move_animation()
            else:
                self._finish_move_animation()

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self._is_game_over():
            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        if incoming_direction is None:
            return False

        new_board, gained, moved, tracks = self._simulate_move(incoming_direction, include_tracks=True)
        if not moved:
            return False

        destinations = defaultdict(list)
        for tr in tracks:
            destinations[(tr["to_r"], tr["to_c"])].append(tr)

        self.board = new_board
        for (to_r, to_c), tr_list in destinations.items():
            if len(tr_list) == 1:
                tr = tr_list[0]
                tile = self._get_tile_at(tr["from_r"], tr["from_c"])
                if tile:
                    tile.value = tr["merged_value"]
                    tile.move_to(to_r, to_c)
            elif len(tr_list) > 1:
                for tr in tr_list:
                    tile = self._get_tile_at(tr["from_r"], tr["from_c"])
                    if tile:
                        tile.move_to(to_r, to_c)
                        tile.to_delete = True
                merged_value = tr_list[0]["merged_value"]
                new_tile = self._make_tile(merged_value, to_r, to_c)
                new_tile.is_visible = False
                new_tile.merge_anim = 8
                self.tiles.append(new_tile)
                self._create_tile_callback(merged_value, to_r, to_c)

        self.score += gained
        self.high_score = max(self.high_score, self.score)
        self.pending_display_info_text = f"{self.name}  Score: {self.score}  High Score: {self.high_score}"
        self._spawn_tile(visible=False)
        self.move_anim_frame = 0
        self.is_move_animating = True
        return False

    def draw(self) -> None:
        self.screen.fill(self.palette["bg"])

        tile_area = min(self.width, self.height) - self.padding * 2
        tile_size = (tile_area - self.padding * (self.grid_size + 1)) // self.grid_size
        board_x = (self.width - tile_area) // 2
        board_y = (self.height - tile_area) // 2

        board_rect = pygame.Rect(board_x, board_y, tile_area, tile_area)
        pygame.draw.rect(self.screen, self.palette["board"], board_rect, border_radius=12)

        for r in range(self.grid_size):
            for c in range(self.grid_size):
                x = board_x + self.padding + c * (tile_size + self.padding)
                y = board_y + self.padding + r * (tile_size + self.padding)
                cell_rect = pygame.Rect(x, y, tile_size, tile_size)
                pygame.draw.rect(self.screen, self.palette["cell"], cell_rect, border_radius=8)

        for tile in self.tiles:
            tile_col = self._get_tile_color(tile.value)
            tile.draw(self.screen, board_x, board_y, tile_size, self.padding, self.palette, tile_col)

        info_font = pygame.font.SysFont("consolas", 24, bold=True)
        info_surf = info_font.render(self.display_info_text, True, self.palette["hud"])
        self.screen.blit(info_surf, (18, 12))

        if self._is_game_over() and not self.is_move_animating:
            alpha = min(180, 60 + self.end_screen_frames * 4)
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, alpha))
            self.screen.blit(overlay, (0, 0))

            end_font = pygame.font.SysFont("consolas", 42, bold=True)
            tip_font = pygame.font.SysFont("consolas", 22)
            end_title = "You Win" if self._check_win_condition() else "Game Over"
            end_txt = end_font.render(end_title, True, (245, 245, 245))
            tip_txt = tip_font.render("Press A / Left Arrow to restart", True, (220, 220, 220))
            self.screen.blit(end_txt, end_txt.get_rect(center=(self.width // 2, self.height // 2 - 20)))
            self.screen.blit(tip_txt, tip_txt.get_rect(center=(self.width // 2, self.height // 2 + 28)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to slide all tiles in one direction. "
            f"When two tiles with the same value collide, they merge into one tile with doubled value. After each valid move, a new tile appears in an empty cell. The game ends when there are no valid moves left. Reach the {self.target_tile} tile to win!"
        )

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if self.frame_index % self.moveInterval != 0:
            return action

        if self._is_game_over() and not self.is_move_animating:
            if self.auto_restart_wait_steps < 0:
                self.auto_restart_wait_steps = random.randint(3, 10)
            if self.auto_restart_wait_steps > 0:
                self.auto_restart_wait_steps -= 1
                return action
            self.auto_restart_wait_steps = -1
            action["A"] = True
            return action
        self.auto_restart_wait_steps = -1

        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action

        signature = self._board_signature(self.board)
        if self.auto_last_signature != signature:
            self.auto_plan = []
            self.auto_last_signature = signature

        if not self.auto_plan:
            self.auto_plan = self._build_auto_plan()
            self.auto_wait_frames = random.randint(1, 3)
            return action

        direction = self.auto_plan.pop(0)
        self.auto_last_direction = direction
        self.auto_wait_frames = random.randint(0, 2)
        return self._direction_to_action(direction)

    def _build_auto_plan(self) -> list[Direction]:
        candidates: list[Direction] = ["up", "left", "right", "down"]
        random.shuffle(candidates)

        scored: list[tuple[int, Direction]] = []
        for direction in candidates:
            sim_board, gained, moved, _ = self._simulate_move(direction)
            if not moved:
                continue
            score = self._evaluate_board(sim_board, gained, direction)
            scored.append((score, direction))

        if not scored:
            return []

        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:2]
        chosen = random.choice(top)[1]

        if self.auto_last_direction is not None and random.random() < 0.35:
            for _, direction in top:
                if direction == self.auto_last_direction:
                    chosen = direction
                    break

        plan = [chosen]
        if random.random() < 0.4:
            plan.append(chosen)
        return plan

    def _evaluate_board(self, board: list[list[Any]], gained: int, direction: Direction) -> int:
        empties = self._empty_count(board)
        corner = self._corner_bonus(board)
        monotonic = self._monotonic_bonus(board)
        momentum = 0
        if self.auto_last_direction == direction:
            momentum = 24
        return gained * 14 + empties * 22 + corner + monotonic + momentum

    def _board_signature(self, board: list[list[Any]]) -> tuple[tuple[Any, ...], ...]:
        return tuple(tuple(row) for row in board)

    def _monotonic_bonus(self, board: list[list[Any]]) -> int:
        def b_val(x: Any) -> int:
            return x if isinstance(x, int) else 0

        bonus = 0
        for row in board:
            vals = [b_val(x) for x in row]
            if len(vals) >= 4:
                if vals[0] >= vals[1] >= vals[2] >= vals[3]:
                    bonus += 8
                if vals[0] <= vals[1] <= vals[2] <= vals[3]:
                    bonus += 8
        for c in range(self.grid_size):
            column = [b_val(board[r][c]) for r in range(self.grid_size)]
            if len(column) >= 4:
                if column[0] >= column[1] >= column[2] >= column[3]:
                    bonus += 8
                if column[0] <= column[1] <= column[2] <= column[3]:
                    bonus += 8
        return bonus

    def _get_tile_at(self, r: int, c: int) -> Tile | None:
        for tile in self.tiles:
            if round(tile.r) == r and round(tile.c) == c and not tile.to_delete and tile.is_visible:
                return tile
        return None

    def _action_to_direction(self, action: ActionState) -> Direction | None:
        if action["W"] or action["LU"]:
            return "up"
        if action["S"] or action["LD"]:
            return "down"
        if action["A"] or action["LL"]:
            return "left"
        if action["D"] or action["LR"]:
            return "right"
        return None

    def _direction_to_action(self, direction: Direction) -> ActionState:
        action = self.BLANK_ACTION.copy()
        if direction == "up":
            action["W"] = True
        elif direction == "down":
            action["S"] = True
        elif direction == "left":
            action["A"] = True
        else:
            action["D"] = True
        return action

    def _spawn_tile(self, visible: bool = True) -> None:
        empty = [(r, c) for r in range(self.grid_size) for c in range(self.grid_size) if self.board[r][c] == 0]
        if not empty:
            return
        r, c = random.choice(empty)
        value = self._get_spawn_value()
        self.board[r][c] = value

        new_tile = self._make_tile(value, r, c)
        new_tile.spawn_anim = 8
        new_tile.is_visible = visible
        self.tiles.append(new_tile)
        self._create_tile_callback(value, r, c)
        
    def _make_tile(self, value: Any, r: int, c: int) -> Tile:
        '''For variants that need to replace Tile with their own subclass.'''
        tile = Tile(value, r, c)
        return tile
    
    def _create_tile_callback(self, value: Any, r: int, c: int) -> None:
        '''For variants that need to do something when a new tile is created.'''

    def _finish_move_animation(self) -> None:
        self.is_move_animating = False
        self.move_anim_frame = 0

        for tile in self.tiles:
            tile.update_movement(1.0)

        new_tiles = []
        for tile in self.tiles:
            if tile.to_delete:
                continue
            if not tile.is_visible:
                tile.is_visible = True
            new_tiles.append(tile)
        self.tiles = new_tiles

        if self.pending_display_info_text is not None:
            self.display_info_text = self.pending_display_info_text
            self.pending_display_info_text = None

        if self._is_game_over() and not self.end_reported:
            self.end_reported = True
            self.end_event_pending = True

    def _simulate_move(
        self,
        direction: Direction,
        include_tracks: bool = False,
    ) -> tuple[list[list[Any]], int, bool, list[dict[str, Any]]]:
        original = [row[:] for row in self.board]
        board = [row[:] for row in self.board]
        gained = 0
        tracks: list[dict[str, Any]] = []
        n = self.grid_size

        def coord(line_id: int, idx: int) -> tuple[int, int]:
            if direction == "left":
                return line_id, idx
            if direction == "right":
                return line_id, n - 1 - idx
            if direction == "up":
                return idx, line_id
            return n - 1 - idx, line_id

        for line_id in range(n):
            values: list[Any] = []
            for idx in range(n):
                r, c = coord(line_id, idx)
                values.append(board[r][c])

            merged, score_gain, line_tracks = self._merge_line(values, include_tracks=include_tracks)
            gained += score_gain

            for idx in range(n):
                r, c = coord(line_id, idx)
                board[r][c] = merged[idx]

            if include_tracks:
                for tr in line_tracks:
                    fr, fc = coord(line_id, tr["from_idx"])
                    to_r, to_c = coord(line_id, tr["to_idx"])
                    tracks.append(
                        {
                            "value": tr["value"],
                            "merged_value": tr["merged_value"],
                            "from_r": fr,
                            "from_c": fc,
                            "to_r": to_r,
                            "to_c": to_c,
                        }
                    )

        moved = board != original
        if not moved:
            tracks = []
        return board, gained, moved, tracks

    def _merge_line(
        self,
        line: list[Any],
        include_tracks: bool = False,
    ) -> tuple[list[Any], int, list[dict[str, Any]]]:
        compact: list[tuple[Any, int]] = []
        for idx, value in enumerate(line):
            if value != 0:
                compact.append((value, idx))

        merged: list[Any] = []
        tracks: list[dict[str, Any]] = []
        score_gain = 0
        i = 0
        while i < len(compact):
            to_idx = len(merged)
            merged_count = 0
            remaining = len(compact) - i
            for take in range(remaining, 1, -1):
                group_values = [compact[i + j][0] for j in range(take)]
                if not self._can_multi_merge(group_values):
                    continue
                merged_value, gain = self._get_multi_merge_result(group_values)
                merged.append(merged_value)
                score_gain += gain
                if include_tracks:
                    for j in range(take):
                        source_value, source_idx = compact[i + j]
                        tracks.append({"value": source_value, "merged_value": merged_value, "from_idx": source_idx, "to_idx": to_idx})
                i += take
                merged_count = take
                break

            if merged_count == 0:
                value, src_idx = compact[i]
                merged.append(value)
                if include_tracks:
                    tracks.append({"value": value, "merged_value": value, "from_idx": src_idx, "to_idx": to_idx})
                i += 1

        merged.extend([0] * (self.grid_size - len(merged)))
        return merged, score_gain, tracks

    def _can_merge(self, val1: Any, val2: Any) -> bool:
        return val1 == val2

    def _can_multi_merge(self, values: list[Any]) -> bool:
        if len(values) == 2:
            return self._can_merge(values[0], values[1])
        return False

    def _get_merge_result(self, val1: Any, val2: Any) -> tuple[Any, int]:
        """Returns (merged_value, score_gain)"""
        if isinstance(val1, int) and isinstance(val2, int):
            new_val = val1 * 2
            return new_val, new_val
        return val1, 0

    def _get_multi_merge_result(self, values: list[Any]) -> tuple[Any, int]:
        if len(values) == 2:
            return self._get_merge_result(values[0], values[1])
        return values[0], 0

    def _get_spawn_value(self) -> Any:
        return 4 if random.random() < 0.1 else 2

    def _check_win_condition(self) -> bool:
        if isinstance(self.target_tile, int) and self.target_tile <= 0:
            return False
        return any(self.target_tile in row for row in self.board)

    def _is_game_over(self) -> bool:
        if self._check_win_condition():
            return True
        if any(0 in row for row in self.board):
            return False
        for direction in ("up", "down", "left", "right"):
            _, _, moved, _ = self._simulate_move(direction)
            if moved:
                return False
        return True

    def _empty_count(self, board: list[list[Any]]) -> int:
        count = 0
        for row in board:
            for value in row:
                if value == 0:
                    count += 1
        return count

    def _corner_bonus(self, board: list[list[Any]]) -> int:
        corners = [board[0][0], board[0][-1], board[-1][0], board[-1][-1]]
        mx = max((v for row in board for v in row if isinstance(v, int)), default=0)
        if mx in corners:
            return mx // 2
        return 0

    def _get_tile_color(self, value: Any) -> tuple[int, int, int]:
        base_h = float(self.palette.get("base_h", 0.0))
        is_dark = bool(self.palette.get("is_dark", False))
        
        if isinstance(value, int) and value <= 0:
            return self.palette.get("cell", (60, 58, 50)) # type: ignore
            
        power = math.log2(value) if isinstance(value, int) and value > 0 else 1.5
        h = base_h + (power * 0.03)
        s = min(0.9, 0.4 + (power * 0.05))
        
        if is_dark:
            l = min(0.8, 0.25 + (power * 0.04))
        else:
            l = max(0.4, 0.85 - (power * 0.04))
            
        r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
        return int(r * 255), int(g * 255), int(b * 255)

    def _make_palette(self) -> dict[str, tuple[int, int, int] | float | bool]:
        base_h = random.random()
        is_dark = random.choice([True, False])

        def color(h: float, l: float, s: float) -> tuple[int, int, int]:
            r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
            return int(r * 255), int(g * 255), int(b * 255)

        if is_dark:
            p = {
                "bg": color(base_h, 0.1, 0.2),
                "board": color(base_h, 0.15, 0.2),
                "cell": color(base_h, 0.2, 0.2),
                "text": (245, 245, 245),
                "hud": color(base_h, 0.8, 0.2),
            }
        else:
            p = {
                "bg": color(base_h, 0.95, 0.2),
                "board": color(base_h, 0.8, 0.25),
                "cell": color(base_h, 0.85, 0.25),
                "text": (32, 30, 24),
                "hud": color(base_h, 0.3, 0.2),
            }
            
        p["base_h"] = base_h
        p["is_dark"] = is_dark
        return p


if __name__ == "__main__":
    from gameRunner import run_autoplay, run_human_debug

    run_human_debug(Game2048)