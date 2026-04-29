from __future__ import annotations

import os, random, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.onet import MatchResult, OnetBase


def triplet_orders(positions: list[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]:
    """Return all six possible selection orders for three cells."""
    first, second, third = positions
    return [(first, second, third), (first, third, second), (second, first, third), (second, third, first), (third, first, second), (third, second, first)]


class TriadSumOnet(OnetBase):
    """Onet variant where three numbers match when two add up to the third."""

    name = "Triad Sum Onet"

    def get_required_selection_size(self) -> int:
        """Require three selected tiles before resolving a move."""
        return 3

    def get_rule_prompt_text(self) -> str:
        """Describe the arithmetic triad rule for the training prompt."""
        return "Match three number tiles when two of the numbers add up to the third number. The line must connect the first tile to the middle tile and then the middle tile to the last tile, and each segment cannot bend more than twice."

    def build_initial_tiles(self) -> list:
        """Create arithmetic triplets where two numbers add up to the third."""
        cell_count = sum(1 for row, col in self.iter_play_cells() if self.board_mask[row][col])
        tiles = []
        for _ in range(cell_count // 3):
            first, second, third = self.get_random_sum_triplet()
            tiles.append(self.make_tile(-1, -1, first))
            tiles.append(self.make_tile(-1, -1, second))
            tiles.append(self.make_tile(-1, -1, third))
        random.shuffle(tiles)
        return tiles

    def get_random_sum_triplet(self) -> tuple[int, int, int]:
        """Choose one random triplet where two values add up to the third."""
        first = random.randint(1, 10)
        second = random.randint(1, 20 - first)
        return first, second, first + second

    def try_create_match(self, positions: list[tuple[int, int]]) -> MatchResult | None:
        """Accept any order of three tiles when two numbers sum to the third and both segments use at most two turns."""
        tiles = [self.board[row][col] for row, col in positions]
        if any(tile is None for tile in tiles):
            return None
        values = sorted(tile.content for tile in tiles)
        if values[0] + values[1] != values[2]:
            return None
        best_result = None
        for first, second, third in triplet_orders(positions):
            first_path = self.find_connection_result(first[0], first[1], second[0], second[1], 2)
            if first_path is None:
                continue
            second_path = self.find_connection_result(second[0], second[1], third[0], third[1], 2)
            if second_path is None:
                continue
            score = (first_path[1] + second_path[1], len(first_path[0]) + len(second_path[0]))
            if best_result is None or score < best_result[0]:
                best_result = (score, [first, second, third], [first_path[0], second_path[0]])
        if best_result is None:
            return None
        return MatchResult(positions=best_result[1], path_groups=best_result[2], score_gain=2)

    def get_available_matches(self) -> list[MatchResult]:
        """Enumerate all legal arithmetic triads for autoplay and reshuffles."""
        positions = [(row, col) for row, col in self.iter_play_cells() if self.board[row][col] is not None]
        matches = []
        for first_index in range(len(positions)):
            for second_index in range(first_index + 1, len(positions)):
                for third_index in range(second_index + 1, len(positions)):
                    result = self.try_create_match([positions[first_index], positions[second_index], positions[third_index]])
                    if result is not None:
                        matches.append(result)
        return matches

    def draw_tile_content(self, surface, tile, rect, alpha_scale: float) -> None:
        """Draw the tile number instead of a symbol."""
        self.draw_tile_text(surface, str(tile.content), rect, tile.text_color, alpha_scale)

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(TriadSumOnet)