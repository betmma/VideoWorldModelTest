from __future__ import annotations

import os, random, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.onet import OnetBase


class MovingMatchOnet(OnetBase):
    """Onet variant where tiles slide after every successful match according to directional inner shade."""

    name = "Moving Onet"

    def prepare_new_board(self) -> None:
        """Choose one of the ten hidden movement layouts for this board."""
        self.move_mode = random.choice(["all_up", "all_down", "all_left", "all_right", "split_horizontal_out", "split_horizontal_in", "split_vertical_out", "split_vertical_in", "nearest_side", "opposite_nearest_side"])

    def get_rule_prompt_text(self) -> str:
        """Describe the movement rule for the training prompt."""
        return "Match two identical tiles. The line connecting them cannot bend more than twice. After each match, the remaining tiles slide in the directions shown by the faint inner shade until they hit a border or another tile."

    def get_tile_move_direction_for_tile(self, tile) -> tuple[int, int]:
        """Return the current arrow direction for one tile under the active hidden layout."""
        if tile.row < 0 or tile.col < 0:
            return 0, 0
        if self.move_mode == "all_up":
            return -1, 0
        if self.move_mode == "all_down":
            return 1, 0
        if self.move_mode == "all_left":
            return 0, -1
        if self.move_mode == "all_right":
            return 0, 1
        if self.move_mode == "split_horizontal_out":
            return (0, -1) if tile.col < self.play_cols // 2 else (0, 1)
        if self.move_mode == "split_horizontal_in":
            return (0, 1) if tile.col < self.play_cols // 2 else (0, -1)
        if self.move_mode == "split_vertical_out":
            return (-1, 0) if tile.row < self.play_rows // 2 else (1, 0)
        if self.move_mode == "split_vertical_in":
            return (1, 0) if tile.row < self.play_rows // 2 else (-1, 0)
        nearest_direction = self.get_nearest_side_direction(tile.row, tile.col)
        if self.move_mode == "nearest_side":
            return nearest_direction
        return -nearest_direction[0], -nearest_direction[1]

    def get_nearest_side_direction(self, row: int, col: int) -> tuple[int, int]:
        """Return the direction toward the nearest board edge using a fixed tie order."""
        candidates = [(col, (0, -1)), (row, (-1, 0)), (self.play_cols - 1 - col, (0, 1)), (self.play_rows - 1 - row, (1, 0))]
        best_distance, best_direction = candidates[0]
        for distance, direction in candidates[1:]:
            if distance < best_distance:
                best_distance = distance
                best_direction = direction
        return best_direction

    def apply_match_effect(self, result) -> None:
        """Remove the pair and then slide the remaining tiles according to the hidden movement layout."""
        self.remove_tiles(result.positions)
        self.slide_tiles_by_direction()

    def slide_tiles_by_direction(self) -> None:
        """Run repeated parallel one-cell moves until every tile is blocked."""
        fixed_directions = {tile.id: tile.move_direction for tile in self.iter_tiles()}
        while True:
            proposals = {}
            for tile in self.iter_tiles():
                dr, dc = fixed_directions[tile.id]
                next_row = tile.row + dr
                next_col = tile.col + dc
                if 0 <= next_row < self.play_rows and 0 <= next_col < self.play_cols and self.is_play_cell(next_row, next_col) and self.board[next_row][next_col] is None:
                    proposals.setdefault((next_row, next_col), []).append((tile.row, tile.col))
            if len(proposals) == 0:
                break
            winners = []
            for target, sources in proposals.items():
                if len(sources) == 1:
                    winners.append((sources[0], target))
                    continue
                winners.append((self.choose_winning_source(sources, fixed_directions), target))
            moving_tiles = []
            for (source_row, source_col), (target_row, target_col) in winners:
                tile = self.take_tile(source_row, source_col)
                if tile is not None:
                    moving_tiles.append((tile, target_row, target_col))
            for tile, target_row, target_col in moving_tiles:
                tile.row = target_row
                tile.col = target_col
                tile.move_direction = fixed_directions[tile.id]
                self.board[target_row][target_col] = tile
        for tile in self.iter_tiles():
            tile.move_direction = self.get_tile_move_direction_for_tile(tile)

    def choose_winning_source(self, sources: list[tuple[int, int]], fixed_directions: dict[int, tuple[int, int]]) -> tuple[int, int]:
        """Break movement conflicts by comparing consecutive runs and then a fixed direction order."""
        best_source = sources[0]
        best_score = (-1, -1)
        for source_row, source_col in sources:
            tile = self.board[source_row][source_col]
            direction = fixed_directions[tile.id]
            run_length = self.count_direction_run(source_row, source_col, direction, fixed_directions)
            direction_score = -self.get_direction_priority(direction)
            score = (run_length, direction_score)
            if score > best_score:
                best_score = score
                best_source = (source_row, source_col)
        return best_source

    def count_direction_run(self, row: int, col: int, direction: tuple[int, int], fixed_directions: dict[int, tuple[int, int]]) -> int:
        """Count the consecutive tiles behind one mover that share the same fixed direction."""
        dr, dc = direction
        length = 0
        probe_row = row
        probe_col = col
        while 0 <= probe_row < self.play_rows and 0 <= probe_col < self.play_cols and self.is_play_cell(probe_row, probe_col):
            tile = self.board[probe_row][probe_col]
            if tile is None or fixed_directions[tile.id] != direction:
                return length
            length += 1
            probe_row -= dr
            probe_col -= dc
        return length

    def get_direction_priority(self, direction: tuple[int, int]) -> int:
        """Return the fixed conflict priority for one direction."""
        return {(0, -1): 0, (-1, 0): 1, (0, 1): 2, (1, 0): 3}[direction]

    def draw_tile_overlay(self, surface, tile, rect, alpha_scale: float) -> None:
        """Draw the directional inner shade that shows how this tile will move after a match."""
        self.draw_direction_inner_shade(surface, rect, tile.move_direction, tile.edge_color, alpha_scale)

if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(MovingMatchOnet)
