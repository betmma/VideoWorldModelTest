from __future__ import annotations

import os, random, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.onet import MatchResult, OnetBase


def triplet_orders(positions: list[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]:
    """Return all six possible selection orders for three cells."""
    first, second, third = positions
    return [(first, second, third), (first, third, second), (second, first, third), (second, third, first), (third, first, second), (third, second, first)]


class ThreeWayTotalThreeOnet(OnetBase):
    """Onet variant where two segments share a combined turn budget of three."""

    name = "Three-Way Onet"

    def get_required_selection_size(self) -> int:
        """Require three selected tiles before resolving a move."""
        return 3

    def get_rule_prompt_text(self) -> str:
        """Describe the combined-turn three-way rule for the training prompt."""
        return "Match three identical tiles. Connect them through a middle tile, and the two connection segments together can bend at most three times."

    def build_initial_tiles(self) -> list:
        """Create triplets of identical tiles for the three-way rule."""
        cell_count = sum(1 for row, col in self.iter_play_cells() if self.board_mask[row][col])
        contents = [self.get_symbol_pool()[index % len(self.get_symbol_pool())] for index in range(cell_count // 3)]
        random.shuffle(contents)
        tiles = []
        for content in contents:
            tiles.append(self.make_tile(-1, -1, content))
            tiles.append(self.make_tile(-1, -1, content))
            tiles.append(self.make_tile(-1, -1, content))
        random.shuffle(tiles)
        return tiles

    def try_create_match(self, positions: list[tuple[int, int]]) -> MatchResult | None:
        """Accept any order of three identical tiles whose two segments use at most three turns in total."""
        tiles = [self.board[row][col] for row, col in positions]
        if any(tile is None for tile in tiles):
            return None
        if len({tile.content for tile in tiles}) != 1:
            return None
        best_result = None
        for first, second, third in triplet_orders(positions):
            first_path = self.find_connection_result(first[0], first[1], second[0], second[1], 3)
            if first_path is None:
                continue
            second_path = self.find_connection_result(second[0], second[1], third[0], third[1], 3)
            if second_path is None:
                continue
            if first_path[1] + second_path[1] > 3:
                continue
            score = (first_path[1] + second_path[1], len(first_path[0]) + len(second_path[0]))
            if best_result is None or score < best_result[0]:
                best_result = (score, [first, second, third], [first_path[0], second_path[0]])
        if best_result is None:
            return None
        return MatchResult(positions=best_result[1], path_groups=best_result[2], score_gain=2)

    def get_available_matches(self) -> list[MatchResult]:
        """Enumerate all currently legal three-tile matches for autoplay and reshuffles."""
        buckets = {}
        for row, col in self.iter_play_cells():
            tile = self.board[row][col]
            if tile is not None:
                buckets.setdefault(tile.content, []).append((row, col))
        matches = []
        for bucket in buckets.values():
            for first_index in range(len(bucket)):
                for second_index in range(first_index + 1, len(bucket)):
                    for third_index in range(second_index + 1, len(bucket)):
                        result = self.try_create_match([bucket[first_index], bucket[second_index], bucket[third_index]])
                        if result is not None:
                            matches.append(result)
        return matches

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(ThreeWayTotalThreeOnet)