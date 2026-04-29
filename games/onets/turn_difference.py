from __future__ import annotations

import os, random, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.onet import MatchResult, OnetBase


class TurnDifferenceOnet(OnetBase):
    """Onet variant where the number difference must equal the minimal path turn count."""

    name = "Turn Difference Onet"

    def get_rule_prompt_text(self) -> str:
        """Describe the difference-versus-turns rule for the training prompt."""
        return "Match two number tiles when the larger number minus the smaller number equals the number of turns in the lowest-turn connecting line."

    def build_initial_tiles(self) -> list:
        """Create number pairs with small differences so the board regularly produces legal matches."""
        cell_count = sum(1 for row, col in self.iter_play_cells() if self.board_mask[row][col])
        tiles = []
        for _ in range(cell_count // 2):
            first, second = self.get_random_difference_pair()
            tiles.append(self.make_tile(-1, -1, first))
            tiles.append(self.make_tile(-1, -1, second))
        random.shuffle(tiles)
        return tiles

    def get_random_difference_pair(self) -> tuple[int, int]:
        """Choose one random pair of digits with a small absolute difference."""
        difference = random.choice([0, 1, 1, 2, 2, 3, 4])
        low = random.randint(1, 9 - difference)
        pair = [low, low + difference]
        random.shuffle(pair)
        return pair[0], pair[1]

    def try_create_match(self, positions: list[tuple[int, int]]) -> MatchResult | None:
        """Accept a pair only when its absolute difference equals the minimal path turn count."""
        first_row, first_col = positions[0]
        second_row, second_col = positions[1]
        first_tile = self.board[first_row][first_col]
        second_tile = self.board[second_row][second_col]
        if first_tile is None or second_tile is None:
            return None
        path = self.find_connection_result(first_row, first_col, second_row, second_col, None)
        if path is None:
            return None
        if abs(first_tile.content - second_tile.content) != path[1]:
            return None
        return MatchResult(positions=positions[:], path_groups=[path[0]], score_gain=1)

    def reassign_tiles_for_shuffle(self, tiles: list, attempt: int) -> None:
        """Rewrite the remaining numbers so the board keeps producing plausible turn differences."""
        random.shuffle(tiles)
        for index in range(0, len(tiles), 2):
            first, second = self.get_random_difference_pair()
            self.set_tile_content(tiles[index], first)
            self.set_tile_content(tiles[index + 1], second)

    def draw_tile_content(self, surface, tile, rect, alpha_scale: float) -> None:
        """Draw the tile number instead of a symbol."""
        self.draw_tile_text(surface, str(tile.content), rect, tile.text_color, alpha_scale)

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_human_debug(TurnDifferenceOnet)