from __future__ import annotations

import os
import math
import random
import sys
from itertools import product
from typing import Any

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048, Direction, Tile


class QuantumTile(Tile):
    orbit_time_seconds = 0.0

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

        values = self.value if isinstance(self.value, tuple) else (self.value,)
        if len(values) == 1:
            font = pygame.font.SysFont("consolas", 36 if values[0] < 1000 else 28, bold=True)
            text = font.render(str(values[0]), True, palette["text"])
            text_rect = text.get_rect(center=tile_rect.center)
            screen.blit(text, text_rect)
            return

        orbit_radius = max(10, int(min(tw, th) * 0.24))
        font_size = 28 if len(values) == 2 else 24 if len(values) == 3 else 20
        font = pygame.font.SysFont("consolas", font_size, bold=True)
        center_x, center_y = tile_rect.center
        t = self.orbit_time_seconds
        base_angle = t * 1.9
        step = (2.0 * math.pi) / len(values)

        for idx, val in enumerate(values):
            angle = base_angle + step * idx
            ox = math.cos(angle) * orbit_radius
            oy = math.sin(angle) * orbit_radius
            text = font.render(str(val), True, palette["text"])
            text_rect = text.get_rect(center=(int(center_x + ox), int(center_y + oy)))
            screen.blit(text, text_rect)


class GameQuantum(Game2048):
    name = "Quantum 2048"

    def __init__(self, headless: bool = False) -> None:
        self.quantum_spawn_chance = 0.5
        self.quantum_spawn_options: list[tuple[int, ...]] = [(2, 4), (2, 8), (4, 8)]
        super().__init__(headless=headless)

    def _get_spawn_value(self) -> Any:
        if random.random() < self.quantum_spawn_chance:
            return random.choice(self.quantum_spawn_options)
        return super()._get_spawn_value()

    def _make_tile(self, value: Any, r: int, c: int) -> Tile:
        return QuantumTile(value, r, c)

    def draw(self) -> None:
        QuantumTile.orbit_time_seconds = self.frame_index / float(self.fps)
        super().draw()

    def _tile_options(self, value: Any) -> list[Any]:
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _normalize_quantum_tile(self, values: list[Any]) -> Any:
        unique_sorted = sorted(set(values))
        if unique_sorted[0] == 0:
            unique_sorted = unique_sorted[1:]
        if not unique_sorted:
            return 0
        if len(unique_sorted) == 1:
            return unique_sorted[0]
        return tuple(unique_sorted)

    def _expand_line_timelines(self, line: list[Any]) -> list[list[Any]]:
        options_per_cell = [self._tile_options(value) for value in line]
        return [list(concrete) for concrete in product(*options_per_cell)]

    def _simulate_concrete_line(
        self,
        line: list[Any],
        include_tracks: bool = False,
    ) -> tuple[list[Any], int, int, list[dict[str, Any]]]:
        merged_line, gain, tracks = super()._merge_line(line, include_tracks=include_tracks)
        non_zero_before = sum(1 for value in line if value != 0)
        non_zero_after = sum(1 for value in merged_line if value != 0)
        merge_count = non_zero_before - non_zero_after
        return merged_line, gain, merge_count, tracks

    def _collapse_line_timelines(
        self,
        source_line: list[Any],
        timelines: list[tuple[list[Any], int, int, list[dict[str, Any]]]],
    ) -> tuple[list[Any], int, list[dict[str, Any]]]:
        if not timelines:
            return [0] * self.grid_size, 0, []

        has_any_merge = False
        for _, _, merge_count, _ in timelines:
            if merge_count > 0:
                has_any_merge = True
                break

        survivors: list[tuple[list[Any], int, int, list[dict[str, Any]]]] = []
        if has_any_merge:
            for item in timelines:
                if item[2] > 0:
                    survivors.append(item)
        else:
            survivors = timelines

        collapsed_line: list[Any] = []
        for idx in range(self.grid_size):
            values_at_idx = [timeline[0][idx] for timeline in survivors]
            collapsed_line.append(self._normalize_quantum_tile(values_at_idx))

        best_gain = max(item[1] for item in survivors)

        collapsed_non_zero = [idx for idx, value in enumerate(collapsed_line) if value != 0]

        matched_tracks: list[dict[str, Any]] = []
        for line_values, _, _, line_tracks in survivors:
            line_non_zero = [idx for idx, value in enumerate(line_values) if value != 0]
            if line_non_zero != collapsed_non_zero:
                continue
            for tr in line_tracks:
                to_idx = tr["to_idx"]
                matched_tracks.append(
                    {
                        "value": tr["value"],
                        "merged_value": collapsed_line[to_idx],
                        "from_idx": tr["from_idx"],
                        "to_idx": to_idx,
                    }
                )
            return collapsed_line, best_gain, matched_tracks

        synthetic_tracks: list[dict[str, Any]] = []
        source_non_zero = [idx for idx, value in enumerate(source_line) if value != 0]

        for dst_pos, to_idx in enumerate(collapsed_non_zero):
            from_idx = source_non_zero[dst_pos]
            synthetic_tracks.append(
                {
                    "value": source_line[from_idx],
                    "merged_value": collapsed_line[to_idx],
                    "from_idx": from_idx,
                    "to_idx": to_idx,
                }
            )

        if collapsed_non_zero:
            last_to_idx = collapsed_non_zero[-1]
            for from_idx in source_non_zero[len(collapsed_non_zero):]:
                synthetic_tracks.append(
                    {
                        "value": source_line[from_idx],
                        "merged_value": collapsed_line[last_to_idx],
                        "from_idx": from_idx,
                        "to_idx": last_to_idx,
                    }
                )

        return collapsed_line, best_gain, synthetic_tracks

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

            timelines: list[tuple[list[Any], int, int, list[dict[str, Any]]]] = []
            for concrete_line in self._expand_line_timelines(values):
                timelines.append(self._simulate_concrete_line(concrete_line, include_tracks=include_tracks))

            collapsed_line, line_gain, line_tracks = self._collapse_line_timelines(values, timelines)
            gained += line_gain

            for idx in range(n):
                r, c = coord(line_id, idx)
                board[r][c] = collapsed_line[idx]

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

    def _check_win_condition(self) -> bool:
        if self.target_tile <= 0:
            return False
        for row in self.board:
            for value in row:
                if self.target_tile in self._tile_options(value):
                    return True
        return False

    def _is_game_over(self) -> bool:
        if self._check_win_condition():
            return True
        for direction in ("up", "down", "left", "right"):
            _, _, moved, _ = self._simulate_move(direction)
            if moved:
                return False
        return True

    def _get_tile_color(self, value: Any) -> tuple[int, int, int]:
        if isinstance(value, tuple):
            return super()._get_tile_color(max(value))
        return super()._get_tile_color(value)

    def getPrompt(self) -> str:
        return "This is Quantum 2048. Use W/A/S/D or Arrow keys to slide tiles. Some spawned tiles are quantum tiles such as (2, 4), meaning the tile can be either value. When a swipe affects a line with quantum tiles, the line splits into timelines for each quantum possibility, then each timeline slides in the chosen direction and equal values merge into doubled values. If at least one timeline gets a merge, all non-merge timelines collapse away. The surviving timelines are stacked back into one board, and cells with multiple surviving outcomes become quantum tiles."


if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(GameQuantum)
