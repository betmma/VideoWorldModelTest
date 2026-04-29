from __future__ import annotations

import os, random, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.onet import OnetBase


class FactorMatchOnet(OnetBase):
    """Onet variant where one number must be a factor of the other."""

    name = "Factor Onet"

    def get_rule_prompt_text(self) -> str:
        """Describe the factor rule for the training prompt."""
        return "Match two number tiles when one of the numbers is a factor of the other. The line connecting them cannot bend more than twice."

    def build_initial_tiles(self) -> list:
        """Create number pairs that satisfy the factor rule."""
        cell_count = sum(1 for row, col in self.iter_play_cells() if self.board_mask[row][col])
        tiles = []
        for _ in range(cell_count // 2):
            first, second = self.get_random_factor_pair()
            tiles.append(self.make_tile(-1, -1, first))
            tiles.append(self.make_tile(-1, -1, second))
        random.shuffle(tiles)
        return tiles

    def get_number_weight(self, value: int) -> int:
        """Lower the frequency of 11, 13, and 17 while keeping other values common."""
        return 1 if value in [11, 13, 17] else 4

    def get_random_factor_pair(self) -> tuple[int, int]:
        """Choose one random factor pair from 1 through 20."""
        pairs = []
        weights = []
        for first in range(1, 21):
            for second in range(1, 21):
                if first == second:
                    continue
                if first % second == 0 or second % first == 0:
                    pairs.append((first, second))
                    weights.append(self.get_number_weight(first) * self.get_number_weight(second))
        return random.choices(pairs, weights=weights, k=1)[0]

    def are_tiles_compatible(self, first_tile, second_tile) -> bool:
        """Allow a pair only when one value divides the other exactly."""
        return first_tile.content % second_tile.content == 0 or second_tile.content % first_tile.content == 0

    def draw_tile_content(self, surface, tile, rect, alpha_scale: float) -> None:
        """Draw the tile number instead of a symbol."""
        self.draw_tile_text(surface, str(tile.content), rect, tile.text_color, alpha_scale)

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(FactorMatchOnet)