from __future__ import annotations

import os
import random
import sys
from typing import Any

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048


class GameDivisorSeeds(Game2048):
    name = "Dive"
    initial_seeds: set[int] = {2}

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        self.target_tile = 4096
        self.seeds: set[int] = set(self.initial_seeds)
        self.pending_new_tiles: list[int] = []
        self.reset()

    def reset(self) -> None:
        self.seeds = set(self.initial_seeds)
        self.pending_new_tiles = []
        super().reset()

    def update(self, action):  # type: ignore[override]
        was_animating = self.is_move_animating
        had_pending = self.pending_board is not None

        result = super().update(action)

        if (
            was_animating
            and had_pending
            and self.pending_board is not None
            and self.is_move_animating
            and not self.pending_new_tiles
        ):
            # A new move has just been accepted and pending_board now points to the new state.
            self.pending_new_tiles = self._extract_created_tiles(self.board, self.pending_board)

        return result

    def _can_merge(self, val1: Any, val2: Any) -> bool:
        if not isinstance(val1, int) or not isinstance(val2, int):
            return False
        if val1 <= 0 or val2 <= 0:
            return False

        a = min(val1, val2)
        b = max(val1, val2)
        return b % a == 0

    def _get_merge_result(self, val1: Any, val2: Any) -> tuple[Any, int]:
        if not isinstance(val1, int) or not isinstance(val2, int):
            return val1, 0

        new_val = val1 + val2
        return new_val, new_val

    def _get_spawn_value(self) -> Any:
        if not self.seeds:
            return 2
        return random.choice(sorted(self.seeds))

    def _finish_move_animation(self) -> None:
        super()._finish_move_animation()

        if not self.pending_new_tiles:
            self._sync_seeds_with_board()
            return

        self._unlock_seeds_from_new_tiles(self.pending_new_tiles)
        self.pending_new_tiles = []
        self._sync_seeds_with_board()

    def _unlock_seeds_from_new_tiles(self, new_tiles: list[int]) -> None:
        for new_tile in new_tiles:
            current_seeds = sorted(self.seeds)
            while new_tile > 1:
                flag = True
                for seed in current_seeds:
                    if seed <= 1:
                        continue
                    if new_tile % seed == 0:
                        new_tile = new_tile // seed
                        flag = False
                if flag:
                    break
            if new_tile > 1:
                self.seeds.add(new_tile)

    def _sync_seeds_with_board(self) -> None:
        present_values = [
            value
            for row in self.board
            for value in row
            if isinstance(value, int) and value > 0
        ]

        keep: set[int] = set()
        for seed in self.seeds:
            if seed <= 0:
                continue
            if any(value % seed == 0 for value in present_values):
                keep.add(seed)

        self.seeds = keep
        if not self.seeds:
            self.seeds = set(self.initial_seeds)

    def _extract_created_tiles(
        self,
        old_board: list[list[Any]],
        new_board: list[list[Any]],
    ) -> list[int]:
        old_counts: dict[int, int] = {}
        for row in old_board:
            for value in row:
                if isinstance(value, int) and value > 0:
                    old_counts[value] = old_counts.get(value, 0) + 1

        new_counts: dict[int, int] = {}
        for row in new_board:
            for value in row:
                if isinstance(value, int) and value > 0:
                    new_counts[value] = new_counts.get(value, 0) + 1

        created: list[int] = []
        for value, count in new_counts.items():
            delta = count - old_counts.get(value, 0)
            if delta > 0:
                created.extend([value] * delta)

        return created

    def draw(self) -> None:
        super().draw()

        seeds_sorted = sorted(self.seeds)
        seed_text = "Seeds: " + (", ".join(str(seed) for seed in seeds_sorted) if seeds_sorted else "(none)")

        font = pygame.font.SysFont("consolas", 20, bold=True)
        text_surf = font.render(seed_text, True, self.palette["hud"])
        text_rect = text_surf.get_rect(center=(self.width // 2, self.height - 20))

        bg_rect = text_rect.inflate(16, 8)
        bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 100))
        self.screen.blit(bg, bg_rect.topleft)
        self.screen.blit(text_surf, text_rect)

    def getPrompt(self) -> str:
        return "This is Dive. Use W/A/S/D or Arrow keys to slide all tiles in one direction. Two tiles can merge if one value divides the other. Merge result is the sum of both values. New tiles spawn only from current seed values (initially only 2). Whenever a new tile N is created, N is divided by each current seed until no more division is possible; the quotient becomes an unlocked seed. A seed is removed when no multiples of that seed remain on the grid."


if __name__ == "__main__":
    from gameRunner import run_human_debug

    run_human_debug(GameDivisorSeeds)
