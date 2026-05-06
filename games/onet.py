from __future__ import annotations

import heapq, math, os, random, sys
from collections import deque
from dataclasses import dataclass

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase

CellPos = tuple[int, int]
SearchPos = tuple[int, int]


@dataclass
class OnetTile:
    """Store one logical tile together with the data used for drawing and animation."""

    id: int
    row: int
    col: int
    content: object
    symbol: str
    fill_color: tuple[int, int, int]
    edge_color: tuple[int, int, int]
    accent_color: tuple[int, int, int]
    text_color: tuple[int, int, int]
    move_direction: tuple[int, int] = (0, 0)


@dataclass
class MatchResult:
    """Describe one successful selection and the paths that should be drawn for it."""

    positions: list[CellPos]
    path_groups: list[list[SearchPos]]
    score_gain: int = 1


@dataclass
class TileMotion:
    """Store one tile moving from an old cell to a new cell."""

    tile: OnetTile
    from_row: int
    from_col: int
    to_row: int
    to_col: int


@dataclass
class TileGhost:
    """Store one removed tile that should fade out from its old cell."""

    tile: OnetTile
    row: int
    col: int


class OnetBase(GameBase):
    """Playable Onet base class with cursor controls, two-turn path matching, and variant hooks."""

    name = "Onet"
    variantsPath = "onets"
    moveInterval = 4
    play_rows = 6
    play_cols = 10

    def __init__(self, headless: bool = False) -> None:
        """Create fonts, colors, reusable timing values, and the first board."""
        self.fps = 30
        self.margin = 22
        self.panel_width = 228
        self.board_padding = 18
        self.selection_flash_total_frames = 14
        self.movement_anim_total_frames = 16
        self.end_screen_auto_reset = 86
        self.end_screen_event_frame = 26

        self.background_top = (29, 42, 64)
        self.background_bottom = (10, 18, 33)
        self.panel_fill = (17, 29, 46)
        self.panel_line = (75, 103, 141)
        self.board_shadow = (7, 12, 20)
        self.board_frame = (208, 226, 250)
        self.slot_fill_a = (219, 232, 244)
        self.slot_fill_b = (202, 218, 236)
        self.slot_gap_fill = (26, 39, 58)
        self.cursor_color = (255, 212, 74)
        self.selection_color = (255, 249, 189)
        self.error_color = (255, 109, 109)
        self.path_color = (224, 202, 103)
        self.text_primary = (242, 247, 253)
        self.text_soft = (180, 198, 219)
        self.win_color = (140, 244, 173)

        self.tile_palettes = [
            ((255, 140, 122), (153, 67, 56), (255, 228, 215), (94, 29, 24)),
            ((255, 189, 113), (149, 90, 29), (255, 237, 196), (101, 57, 18)),
            ((252, 232, 122), (150, 128, 31), (255, 250, 212), (94, 79, 15)),
            ((145, 221, 139), (59, 133, 58), (224, 255, 223), (28, 76, 31)),
            ((120, 219, 197), (34, 125, 112), (214, 255, 246), (12, 76, 69)),
            ((126, 202, 255), (36, 109, 170), (226, 245, 255), (20, 68, 111)),
            ((145, 171, 255), (57, 80, 163), (234, 239, 255), (31, 44, 98)),
            ((194, 151, 255), (97, 64, 165), (245, 233, 255), (67, 35, 121)),
            ((244, 149, 228), (157, 64, 139), (255, 229, 248), (107, 31, 94)),
            ((255, 155, 186), (171, 62, 96), (255, 228, 237), (114, 30, 59)),
        ]

        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        pygame.font.init()
        self.title_font = pygame.font.SysFont("trebuchetms", 24, bold=True)
        self.panel_font = pygame.font.SysFont("trebuchetms", 22, bold=True)
        self.small_font = pygame.font.SysFont("trebuchetms", 18)
        self.value_font = pygame.font.SysFont("trebuchetms", 34, bold=True)
        self.win_font = pygame.font.SysFont("trebuchetms", 50, bold=True)
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

    def reset(self) -> None:
        """Build a fresh puzzle board and clear runtime state."""
        self.frame_index = 0
        self.board_index = getattr(self, "board_index", -1) + 1
        self.score = 0
        self.matches_cleared = 0
        self.shuffle_count = 0
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.win = False
        self.auto_plan = []
        self.auto_wait_frames = 1
        self.error_flash_frames = 0
        self.error_flash_positions: list[CellPos] = []
        self.animating = False
        self.anim_frame = 0
        self.anim_paths: list[list[SearchPos]] = []
        self.anim_motions: list[TileMotion] = []
        self.anim_ghosts: list[TileGhost] = []
        self.anim_hidden_ids: set[int] = set()
        self.anim_has_match = False
        self.next_tile_id = 1
        self.prepare_new_board()
        self.board_mask = self.build_board_mask()
        self.board = self.make_empty_board()
        self.populate_board()
        self.cursor_row, self.cursor_col = self.get_default_cursor_cell()
        self.selected_positions: list[CellPos] = []
        self.prev_action = self.BLANK_ACTION.copy()

    def prepare_new_board(self) -> None:
        """Allow subclasses to initialize per-board state before tiles are created."""
        return None

    def build_board_mask(self) -> list[list[bool]]:
        """Return the playable cell mask used for cursor movement and tile placement."""
        return [[True for _ in range(self.play_cols)] for _ in range(self.play_rows)]

    def make_empty_board(self) -> list[list[OnetTile | None]]:
        """Create an empty board using the current play size."""
        return [[None for _ in range(self.play_cols)] for _ in range(self.play_rows)]

    def get_default_cursor_cell(self) -> CellPos:
        """Return the starting cursor cell near the center of the board."""
        center_row = self.play_rows // 2
        center_col = self.play_cols // 2
        if self.is_play_cell(center_row, center_col):
            return center_row, center_col
        for distance in range(self.play_rows + self.play_cols):
            for row in range(self.play_rows):
                for col in range(self.play_cols):
                    if abs(row - center_row) + abs(col - center_col) == distance and self.is_play_cell(row, col):
                        return row, col
        return 0, 0

    def populate_board(self) -> None:
        """Create a random tile layout for the base game."""
        tiles = self.build_initial_tiles()
        self.randomize_tiles_until_match(tiles)

    def build_initial_tiles(self) -> list[OnetTile]:
        """Create all tiles for a new base puzzle before they are placed on the board."""
        cell_count = sum(1 for row, col in self.iter_play_cells() if self.board_mask[row][col])
        pair_contents = self.build_pair_contents(cell_count // 2)
        tiles = []
        for content in pair_contents:
            tiles.append(self.make_tile(-1, -1, content))
            tiles.append(self.make_tile(-1, -1, content))
        random.shuffle(tiles)
        return tiles

    def build_pair_contents(self, pair_count: int) -> list[object]:
        """Return the list of content values used for the initial tile pairs."""
        symbols = self.get_symbol_pool()
        contents = [symbols[index % len(symbols)] for index in range(pair_count)]
        random.shuffle(contents)
        return contents

    def get_symbol_pool(self) -> list[str]:
        """Return the base tile symbol names drawn by this class."""
        return ["sun", "moon", "star", "diamond", "plus", "cross", "ring", "leaf", "drop", "bolt", "wave", "crown", "kite", "gem", "seed", "hex"]

    def make_tile(self, row: int, col: int, content: object) -> OnetTile:
        """Create one tile object with colors derived from its content."""
        tile = OnetTile(
            id=self.next_tile_id,
            row=row,
            col=col,
            content=content,
            symbol="",
            fill_color=(0, 0, 0),
            edge_color=(0, 0, 0),
            accent_color=(0, 0, 0),
            text_color=(0, 0, 0),
            move_direction=self.get_tile_move_direction(content),
        )
        self.next_tile_id += 1
        self.refresh_tile_style(tile)
        return tile

    def refresh_tile_style(self, tile: OnetTile) -> None:
        """Refresh one tile's drawing fields after its content changes."""
        tile.symbol = self.get_tile_symbol(tile.content)
        palette_index = self.get_content_palette_index(tile.content)
        tile.fill_color, tile.edge_color, tile.accent_color, tile.text_color = self.tile_palettes[palette_index % len(self.tile_palettes)]
        tile.move_direction = self.get_tile_move_direction_for_tile(tile)

    def set_tile_content(self, tile: OnetTile, content: object) -> None:
        """Replace one tile's content and update its derived drawing state."""
        tile.content = content
        self.refresh_tile_style(tile)

    def get_tile_symbol(self, content: object) -> str:
        """Return the symbol key the base renderer should draw for this content."""
        if isinstance(content, str):
            return content
        return self.get_symbol_pool()[self.get_content_palette_index(content) % len(self.get_symbol_pool())]

    def get_content_palette_index(self, content: object) -> int:
        """Return a stable palette index for one content value."""
        symbols = self.get_symbol_pool()
        if isinstance(content, str) and content in symbols:
            return symbols.index(content)
        return sum((index + 1) * ord(char) for index, char in enumerate(str(content)))

    def get_tile_move_direction(self, content: object) -> tuple[int, int]:
        """Return the tile's movement preference used by future subclasses."""
        return 0, 0

    def get_tile_move_direction_for_tile(self, tile: OnetTile) -> tuple[int, int]:
        """Return the tile direction, allowing subclasses to use the tile position."""
        return self.get_tile_move_direction(tile.content)

    def get_required_selection_size(self) -> int:
        """Return how many tiles must be selected before the game resolves a choice."""
        return 2

    def get_rule_prompt_text(self) -> str:
        """Return the rule sentence implemented by the base class."""
        return "Match two identical tiles. The line connecting them must pass only through empty spaces and it cannot bend more than twice."

    def get_additional_prompt_sentences(self) -> list[str]:
        """Return extra prompt sentences for subclasses with custom rules."""
        return []

    def getPrompt(self) -> str:
        """Return the training prompt describing controls and the current rule set."""
        parts = [
            f"This is {self.name}.",
            "Use Arrow keys to move the cursor on the board.",
            "Press W to select or deselect the tile under the cursor.",
            self.get_rule_prompt_text(),
        ]
        parts.extend(self.get_additional_prompt_sentences())
        parts.append("When no valid match remains, the board reshuffles and play continues.")
        return " ".join(parts)

    def get_pressed_action(self, action: ActionState) -> ActionState:
        """Convert held keys into edge-triggered key presses."""
        pressed = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action.get(key, False):
                pressed[key] = True
        self.prev_action = action.copy()
        return pressed

    def update(self, action: ActionState) -> bool:
        """Advance animations, resolve input, and handle reset timing."""
        self.frame_index += 1
        pressed = self.get_pressed_action(action)

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.error_flash_frames > 0:
            self.error_flash_frames -= 1
            if self.error_flash_frames == 0:
                self.error_flash_positions = []

        if self.animating:
            self.anim_frame += 1
            if self.anim_frame >= self.get_active_anim_total_frames():
                self.finish_animation()
            return False

        if self.win:
            self.end_screen_frames += 1
            if self.end_screen_frames == self.end_screen_event_frame:
                self.end_event_pending = True
            if self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        self.handle_idle_input(pressed)
        return False

    def handle_idle_input(self, pressed: ActionState) -> None:
        """Apply cursor movement and selection input while the board is idle."""
        if pressed["LU"]:
            self.move_cursor(-1, 0)
        elif pressed["LD"]:
            self.move_cursor(1, 0)
        elif pressed["LL"]:
            self.move_cursor(0, -1)
        elif pressed["LR"]:
            self.move_cursor(0, 1)

        if pressed["W"]:
            self.toggle_cursor_selection()

    def move_cursor(self, dr: int, dc: int) -> None:
        """Move the cursor to the next playable cell in one direction."""
        row = self.cursor_row + dr
        col = self.cursor_col + dc
        while 0 <= row < self.play_rows and 0 <= col < self.play_cols:
            if self.is_play_cell(row, col):
                self.cursor_row = row
                self.cursor_col = col
                return
            row += dr
            col += dc

    def toggle_cursor_selection(self) -> None:
        """Select or deselect the tile under the cursor and resolve a full choice."""
        row = self.cursor_row
        col = self.cursor_col
        if not self.is_play_cell(row, col):
            return
        if self.board[row][col] is None:
            return

        current = (row, col)
        if current in self.selected_positions:
            self.selected_positions = [position for position in self.selected_positions if position != current]
            return

        if len(self.selected_positions) >= self.get_required_selection_size():
            self.selected_positions = []

        self.selected_positions.append(current)
        if len(self.selected_positions) == self.get_required_selection_size():
            self.resolve_ready_selection()

    def resolve_ready_selection(self) -> None:
        """Try to match the current selection and start the next animation state."""
        positions = self.selected_positions[:]
        result = self.try_create_match(positions)
        if result is None:
            self.error_flash_positions = positions[:]
            self.error_flash_frames = 12
            self.selected_positions = [positions[-1]]
            return
        self.selected_positions = []
        snapshot = self.capture_tile_snapshot()
        self.apply_match_effect(result)
        self.score += result.score_gain
        self.matches_cleared += 1
        self.begin_transition_from_snapshot(snapshot, result.path_groups, True)

    def try_create_match(self, positions: list[CellPos]) -> MatchResult | None:
        """Return a match object when the selected tiles satisfy this game's rule."""
        first_row, first_col = positions[0]
        second_row, second_col = positions[1]
        first_tile = self.board[first_row][first_col]
        second_tile = self.board[second_row][second_col]
        if first_tile is None or second_tile is None:
            return None
        if not self.are_tiles_compatible(first_tile, second_tile):
            return None
        path = self.find_basic_connection_path(first_row, first_col, second_row, second_col)
        if path is None:
            return None
        return MatchResult(positions=positions, path_groups=[path], score_gain=1)

    def are_tiles_compatible(self, first_tile: OnetTile, second_tile: OnetTile) -> bool:
        """Return whether two tiles can match before the path rule is checked."""
        return first_tile.content == second_tile.content

    def apply_match_effect(self, result: MatchResult) -> None:
        """Remove the matched tiles and let subclasses add board motion afterwards."""
        self.remove_tiles(result.positions)

    def remove_tiles(self, positions: list[CellPos]) -> None:
        """Clear the listed cells from the board."""
        for row, col in positions:
            self.board[row][col] = None

    def capture_tile_snapshot(self) -> list[tuple[OnetTile, int, int]]:
        """Capture every tile and its current position before a board mutation."""
        return [(tile, tile.row, tile.col) for tile in self.iter_tiles()]

    def begin_transition_from_snapshot(self, snapshot: list[tuple[OnetTile, int, int]], path_groups: list[list[SearchPos]], has_match: bool) -> None:
        """Build ghost and movement animations after the board has already been mutated."""
        new_positions = {tile.id: (tile.row, tile.col) for tile in self.iter_tiles()}
        motions = []
        ghosts = []
        hidden_ids = set()

        for tile, old_row, old_col in snapshot:
            if tile.id not in new_positions:
                ghosts.append(TileGhost(tile, old_row, old_col))
                continue
            new_row, new_col = new_positions[tile.id]
            if old_row != new_row or old_col != new_col:
                motions.append(TileMotion(tile, old_row, old_col, new_row, new_col))
                hidden_ids.add(tile.id)

        self.animating = len(path_groups) > 0 or len(motions) > 0 or len(ghosts) > 0
        self.anim_frame = 0
        self.anim_paths = [path[:] for path in path_groups]
        self.anim_motions = motions
        self.anim_ghosts = ghosts
        self.anim_hidden_ids = hidden_ids
        self.anim_has_match = has_match
        if not self.animating:
            self.finish_animation()

    def finish_animation(self) -> None:
        """End the active animation and move the board to the next stable state."""
        self.animating = False
        self.anim_frame = 0
        self.anim_paths = []
        self.anim_motions = []
        self.anim_ghosts = []
        self.anim_hidden_ids = set()
        self.anim_has_match = False
        self.handle_stable_board_state()

    def handle_stable_board_state(self) -> None:
        """Handle win detection and automatic reshuffling after animations stop."""
        if not self.has_tiles_left():
            self.win = True
            self.end_screen_frames = 0
            return
        if len(self.get_available_matches()) == 0:
            self.shuffle_remaining_tiles()

    def shuffle_remaining_tiles(self) -> None:
        """Randomly rearrange the remaining tiles until at least one legal move exists."""
        snapshot = self.capture_tile_snapshot()
        tiles = [tile for tile, _, _ in snapshot]
        self.randomize_tiles_until_match(tiles, True)
        self.shuffle_count += 1
        self.begin_transition_from_snapshot(snapshot, [], False)

    def randomize_tiles_until_match(self, tiles: list[OnetTile], is_shuffle: bool = False) -> None:
        """Keep randomly placing tiles until the board has at least one legal move."""
        attempt = 0
        while True:
            attempt += 1
            if is_shuffle:
                self.reassign_tiles_for_shuffle(tiles, attempt)
            self.board = self.make_empty_board()
            self.place_tiles_randomly(tiles)
            if len(tiles) == 0 or len(self.get_available_matches()) > 0:
                return

    def reassign_tiles_for_shuffle(self, tiles: list[OnetTile], attempt: int) -> None:
        """Allow subclasses to rewrite remaining tile contents before another shuffle attempt."""
        return None

    def place_tiles_randomly(self, tiles: list[OnetTile]) -> None:
        """Place all given tiles onto random playable cells."""
        cells = self.iter_play_cells()
        random.shuffle(cells)
        random.shuffle(tiles)
        for tile, (row, col) in zip(tiles, cells):
            self.set_tile(row, col, tile)

    def has_tiles_left(self) -> bool:
        """Return whether the board still contains at least one tile."""
        for tile in self.iter_tiles():
            if tile is not None:
                return True
        return False

    def is_play_cell(self, row: int, col: int) -> bool:
        """Return whether a board coordinate belongs to the playable mask."""
        return self.board_mask[row][col]

    def iter_play_cells(self) -> list[CellPos]:
        """Return all playable board coordinates."""
        return [(row, col) for row in range(self.play_rows) for col in range(self.play_cols) if self.board_mask[row][col]]

    def iter_tiles(self) -> list[OnetTile]:
        """Return every tile currently present on the board."""
        return [self.board[row][col] for row, col in self.iter_play_cells() if self.board[row][col] is not None]

    def set_tile(self, row: int, col: int, tile: OnetTile) -> None:
        """Place a tile into one cell and update its stored coordinates."""
        tile.row = row
        tile.col = col
        tile.move_direction = self.get_tile_move_direction_for_tile(tile)
        self.board[row][col] = tile

    def take_tile(self, row: int, col: int) -> OnetTile | None:
        """Remove and return one tile from the board."""
        tile = self.board[row][col]
        self.board[row][col] = None
        return tile

    def move_tile(self, from_row: int, from_col: int, to_row: int, to_col: int) -> None:
        """Move one tile to another cell."""
        tile = self.take_tile(from_row, from_col)
        if tile is not None:
            self.set_tile(to_row, to_col, tile)

    def get_available_matches(self) -> list[MatchResult]:
        """Return every currently legal match that the base autoplay can use."""
        positions = [(row, col) for row, col in self.iter_play_cells() if self.board[row][col] is not None]
        matches = []
        for index, first in enumerate(positions):
            for second in positions[index + 1:]:
                result = self.try_create_match([first, second])
                if result is not None:
                    matches.append(result)
        return matches

    def find_connection_result(self, first_row: int, first_col: int, second_row: int, second_col: int, max_turns: int | None = 2) -> tuple[list[SearchPos], int] | None:
        """Find a connection path and its turn count, optionally limited by a maximum."""
        start = (first_row + 1, first_col + 1)
        end = (second_row + 1, second_col + 1)
        directions = [(-1, 0), (0, -1), (0, 1), (1, 0)]
        best = {}
        parents = {}
        heap = []

        for direction_index, (dr, dc) in enumerate(directions):
            next_row = start[0] + dr
            next_col = start[1] + dc
            if not self.is_search_cell_open(next_row, next_col, start, end):
                continue
            state = (next_row, next_col, direction_index)
            best[state] = (0, 1)
            parents[state] = None
            heapq.heappush(heap, (0, 1, next_row, next_col, direction_index))

        while len(heap) > 0:
            turns, steps, row, col, direction_index = heapq.heappop(heap)
            state = (row, col, direction_index)
            if best[state] != (turns, steps):
                continue
            if (row, col) == end:
                return self.rebuild_connection_path(state, parents, start), turns
            for next_direction_index, (dr, dc) in enumerate(directions):
                next_row = row + dr
                next_col = col + dc
                if not self.is_search_cell_open(next_row, next_col, start, end):
                    continue
                next_turns = turns if next_direction_index == direction_index else turns + 1
                if max_turns is not None and next_turns > max_turns:
                    continue
                next_steps = steps + 1
                next_state = (next_row, next_col, next_direction_index)
                if next_state in best and best[next_state] <= (next_turns, next_steps):
                    continue
                best[next_state] = (next_turns, next_steps)
                parents[next_state] = state
                heapq.heappush(heap, (next_turns, next_steps, next_row, next_col, next_direction_index))
        return None

    def find_basic_connection_path(self, first_row: int, first_col: int, second_row: int, second_col: int) -> list[SearchPos] | None:
        """Find a connection path with at most two bends between two board cells."""
        result = self.find_connection_result(first_row, first_col, second_row, second_col, 2)
        if result is None:
            return None
        return result[0]

    def rebuild_connection_path(self, state: tuple[int, int, int], parents: dict[tuple[int, int, int], tuple[int, int, int] | None], start: SearchPos) -> list[SearchPos]:
        """Rebuild and compress one path from the connection search parent map."""
        points = [(state[0], state[1])]
        cursor = state
        while parents[cursor] is not None:
            cursor = parents[cursor]
            points.append((cursor[0], cursor[1]))
        points.append(start)
        points.reverse()
        return self.compress_search_path(points)

    def count_path_turns(self, path: list[SearchPos]) -> int:
        """Count how many times a path changes direction."""
        return len(path) - 2 if len(path) >= 2 else 0

    def is_search_cell_open(self, row: int, col: int, start: SearchPos, end: SearchPos) -> bool:
        """Return whether the path can pass through a search-grid coordinate."""
        if not (0 <= row <= self.play_rows + 1 and 0 <= col <= self.play_cols + 1):
            return False
        if (row, col) == start or (row, col) == end:
            return True
        if row == 0 or row == self.play_rows + 1 or col == 0 or col == self.play_cols + 1:
            return True
        board_row = row - 1
        board_col = col - 1
        return self.is_path_board_cell_open(board_row, board_col)

    def is_path_board_cell_open(self, row: int, col: int) -> bool:
        """Return whether a board cell can be crossed by a connection path."""
        if not self.board_mask[row][col]:
            return True
        return self.board[row][col] is None

    def compress_search_path(self, path: list[SearchPos]) -> list[SearchPos]:
        """Remove duplicate and straight-through interior points from one path."""
        cleaned = []
        for point in path:
            if len(cleaned) == 0 or cleaned[-1] != point:
                cleaned.append(point)
        changed = True
        while changed and len(cleaned) >= 3:
            changed = False
            for index in range(1, len(cleaned) - 1):
                previous_point = cleaned[index - 1]
                point = cleaned[index]
                next_point = cleaned[index + 1]
                if (previous_point[0] == point[0] == next_point[0]) or (previous_point[1] == point[1] == next_point[1]):
                    cleaned.pop(index)
                    changed = True
                    break
        return cleaned

    def get_layout(self) -> tuple[int, int, int, pygame.Rect]:
        """Return tile size, board origin, and the side panel rectangle."""
        panel_rect = pygame.Rect(self.width - self.panel_width - self.margin, self.margin, self.panel_width, self.height - self.margin * 2)
        board_area_width = self.width - panel_rect.width - self.margin * 3 - self.board_padding * 2
        board_area_height = self.height - self.margin * 2 - self.board_padding * 2
        tile_size = board_area_width // self.play_cols if board_area_width // self.play_cols < board_area_height // self.play_rows else board_area_height // self.play_rows
        board_width = tile_size * self.play_cols
        board_height = tile_size * self.play_rows
        board_left = self.margin + self.board_padding + (board_area_width - board_width) // 2
        board_top = self.margin + self.board_padding + (board_area_height - board_height) // 2
        return tile_size, board_left, board_top, panel_rect

    def get_board_rect(self, tile_size: int, board_left: int, board_top: int) -> pygame.Rect:
        """Return the outer board rectangle including the visible frame."""
        return pygame.Rect(board_left - 12, board_top - 12, tile_size * self.play_cols + 24, tile_size * self.play_rows + 24)

    def get_cell_rect(self, row: int, col: int, tile_size: int, board_left: int, board_top: int) -> pygame.Rect:
        """Return one board cell rectangle in screen space."""
        return pygame.Rect(board_left + col * tile_size, board_top + row * tile_size, tile_size, tile_size)

    def get_search_point_pixel(self, search_point: SearchPos, tile_size: int, board_left: int, board_top: int) -> tuple[int, int]:
        """Convert one padded-grid point into the pixel center used for path drawing."""
        x = round(board_left + (search_point[1] - 0.5) * tile_size)
        y = round(board_top + (search_point[0] - 0.5) * tile_size)
        return x, y

    def get_active_anim_total_frames(self) -> int:
        """Return the duration for the current animation."""
        if self.anim_has_match:
            return self.selection_flash_total_frames + self.movement_anim_total_frames
        return self.movement_anim_total_frames

    def get_anim_progress(self) -> float:
        """Return eased animation progress from zero to one."""
        total = self.get_active_anim_total_frames()
        t = self.anim_frame / total
        if t < 0:
            return 0.0
        if t > 1:
            return 1.0
        return 1.0 - (1.0 - t) * (1.0 - t)

    def draw_background(self) -> None:
        """Paint the scene background with a soft gradient and floating lights."""
        for y in range(self.height):
            t = y / (self.height - 1)
            color = (
                round(self.background_top[0] * (1.0 - t) + self.background_bottom[0] * t),
                round(self.background_top[1] * (1.0 - t) + self.background_bottom[1] * t),
                round(self.background_top[2] * (1.0 - t) + self.background_bottom[2] * t),
            )
            pygame.draw.line(self.screen, color, (0, y), (self.width, y))
        for index in range(11):
            radius = 22 + (index % 4) * 14
            x = round(self.width * (0.12 + 0.08 * index))
            y = round(self.height * (0.15 + 0.06 * (index % 5)))
            alpha = 26 + index * 5
            glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 255, 255, alpha), (radius * 2, radius * 2), radius)
            self.screen.blit(glow, (x - radius * 2, y - radius * 2))

    def draw_panel(self, panel_rect: pygame.Rect) -> None:
        """Draw the information panel without showing the rules text."""
        pygame.draw.rect(self.screen, self.panel_fill, panel_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.panel_line, panel_rect, 2, border_radius=20)
        self.screen.blit(self.title_font.render(self.name, True, self.text_primary), (panel_rect.x + 20, panel_rect.y + 16))
        info_lines = self.get_panel_lines()
        for index, line in enumerate(info_lines):
            surface = self.panel_font.render(line, True, self.text_primary if index == 0 else self.text_soft)
            self.screen.blit(surface, (panel_rect.x + 20, panel_rect.y + 76 + index * 38))

        preview_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 112 + len(info_lines) * 38, panel_rect.width - 40, 146)
        pygame.draw.rect(self.screen, (31, 47, 69), preview_rect, border_radius=16)
        pygame.draw.rect(self.screen, self.panel_line, preview_rect, 2, border_radius=16)
        self.screen.blit(self.small_font.render(f"Cursor On:", True, self.text_soft), (preview_rect.x + 16, preview_rect.y + 12))
        tile = self.board[self.cursor_row][self.cursor_col]
        if tile is None:
            self.screen.blit(self.panel_font.render("Empty", True, self.text_primary), (preview_rect.x + 16, preview_rect.y + 100))
        else:
            preview_tile_rect = pygame.Rect(preview_rect.x + 16, preview_rect.y + 34, 82, 66)
            self.draw_tile_box(tile, preview_tile_rect, 1.0, False, False)
            label = self.get_tile_label(tile)
            if label:
                self.screen.blit(self.panel_font.render(label, True, self.text_primary), (preview_rect.x + 16, preview_rect.y + 100))

    def get_panel_lines(self) -> list[str]:
        """Return the short status lines shown in the side panel."""
        return [f"Tiles Left {len(self.iter_tiles())}"]

    def get_tile_label(self, tile: OnetTile) -> str:
        """Return a short text label that can appear in the side preview."""
        if isinstance(tile.content, str):
            return tile.content.title()
        return str(tile.content)

    def draw_board_frame(self, board_rect: pygame.Rect) -> None:
        """Draw the board frame and shadow."""
        shadow = board_rect.move(0, 10)
        pygame.draw.rect(self.screen, self.board_shadow, shadow, border_radius=24)
        pygame.draw.rect(self.screen, (244, 248, 253), board_rect, border_radius=24)
        inner = board_rect.inflate(-10, -10)
        pygame.draw.rect(self.screen, (114, 146, 182), inner, 3, border_radius=20)

    def draw_slots(self, tile_size: int, board_left: int, board_top: int) -> None:
        """Draw the board slot backgrounds under tiles."""
        for row in range(self.play_rows):
            for col in range(self.play_cols):
                rect = self.get_cell_rect(row, col, tile_size, board_left, board_top)
                if not self.board_mask[row][col]:
                    pygame.draw.rect(self.screen, self.slot_gap_fill, rect, border_radius=14)
                    continue
                fill = self.slot_fill_a if (row + col) % 2 == 0 else self.slot_fill_b
                pygame.draw.rect(self.screen, fill, rect, border_radius=14)
                pygame.draw.rect(self.screen, (171, 191, 215), rect, 1, border_radius=14)

    def draw_tiles(self, tile_size: int, board_left: int, board_top: int) -> None:
        """Draw all static tiles that are not currently replaced by motion overlays."""
        for tile in self.iter_tiles():
            if tile.id in self.anim_hidden_ids:
                continue
            rect = self.get_cell_rect(tile.row, tile.col, tile_size, board_left, board_top).inflate(-6, -6)
            is_selected = (tile.row, tile.col) in self.selected_positions
            is_error = (tile.row, tile.col) in self.error_flash_positions and self.error_flash_frames > 0
            self.draw_tile_box(tile, rect, 1.0, is_selected, is_error)

    def draw_tile_box(self, tile: OnetTile, rect: pygame.Rect, alpha_scale: float, is_selected: bool, is_error: bool) -> None:
        """Draw one tile face with either a symbol or subclass-specific content art."""
        surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        fill_alpha = round(255 * alpha_scale)
        edge_alpha = round(255 * alpha_scale)
        shadow_rect = pygame.Rect(0, 6, rect.width, rect.height - 2)
        pygame.draw.rect(surface, (0, 0, 0, round(66 * alpha_scale)), shadow_rect, border_radius=18)
        pygame.draw.rect(surface, (*tile.fill_color, fill_alpha), pygame.Rect(0, 0, rect.width, rect.height - 6), border_radius=18)
        pygame.draw.rect(surface, (*tile.edge_color, edge_alpha), pygame.Rect(0, 0, rect.width, rect.height - 6), 3, border_radius=18)
        if is_selected:
            pygame.draw.rect(surface, (*self.selection_color, edge_alpha), pygame.Rect(2, 2, rect.width - 4, rect.height - 10), 4, border_radius=16)
        if is_error:
            pygame.draw.rect(surface, (*self.error_color, edge_alpha), pygame.Rect(2, 2, rect.width - 4, rect.height - 10), 4, border_radius=16)
        self.draw_tile_content(surface, tile, pygame.Rect(0, 0, rect.width, rect.height - 6), alpha_scale)
        self.draw_tile_overlay(surface, tile, pygame.Rect(0, 0, rect.width, rect.height - 6), alpha_scale)
        self.screen.blit(surface, rect.topleft)

    def draw_tile_content(self, surface: pygame.Surface, tile: OnetTile, rect: pygame.Rect, alpha_scale: float) -> None:
        """Draw the tile-specific face art for the base game."""
        self.draw_symbol_shape(surface, tile.symbol, rect, tile.accent_color, alpha_scale)

    def draw_tile_overlay(self, surface: pygame.Surface, tile: OnetTile, rect: pygame.Rect, alpha_scale: float) -> None:
        """Allow subclasses to draw extra overlays such as arrows or number markers."""
        return None

    def draw_symbol_shape(self, surface: pygame.Surface, symbol: str, rect: pygame.Rect, color: tuple[int, int, int], alpha_scale: float) -> None:
        """Draw one base symbol centered inside a tile."""
        draw_color = (*color, round(255 * alpha_scale))
        shade_color = (*tile_safe_subtract(color, 52), round(255 * alpha_scale))
        center = rect.center
        size = rect.width if rect.width < rect.height else rect.height
        heavy_stroke = round(size * 0.11)
        medium_stroke = round(size * 0.075)
        light_stroke = round(size * 0.05)
        corner_radius = round(size * 0.08)
        if symbol == "sun":
            pygame.draw.circle(surface, draw_color, center, round(size * 0.14))
            for index in range(8):
                angle = math.tau * index / 8
                inner = (round(center[0] + math.cos(angle) * rect.width * 0.16), round(center[1] + math.sin(angle) * rect.height * 0.16))
                outer = (round(center[0] + math.cos(angle) * rect.width * 0.32), round(center[1] + math.sin(angle) * rect.height * 0.32))
                pygame.draw.line(surface, draw_color, inner, outer, light_stroke)
        elif symbol == "moon":
            pygame.draw.circle(surface, draw_color, center, round(size * 0.26))
            pygame.draw.circle(surface, shade_color, rect_point(rect, 0.58, 0.43), round(size * 0.26))
        elif symbol == "star":
            points = []
            for index in range(10):
                angle = -math.pi / 2 + math.tau * index / 10
                radius = size * 0.30 if index % 2 == 0 else size * 0.12
                points.append((round(center[0] + math.cos(angle) * radius), round(center[1] + math.sin(angle) * radius)))
            pygame.draw.polygon(surface, draw_color, points)
        elif symbol == "diamond":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.5, 0.12), rect_point(rect, 0.86, 0.5), rect_point(rect, 0.5, 0.88), rect_point(rect, 0.14, 0.5)])
        elif symbol == "plus":
            pygame.draw.rect(surface, draw_color, rect_box(rect, 0.42, 0.12, 0.16, 0.76), border_radius=corner_radius)
            pygame.draw.rect(surface, draw_color, rect_box(rect, 0.12, 0.42, 0.76, 0.16), border_radius=corner_radius)
        elif symbol == "cross":
            pygame.draw.line(surface, draw_color, rect_point(rect, 0.18, 0.24), rect_point(rect, 0.82, 0.76), heavy_stroke)
            pygame.draw.line(surface, draw_color, rect_point(rect, 0.82, 0.24), rect_point(rect, 0.18, 0.76), heavy_stroke)
        elif symbol == "ring":
            pygame.draw.circle(surface, draw_color, center, round(size * 0.26), medium_stroke)
        elif symbol == "leaf":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.5, 0.12), rect_point(rect, 0.84, 0.47), rect_point(rect, 0.54, 0.86), rect_point(rect, 0.16, 0.53)])
            pygame.draw.line(surface, shade_color, rect_point(rect, 0.46, 0.8), rect_point(rect, 0.58, 0.2), light_stroke)
        elif symbol == "drop":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.5, 0.08), rect_point(rect, 0.8, 0.58), rect_point(rect, 0.5, 0.88), rect_point(rect, 0.2, 0.58)])
        elif symbol == "bolt":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.46, 0.12), rect_point(rect, 0.62, 0.12), rect_point(rect, 0.52, 0.46), rect_point(rect, 0.66, 0.46), rect_point(rect, 0.42, 0.88), rect_point(rect, 0.5, 0.54), rect_point(rect, 0.34, 0.54)])
        elif symbol == "wave":
            for y_ratio in [0.28, 0.5, 0.72]:
                pygame.draw.lines(surface, draw_color, False, [rect_point(rect, 0.12, y_ratio), rect_point(rect, 0.3, y_ratio - 0.08), rect_point(rect, 0.5, y_ratio + 0.05), rect_point(rect, 0.7, y_ratio - 0.08), rect_point(rect, 0.88, y_ratio)], light_stroke)
        elif symbol == "crown":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.14, 0.78), rect_point(rect, 0.24, 0.22), rect_point(rect, 0.42, 0.42), rect_point(rect, 0.5, 0.12), rect_point(rect, 0.58, 0.42), rect_point(rect, 0.76, 0.22), rect_point(rect, 0.86, 0.78)])
        elif symbol == "kite":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.5, 0.12), rect_point(rect, 0.82, 0.5), rect_point(rect, 0.5, 0.84), rect_point(rect, 0.18, 0.5)])
            pygame.draw.line(surface, shade_color, center, rect_point(rect, 0.5, 0.94), light_stroke)
        elif symbol == "gem":
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.24, 0.22), rect_point(rect, 0.76, 0.22), rect_point(rect, 0.86, 0.44), rect_point(rect, 0.5, 0.86), rect_point(rect, 0.14, 0.44)])
            pygame.draw.line(surface, shade_color, rect_point(rect, 0.5, 0.22), rect_point(rect, 0.5, 0.86), light_stroke)
        elif symbol == "seed":
            pygame.draw.ellipse(surface, draw_color, rect_box(rect, 0.2, 0.12, 0.6, 0.76))
            pygame.draw.line(surface, shade_color, rect_point(rect, 0.3, 0.64), rect_point(rect, 0.72, 0.34), light_stroke)
        else:
            pygame.draw.polygon(surface, draw_color, [rect_point(rect, 0.5, 0.12), rect_point(rect, 0.82, 0.36), rect_point(rect, 0.82, 0.64), rect_point(rect, 0.5, 0.88), rect_point(rect, 0.18, 0.64), rect_point(rect, 0.18, 0.36)])

    def draw_tile_text(self, surface: pygame.Surface, text: str, rect: pygame.Rect, color: tuple[int, int, int], alpha_scale: float) -> None:
        """Draw centered tile text sized for one or two characters."""
        font = self.value_font if len(text) == 1 else self.panel_font
        label = font.render(text, True, color)
        label.set_alpha(round(255 * alpha_scale))
        surface.blit(label, label.get_rect(center=rect.center))

    def draw_direction_inner_shade(self, surface: pygame.Surface, rect: pygame.Rect, direction: tuple[int, int], color: tuple[int, int, int], alpha_scale: float) -> None:
        """Draw a soft inner shade on the side of the tile that matches the move direction."""
        if direction == (0, 0):
            return
        shade_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        local_rect = pygame.Rect(0, 0, rect.width, rect.height)
        dark_color = tile_safe_subtract(color, 36)
        strip_specs = {
            (-1, 0): (0.0, 0.0, 1.0, 0.2),
            (1, 0): (0.0, 0.8, 1.0, 0.2),
            (0, -1): (0.0, 0.0, 0.2, 1.0),
            (0, 1): (0.8, 0.0, 0.2, 1.0),
        }
        if direction not in strip_specs:
            return
        pygame.draw.rect(shade_surface, (*dark_color, round(64 * alpha_scale)), rect_box(local_rect, *strip_specs[direction]))
        face_mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(face_mask, (255, 255, 255, 255), local_rect, border_radius=18)
        shade_surface.blit(face_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shade_surface, rect.topleft)

    def draw_path_overlay(self, tile_size: int, board_left: int, board_top: int) -> None:
        """Draw the connection lines for a successful match."""
        if len(self.anim_paths) == 0:
            return
        total = self.get_active_anim_total_frames()
        fade = 1.0 if self.anim_frame <= self.selection_flash_total_frames else 1.0 - (self.anim_frame - self.selection_flash_total_frames) / (total - self.selection_flash_total_frames)
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for path in self.anim_paths:
            points = [self.get_search_point_pixel(point, tile_size, board_left, board_top) for point in path]
            if len(points) >= 2:
                pygame.draw.lines(overlay, (*self.path_color, round(255 * fade)), False, points, 8)
                for point in points:
                    pygame.draw.circle(overlay, (*self.path_color, round(255 * fade)), point, 7)
        self.screen.blit(overlay, (0, 0))

    def draw_animation_tiles(self, tile_size: int, board_left: int, board_top: int) -> None:
        """Draw ghosted and moving tiles above the static board."""
        progress = self.get_anim_progress()
        for ghost in self.anim_ghosts:
            rect = self.get_cell_rect(ghost.row, ghost.col, tile_size, board_left, board_top).inflate(-6, -6)
            alpha_scale = 1.0 - progress
            self.draw_tile_box(ghost.tile, rect, alpha_scale, False, False)
        for motion in self.anim_motions:
            row = motion.from_row + (motion.to_row - motion.from_row) * progress
            col = motion.from_col + (motion.to_col - motion.from_col) * progress
            rect = pygame.Rect(round(board_left + col * tile_size + 3), round(board_top + row * tile_size + 3), tile_size - 6, tile_size - 6)
            self.draw_tile_box(motion.tile, rect, 1.0, False, False)

    def draw_cursor(self, tile_size: int, board_left: int, board_top: int) -> None:
        """Draw the board cursor."""
        rect = self.get_cell_rect(self.cursor_row, self.cursor_col, tile_size, board_left, board_top).inflate(-2, -2)
        pygame.draw.rect(self.screen, self.cursor_color, rect, 4, border_radius=16)

    def draw_win_overlay(self) -> None:
        """Draw the solved overlay before the next board starts."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((5, 10, 16, 164))
        self.screen.blit(overlay, (0, 0))
        title = self.win_font.render("Board Cleared", True, self.win_color)
        detail = self.panel_font.render(f"Matches {self.matches_cleared}   Shuffles {self.shuffle_count}", True, self.text_primary)
        self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 20)))
        self.screen.blit(detail, detail.get_rect(center=(self.width // 2, self.height // 2 + 32)))

    def draw(self) -> None:
        """Render the full board, overlays, and information panel."""
        self.draw_background()
        tile_size, board_left, board_top, panel_rect = self.get_layout()
        board_rect = self.get_board_rect(tile_size, board_left, board_top)
        self.draw_board_frame(board_rect)
        self.draw_slots(tile_size, board_left, board_top)
        self.draw_tiles(tile_size, board_left, board_top)
        self.draw_animation_tiles(tile_size, board_left, board_top)
        self.draw_path_overlay(tile_size, board_left, board_top)
        self.draw_cursor(tile_size, board_left, board_top)
        self.draw_panel(panel_rect)
        if self.win:
            self.draw_win_overlay()

    def choose_auto_match(self, matches: list[MatchResult]) -> MatchResult:
        """Pick one nearby match with a little randomness for autoplay."""
        ranked = []
        for match in matches:
            distance = 0
            probe_row = self.cursor_row
            probe_col = self.cursor_col
            for row, col in match.positions:
                distance += abs(row - probe_row) + abs(col - probe_col)
                probe_row = row
                probe_col = col
            ranked.append((distance + random.random() * 1.6, match))
        ranked.sort(key=lambda item: item[0])
        return random.choice([item[1] for item in ranked[:min(6, len(ranked))]])

    def get_auto_mismatch_chance(self) -> float:
        """Return the small chance that autoplay intentionally picks a bad pair."""
        return 0.08

    def choose_auto_unmatchable_selection(self) -> list[CellPos] | None:
        """Pick one occupied selection that does not currently form a legal match."""
        positions = [(row, col) for row, col in self.iter_play_cells() if self.board[row][col] is not None]
        required = self.get_required_selection_size()
        if len(positions) < required:
            return None
        candidates = []
        for _ in range(48):
            selection = random.sample(positions, required)
            if self.try_create_match(selection) is None:
                distance = abs(selection[0][0] - self.cursor_row) + abs(selection[0][1] - self.cursor_col)
                for index in range(1, len(selection)):
                    distance += abs(selection[index][0] - selection[index - 1][0]) + abs(selection[index][1] - selection[index - 1][1])
                candidates.append((distance + random.random() * 1.8, selection))
        if len(candidates) == 0:
            return None
        candidates.sort(key=lambda item: item[0])
        return random.choice([item[1] for item in candidates[:min(8, len(candidates))]])

    def build_plan_from_current_selection(self) -> list[str]:
        """Build the next autoplay plan while respecting any tile that is already selected."""
        if len(self.selected_positions) == 0:
            return []
        selected = set(self.selected_positions)
        matches = [match for match in self.get_available_matches() if selected.issubset(set(match.positions))]
        if len(matches) > 0:
            match = self.choose_auto_match(matches)
            remaining = [position for position in match.positions if position not in selected]
            return self.plan_selection_steps(remaining)
        last_selected = self.selected_positions[-1]
        return self.plan_cursor_route(self.cursor_row, self.cursor_col, last_selected[0], last_selected[1]) + ["W"]

    def build_auto_plan(self) -> list[str]:
        """Build a cursor-and-select action plan, with a small chance of a deliberate mistake."""
        if len(self.selected_positions) > 0:
            return self.build_plan_from_current_selection()
        matches = self.get_available_matches()
        if len(matches) == 0:
            return []
        if random.random() < self.get_auto_mismatch_chance():
            mismatch = self.choose_auto_unmatchable_selection()
            if mismatch is not None:
                return self.plan_selection_steps(mismatch)
        match = self.choose_auto_match(matches)
        return self.plan_selection_steps(match.positions)

    def plan_selection_steps(self, positions: list[CellPos]) -> list[str]:
        """Return a sequence of arrow and select actions for a list of target cells."""
        plan = []
        probe_row = self.cursor_row
        probe_col = self.cursor_col
        for row, col in positions:
            segment = self.plan_cursor_route(probe_row, probe_col, row, col)
            plan.extend(segment)
            plan.append("W")
            probe_row = row
            probe_col = col
        return plan

    def plan_cursor_route(self, start_row: int, start_col: int, target_row: int, target_col: int) -> list[str]:
        """Create a simple Manhattan route between two board cells."""
        queue = deque([(start_row, start_col)])
        parents = {(start_row, start_col): None}
        moves = {}
        while queue:
            row, col = queue.popleft()
            if row == target_row and col == target_col:
                break
            for dr, dc, key in [(-1, 0, "LU"), (1, 0, "LD"), (0, -1, "LL"), (0, 1, "LR")]:
                next_row = row + dr
                next_col = col + dc
                while 0 <= next_row < self.play_rows and 0 <= next_col < self.play_cols and not self.is_play_cell(next_row, next_col):
                    next_row += dr
                    next_col += dc
                if not (0 <= next_row < self.play_rows and 0 <= next_col < self.play_cols):
                    continue
                if (next_row, next_col) in parents:
                    continue
                parents[(next_row, next_col)] = (row, col)
                moves[(next_row, next_col)] = key
                queue.append((next_row, next_col))

        route = []
        cursor = (target_row, target_col)
        while parents[cursor] is not None:
            route.append(moves[cursor])
            cursor = parents[cursor]
        route.reverse()
        return route

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Return a logical autoplay action that respects the every-fourth-frame cadence."""
        action = self.BLANK_ACTION.copy()
        if frame_index == 0 or frame_index % self.moveInterval != 0:
            return action
        if self.win or self.animating:
            return action
        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action
        if len(self.auto_plan) == 0:
            self.auto_plan = self.build_auto_plan()
            if len(self.auto_plan) == 0:
                self.auto_wait_frames = random.randint(1, 3)
                return action
        next_key = self.auto_plan.pop(0)
        action[next_key] = True
        self.auto_wait_frames = random.randint(0, 2)
        return action


def rect_point(rect: pygame.Rect, x_ratio: float, y_ratio: float) -> tuple[int, int]:
    """Return one point inside a rectangle using normalized coordinates."""
    return round(rect.left + rect.width * x_ratio), round(rect.top + rect.height * y_ratio)


def rect_box(rect: pygame.Rect, x_ratio: float, y_ratio: float, width_ratio: float, height_ratio: float) -> pygame.Rect:
    """Return one sub-rectangle inside a rectangle using normalized coordinates."""
    return pygame.Rect(round(rect.left + rect.width * x_ratio), round(rect.top + rect.height * y_ratio), round(rect.width * width_ratio), round(rect.height * height_ratio))


def tile_safe_subtract(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    """Return a darker color without changing the overall palette too much."""
    return max(color[0] - amount, 0), max(color[1] - amount, 0), max(color[2] - amount, 0)


if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(OnetBase)
