from __future__ import annotations

import os, random, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.onet import OnetBase


class TargetSumOnet(OnetBase):
    """Onet variant where pairs must sum to a cycling target number."""

    name = "Sum Onet"

    def prepare_new_board(self) -> None:
        """Create the target sequence for the next board."""
        start = random.randint(6, 10)
        self.target_sequence = [start + offset for offset in range(5)]
        self.target_index = 0

    def get_current_target(self) -> int:
        """Return the target number currently used for matching."""
        return self.target_sequence[self.target_index]

    def get_rule_prompt_text(self) -> str:
        """Describe the sum rule for the training prompt without showing the live target."""
        return "Match two number tiles whose sum equals the current target number. The line connecting them cannot bend more than twice."

    def get_panel_lines(self) -> list[str]:
        """Show the live target and its cycle in the side panel."""
        return [f"Tiles Left {len(self.iter_tiles())}", f"Target {self.get_current_target()}", "Cycle " + " ".join(str(value) for value in self.target_sequence[:3]), "      " + " ".join(str(value) for value in self.target_sequence[3:])]

    def build_initial_tiles(self) -> list:
        """Create number pairs that match the starting target."""
        cell_count = sum(1 for row, col in self.iter_play_cells() if self.board_mask[row][col])
        tiles = []
        for _ in range(cell_count // 2):
            first, second = self.get_random_sum_pair(self.get_current_target())
            tiles.append(self.make_tile(-1, -1, first))
            tiles.append(self.make_tile(-1, -1, second))
        random.shuffle(tiles)
        return tiles

    def get_random_sum_pair(self, target: int) -> tuple[int, int]:
        """Create one random pair of digits that adds up to the given target."""
        first = random.randint(1 if target - 9 < 1 else target - 9, 9 if target - 1 > 9 else target - 1)
        return first, target - first

    def are_tiles_compatible(self, first_tile, second_tile) -> bool:
        """Allow a pair only when its sum equals the live target."""
        return first_tile.content + second_tile.content == self.get_current_target()

    def apply_match_effect(self, result) -> None:
        """Remove the pair and then advance the target number."""
        self.remove_tiles(result.positions)
        self.target_index = (self.target_index + 1) % len(self.target_sequence)

    def reassign_tiles_for_shuffle(self, tiles: list, attempt: int) -> None:
        """Rewrite the remaining numbers so the current target has legal pair values again."""
        random.shuffle(tiles)
        for index in range(0, len(tiles), 2):
            first, second = self.get_random_sum_pair(self.get_current_target())
            self.set_tile_content(tiles[index], first)
            self.set_tile_content(tiles[index + 1], second)

    def draw_tile_content(self, surface, tile, rect, alpha_scale: float) -> None:
        """Draw the tile number instead of a symbol."""
        self.draw_tile_text(surface, str(tile.content), rect, tile.text_color, alpha_scale)

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(TargetSumOnet)