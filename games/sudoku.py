from __future__ import annotations

import os, sys, random, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase

CellPos = tuple[int, int]
CellGroup = list[CellPos]


class SudokuRule:
    """Base hook for validating and drawing one Sudoku-style rule."""

    def __init__(self, prompt_text: str = "") -> None:
        """Store prompt text for this rule."""
        self.prompt_text = prompt_text

    def get_prompt_text(self) -> str:
        """Return the rule sentence to include in the training prompt."""
        return self.prompt_text

    def find_related_cells(self, board: list[list[int]], row: int, col: int) -> set[CellPos]:
        """Return all cells involved in a violation caused by the current cell."""
        return set()

    def draw_underlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw visuals that should appear under numbers and cell borders."""
        return None

    def draw_midlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw visuals that should appear above cell fills but below numbers."""
        return None

    def draw_overlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw visuals that should appear above the cells."""
        return None


class UniqueGroupRule(SudokuRule):
    """Rule that forbids repeated non-zero digits inside listed groups."""

    def __init__(self, prompt_text: str, groups: list[CellGroup]) -> None:
        """Store groups and precompute which groups touch each cell."""
        super().__init__(prompt_text)
        self.groups = groups
        self.groups_by_cell: dict[CellPos, list[CellGroup]] = {}
        for group in groups:
            for cell in group:
                self.groups_by_cell.setdefault(cell, []).append(group)

    def find_related_cells(self, board: list[list[int]], row: int, col: int) -> set[CellPos]:
        """Return every group touched by the cell that now contains a duplicate."""
        value = board[row][col]
        if value == 0:
            return set()
        related = set()
        for group in self.groups_by_cell.get((row, col), []):
            duplicate_found = False
            for group_row, group_col in group:
                if (group_row != row or group_col != col) and board[group_row][group_col] == value:
                    duplicate_found = True
                    break
            if duplicate_found:
                related.update(group)
        return related


class PairRelationRule(SudokuRule):
    """Rule for constraints defined on pairs of cells."""

    def __init__(self, prompt_text: str, pairs: list[tuple[CellPos, CellPos]]) -> None:
        """Store cell pairs and index them by cell."""
        super().__init__(prompt_text)
        self.pairs = pairs
        self.pairs_by_cell: dict[CellPos, list[tuple[CellPos, CellPos]]] = {}
        for left, right in pairs:
            self.pairs_by_cell.setdefault(left, []).append((left, right))
            self.pairs_by_cell.setdefault(right, []).append((left, right))

    def relation_holds(self, left_value: int, right_value: int) -> bool:
        """Return whether the pair relation is satisfied."""
        return True

    def find_related_cells(self, board: list[list[int]], row: int, col: int) -> set[CellPos]:
        """Return the conflicting pair when both values are present and break the relation."""
        value = board[row][col]
        if value == 0:
            return set()
        related = set()
        for left, right in self.pairs_by_cell.get((row, col), []):
            left_value = board[left[0]][left[1]]
            right_value = board[right[0]][right[1]]
            if left_value != 0 and right_value != 0 and not self.relation_holds(left_value, right_value):
                related.add(left)
                related.add(right)
        return related


class SumGroupRule(SudokuRule):
    """Rule for cages or areas that must add up to fixed totals."""

    def __init__(self, prompt_text: str, groups: list[CellGroup], targets: list[int], require_unique_digits: bool = False) -> None:
        """Store sum groups, their targets, and optional duplicate prevention."""
        super().__init__(prompt_text)
        self.groups = groups
        self.targets = targets
        self.require_unique_digits = require_unique_digits
        self.groups_by_cell: dict[CellPos, list[tuple[CellGroup, int]]] = {}
        for group, target in zip(groups, targets):
            for cell in group:
                self.groups_by_cell.setdefault(cell, []).append((group, target))

    def find_related_cells(self, board: list[list[int]], row: int, col: int) -> set[CellPos]:
        """Return a whole cage when it exceeds or fails its target."""
        value = board[row][col]
        if value == 0:
            return set()
        related = set()
        for group, target in self.groups_by_cell.get((row, col), []):
            values = [board[group_row][group_col] for group_row, group_col in group if board[group_row][group_col] != 0]
            total = sum(values)
            has_empty = len(values) < len(group)
            if total > target:
                related.update(group)
                continue
            if self.require_unique_digits and len(values) != len(set(values)):
                related.update(group)
                continue
            if not has_empty and total != target:
                related.update(group)
        return related


class ViewCountRule(SudokuRule):
    """Rule for line clues such as skyscraper visibility counts."""

    def __init__(self, prompt_text: str, lines: list[CellGroup], clues: list[int]) -> None:
        """Store lines and side clues and index them by cell."""
        super().__init__(prompt_text)
        self.lines = lines
        self.clues = clues
        self.lines_by_cell: dict[CellPos, list[tuple[CellGroup, int]]] = {}
        for line, clue in zip(lines, clues):
            for cell in line:
                self.lines_by_cell.setdefault(cell, []).append((line, clue))

    def count_visible(self, values: list[int]) -> int:
        """Count how many heights are visible from the start of the line."""
        visible = 0
        tallest = 0
        for value in values:
            if value > tallest:
                tallest = value
                visible += 1
        return visible

    def find_related_cells(self, board: list[list[int]], row: int, col: int) -> set[CellPos]:
        """Return the whole line when a filled line misses its visibility clue."""
        value = board[row][col]
        if value == 0:
            return set()
        related = set()
        for line, clue in self.lines_by_cell.get((row, col), []):
            values = [board[line_row][line_col] for line_row, line_col in line]
            if 0 not in values and self.count_visible(values) != clue:
                related.update(line)
        return related


class SudokuBase(GameBase):
    """Classic Sudoku base with keypad entry and variant-friendly rule composition."""

    name = "Sudoku"
    variantsPath = "sudokus"
    width = 960
    height = 540
    moveInterval = 1
    box_rows = 3
    box_cols = 3
    require_unique_solution = True

    def __init__(self, headless: bool = False) -> None:
        """Set fonts, colors, static rule layout, and build the first puzzle."""
        self.fps = 30
        self.side_panel_width = 290
        self.margin = 24
        self.end_screen_auto_reset = 80
        self.end_screen_event_frame = 28

        self.bg_color = (31, 35, 43)
        self.panel_color = (24, 27, 34)
        self.panel_line = (58, 64, 76)
        self.board_shadow = (16, 19, 24)
        self.board_frame = (86, 92, 106)
        self.given_fill = (228, 221, 208)
        self.edit_fill = (248, 245, 239)
        self.secondary_conflict_fill = (244, 203, 203)
        self.primary_conflict_fill = (213, 93, 93)
        self.keypad_fill = (224, 229, 236)
        self.keypad_selected_fill = (102, 150, 222)
        self.keypad_selected_text = (249, 250, 252)
        self.text_dark = (28, 31, 36)
        self.text_soft = (184, 190, 202)
        self.cursor_board = (247, 206, 82)
        self.cursor_keypad = (95, 198, 235)
        self.edit_text = (45, 86, 148)
        self.given_text = (36, 39, 43)
        self.win_color = (112, 220, 143)

        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        pygame.font.init()
        self.title_font = pygame.font.SysFont("consolas", 28, bold=True)
        self.label_font = pygame.font.SysFont("consolas", 20, bold=True)
        self.cell_font = pygame.font.SysFont("consolas", 28, bold=True)
        self.given_font = pygame.font.SysFont("consolas", 29, bold=True)
        self.preview_font = pygame.font.SysFont("consolas", 58, bold=True)
        self.win_font = pygame.font.SysFont("consolas", 50, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 18, bold=True)

        self.side = self.box_rows * self.box_cols
        self.digits = list(range(1, self.side + 1))
        self.keypad_rows, self.keypad_cols = self.get_keypad_shape()
        self.primary_rules = []
        self.generation_rules = []
        self.variant_rules = []
        self.rules = []
        self.prev_action = self.BLANK_ACTION.copy()
        self.puzzle_index = -1
        self.reset()

    def reset(self) -> None:
        """Generate the next puzzle and clear runtime state."""
        self.puzzle_index += 1
        self.prepare_puzzle_layout()
        self.primary_rules = self.build_primary_rules()
        self.generation_rules = self.build_generation_rules()
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.win = False
        self.mode = "board"
        self.cursor_row = 0
        self.cursor_col = 0
        self.keypad_row, self.keypad_col = self.get_default_keypad_position()
        self.last_modified_cell: CellPos | None = None
        self.primary_conflict_cells: set[CellPos] = set()
        self.secondary_conflict_cells: set[CellPos] = set()
        self.auto_plan: list[str] = []
        self.auto_wait_frames = 1
        self.auto_error_hold = 0
        self.auto_error_cell: CellPos | None = None
        self.solution = self.generate_solution_board()
        self.rules = self.build_puzzle_rules(self.solution)
        self.variant_rules = self.rules[len(self.primary_rules):]
        self.board, self.given_cells = self.generate_puzzle_board(self.solution)
        self.cursor_row = self.side // 2
        self.cursor_col = self.side // 2
        self.prev_action = self.BLANK_ACTION.copy()

    def prepare_puzzle_layout(self) -> None:
        """Build per-puzzle geometry before generating the solved board."""
        return None

    def get_keypad_shape(self) -> tuple[int, int]:
        """Return the keypad grid shape for the current digit set."""
        return self.box_rows, self.box_cols

    def get_default_keypad_position(self) -> tuple[int, int]:
        """Return the keypad cursor's default row and column."""
        default_index = min(self.side - 1, self.side // 2)
        return default_index // self.keypad_cols, default_index % self.keypad_cols

    def build_primary_rules(self) -> list[SudokuRule]:
        """Create the base row, column, and region rules for the current layout."""
        return [
            UniqueGroupRule("Each row must contain each digit at most once.", self.get_row_groups()),
            UniqueGroupRule("Each column must contain each digit at most once.", self.get_column_groups()),
            UniqueGroupRule(self.get_region_prompt_text(), self.get_region_groups()),
        ]

    def build_generation_rules(self) -> list[SudokuRule]:
        """Create the rules that a full solved board must satisfy."""
        rules = self.primary_rules[:]
        rules.extend(self.get_extra_generation_rules())
        return rules

    def build_puzzle_rules(self, solution: list[list[int]]) -> list[SudokuRule]:
        """Create the final active rules for play and uniqueness checking."""
        rules = self.build_generation_rules()
        rules.extend(self.get_extra_puzzle_rules(solution))
        return rules

    def get_row_groups(self) -> list[CellGroup]:
        """Return all row groups for duplicate checking."""
        return [[(row, col) for col in range(self.side)] for row in range(self.side)]

    def get_column_groups(self) -> list[CellGroup]:
        """Return all column groups for duplicate checking."""
        return [[(row, col) for row in range(self.side)] for col in range(self.side)]

    def get_region_groups(self) -> list[CellGroup]:
        """Return classic rectangular box regions."""
        groups = []
        for start_row in range(0, self.side, self.box_rows):
            for start_col in range(0, self.side, self.box_cols):
                groups.append([(row, col) for row in range(start_row, start_row + self.box_rows) for col in range(start_col, start_col + self.box_cols)])
        return groups

    def get_region_prompt_text(self) -> str:
        """Return the prompt sentence for the region rule."""
        return f"Each {self.box_rows} by {self.box_cols} box must contain each digit at most once."

    def get_extra_generation_rules(self) -> list[SudokuRule]:
        """Return extra rules that must hold before clue-specific rules are derived."""
        return []

    def get_extra_puzzle_rules(self, solution: list[list[int]]) -> list[SudokuRule]:
        """Return extra rules derived from the finished solved board."""
        return []

    def choose_target_clues(self) -> int:
        """Pick a clue count that keeps puzzles readable and solvable."""
        if self.side == 9:
            return random.randint(33, 40)
        return max(self.side * 2, self.side * self.side // 2)

    def generate_puzzle_board(self, solution: list[list[int]]) -> tuple[list[list[int]], list[list[bool]]]:
        """Remove clues from one solved board and mark the remaining fixed cells."""
        board = [row[:] for row in solution]
        target_clues = self.choose_target_clues()
        cells = [(row, col) for row in range(self.side) for col in range(self.side)]
        random.shuffle(cells)
        remaining_clues = self.side * self.side

        for row, col in cells:
            if remaining_clues <= target_clues:
                break
            saved = board[row][col]
            board[row][col] = 0
            if self.require_unique_solution and self.count_solutions([line[:] for line in board], 2) != 1:
                board[row][col] = saved
            else:
                remaining_clues -= 1

        given_cells = [[board[row][col] != 0 for col in range(self.side)] for row in range(self.side)]
        return board, given_cells

    def generate_solution_board(self) -> list[list[int]]:
        """Build a solved board that satisfies the generation rules."""
        board = self.generate_pattern_solution_board()
        if self.board_satisfies_rules(board, self.generation_rules):
            return board
        return self.generate_solution_board_by_search(self.generation_rules)

    def generate_pattern_solution_board(self) -> list[list[int]]:
        """Build a solved classic board by shuffling the standard box pattern."""
        row_bands = list(range(self.box_cols))
        col_stacks = list(range(self.box_rows))
        random.shuffle(row_bands)
        random.shuffle(col_stacks)

        rows = []
        for band in row_bands:
            local_rows = list(range(self.box_rows))
            random.shuffle(local_rows)
            for local_row in local_rows:
                rows.append(band * self.box_rows + local_row)

        cols = []
        for stack in col_stacks:
            local_cols = list(range(self.box_cols))
            random.shuffle(local_cols)
            for local_col in local_cols:
                cols.append(stack * self.box_cols + local_col)

        digits = self.digits[:]
        random.shuffle(digits)
        return [[digits[(self.box_cols * (row % self.box_rows) + row // self.box_rows + col) % self.side] for col in cols] for row in rows]

    def generate_solution_board_by_search(self, rules: list[SudokuRule]) -> list[list[int]]:
        """Build a solved board with recursive search under the given rules."""
        board = [[0 for _ in range(self.side)] for _ in range(self.side)]
        self.solve_board(board, rules)
        return board

    def solve_board(self, board: list[list[int]], rules: list[SudokuRule]) -> bool:
        """Fill a board in place and return whether one solution was found."""
        position, candidates = self.find_best_empty_cell(board, rules)
        if position is None:
            return True
        if len(candidates) == 0:
            return False

        row, col = position
        for value in candidates:
            board[row][col] = value
            if self.solve_board(board, rules):
                return True
            board[row][col] = 0
        return False

    def board_satisfies_rules(self, board: list[list[int]], rules: list[SudokuRule]) -> bool:
        """Return whether every filled cell currently obeys the given rules."""
        for row in range(self.side):
            for col in range(self.side):
                value = board[row][col]
                if value == 0:
                    continue
                if len(self.get_rule_conflicts(board, row, col, value, rules)) > 0:
                    return False
        return True

    def count_solutions(self, board: list[list[int]], limit: int, rules: list[SudokuRule] | None = None) -> int:
        """Count solutions up to a small limit using recursive search."""
        position, candidates = self.find_best_empty_cell(board, rules)
        if position is None:
            return 1
        if len(candidates) == 0:
            return 0

        total = 0
        row, col = position
        for value in candidates:
            board[row][col] = value
            total += self.count_solutions(board, limit - total, rules)
            board[row][col] = 0
            if total >= limit:
                return total
        return total

    def find_best_empty_cell(self, board: list[list[int]], rules: list[SudokuRule] | None = None) -> tuple[CellPos | None, list[int]]:
        """Pick the next empty cell with the fewest candidates."""
        best_position = None
        best_candidates: list[int] = []
        for row in range(self.side):
            for col in range(self.side):
                if board[row][col] != 0:
                    continue
                candidates = self.get_candidates(board, row, col, rules)
                if best_position is None or len(candidates) < len(best_candidates):
                    best_position = (row, col)
                    best_candidates = candidates
                    if len(best_candidates) <= 1:
                        return best_position, best_candidates
        return best_position, best_candidates

    def get_candidates(self, board: list[list[int]], row: int, col: int, rules: list[SudokuRule] | None = None) -> list[int]:
        """Return digits that do not break any active rule at this cell."""
        candidates = []
        for value in self.digits:
            if self.is_value_allowed(board, row, col, value, rules):
                candidates.append(value)
        random.shuffle(candidates)
        return candidates

    def is_value_allowed(self, board: list[list[int]], row: int, col: int, value: int, rules: list[SudokuRule] | None = None) -> bool:
        """Return whether placing the value keeps the board locally valid."""
        return len(self.get_rule_conflicts(board, row, col, value, rules)) == 0

    def get_rule_conflicts(self, board: list[list[int]], row: int, col: int, value: int, rules: list[SudokuRule] | None = None) -> set[CellPos]:
        """Return all cells touched by rules violated by this tentative value."""
        active_rules = self.rules if rules is None else rules
        saved = board[row][col]
        board[row][col] = value
        related = set()
        for rule in active_rules:
            related.update(rule.find_related_cells(board, row, col))
        board[row][col] = saved
        return related

    def refresh_conflicts_for_cell(self, row: int, col: int) -> None:
        """Update the red highlight sets based on the last modified cell."""
        self.last_modified_cell = (row, col)
        self.primary_conflict_cells = set()
        self.secondary_conflict_cells = set()
        value = self.board[row][col]
        if value == 0:
            return
        related = self.get_rule_conflicts(self.board, row, col, value)
        if len(related) > 0:
            self.primary_conflict_cells.add((row, col))
            self.secondary_conflict_cells = related - {(row, col)}

    def clear_conflicts(self) -> None:
        """Clear any active error highlighting."""
        self.last_modified_cell = None
        self.primary_conflict_cells = set()
        self.secondary_conflict_cells = set()

    def enter_value(self, value: int) -> None:
        """Write one value into the selected editable cell and leave keypad mode."""
        if self.given_cells[self.cursor_row][self.cursor_col]:
            self.mode = "board"
            return
        self.board[self.cursor_row][self.cursor_col] = value
        self.mode = "board"
        self.refresh_conflicts_for_cell(self.cursor_row, self.cursor_col)
        self.check_win()

    def delete_value(self) -> None:
        """Delete the value at the selected editable cell."""
        if self.given_cells[self.cursor_row][self.cursor_col]:
            return
        self.board[self.cursor_row][self.cursor_col] = 0
        self.refresh_conflicts_for_cell(self.cursor_row, self.cursor_col)

    def check_win(self) -> None:
        """Mark the puzzle solved once every cell is filled and valid."""
        for row in range(self.side):
            for col in range(self.side):
                if self.board[row][col] == 0:
                    return
                if len(self.get_rule_conflicts(self.board, row, col, self.board[row][col])) > 0:
                    return
        self.win = True
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.mode = "board"

    def get_pressed_action(self, action: ActionState) -> ActionState:
        """Convert held actions into edge-triggered button presses."""
        pressed = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action.get(key, False):
                pressed[key] = True
        self.prev_action = action.copy()
        return pressed

    def move_board_cursor(self, row_step: int, col_step: int) -> None:
        """Move the board cursor by one cell while staying inside the grid."""
        self.cursor_row = max(0, min(self.side - 1, self.cursor_row + row_step))
        self.cursor_col = max(0, min(self.side - 1, self.cursor_col + col_step))

    def move_keypad_cursor(self, row_step: int, col_step: int) -> None:
        """Move the keypad cursor by one slot while staying inside the keypad."""
        self.keypad_row = max(0, min(self.keypad_rows - 1, self.keypad_row + row_step))
        self.keypad_col = max(0, min(self.keypad_cols - 1, self.keypad_col + col_step))

    def get_keypad_value(self, row: int, col: int) -> int:
        """Return the digit represented by one keypad slot, or zero if unused."""
        value = row * self.keypad_cols + col + 1
        if value > self.side:
            return 0
        return value

    def open_keypad(self) -> None:
        """Enter keypad mode and reset the keypad cursor to its default slot."""
        self.mode = "keypad"
        self.keypad_row, self.keypad_col = self.get_default_keypad_position()

    def handle_board_input(self, pressed: ActionState) -> None:
        """Apply controls while the cursor is moving on the puzzle board."""
        if pressed["LU"]:
            self.move_board_cursor(-1, 0)
        elif pressed["LD"]:
            self.move_board_cursor(1, 0)
        elif pressed["LL"]:
            self.move_board_cursor(0, -1)
        elif pressed["LR"]:
            self.move_board_cursor(0, 1)
        elif pressed["W"] and not self.given_cells[self.cursor_row][self.cursor_col]:
            self.open_keypad()
        elif pressed["D"]:
            self.delete_value()

    def handle_keypad_input(self, pressed: ActionState) -> None:
        """Apply controls while the number keypad is open."""
        if pressed["LU"]:
            self.move_keypad_cursor(-1, 0)
        elif pressed["LD"]:
            self.move_keypad_cursor(1, 0)
        elif pressed["LL"]:
            self.move_keypad_cursor(0, -1)
        elif pressed["LR"]:
            self.move_keypad_cursor(0, 1)
        elif pressed["W"]:
            self.mode = "board"
        elif pressed["D"]:
            self.delete_value()
        elif pressed["A"]:
            value = self.get_keypad_value(self.keypad_row, self.keypad_col)
            if value != 0:
                self.enter_value(value)

    def update(self, action: ActionState) -> bool:
        """Advance one frame, process input, and manage win-screen timing."""
        self.frame_index += 1
        pressed = self.get_pressed_action(action)

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.win:
            self.end_screen_frames += 1
            if self.end_screen_frames == self.end_screen_event_frame:
                self.end_event_pending = True
            if self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        if self.mode == "keypad":
            self.handle_keypad_input(pressed)
        else:
            self.handle_board_input(pressed)

        return False

    def get_layout(self) -> tuple[int, int, int, pygame.Rect]:
        """Return cell size, board origin, and side panel rectangle."""
        panel_rect = pygame.Rect(self.width - self.side_panel_width - self.margin, self.margin, self.side_panel_width, self.height - self.margin * 2)
        board_space_width = self.width - panel_rect.width - self.margin * 3
        board_space_height = self.height - self.margin * 2
        cell_size = min(board_space_width // self.side, board_space_height // self.side)
        board_width = cell_size * self.side
        board_height = cell_size * self.side
        board_left = self.margin + (board_space_width - board_width) // 2
        board_top = (self.height - board_height) // 2
        return cell_size, board_left, board_top, panel_rect

    def get_cell_rects(self, cell_size: int, board_left: int, board_top: int) -> dict[CellPos, pygame.Rect]:
        """Build a rectangle lookup for every board cell."""
        return {(row, col): pygame.Rect(board_left + col * cell_size, board_top + row * cell_size, cell_size, cell_size) for row in range(self.side) for col in range(self.side)}

    def format_value(self, value: int) -> str:
        """Return the label used to draw one digit."""
        if value <= 9:
            return str(value)
        return chr(ord("A") + value - 10)

    def draw_background(self) -> None:
        """Paint the scene background and board shadow."""
        self.screen.fill(self.bg_color)
        cell_size, board_left, board_top, _ = self.get_layout()
        board_rect = pygame.Rect(board_left - 8, board_top - 8, cell_size * self.side + 16, cell_size * self.side + 16)
        pygame.draw.rect(self.screen, self.board_shadow, board_rect, border_radius=14)
        pygame.draw.rect(self.screen, self.board_frame, board_rect, 3, border_radius=14)

    def draw_panel(self, panel_rect: pygame.Rect) -> None:
        """Draw the side panel with title, puzzle count, mode, and cell preview."""
        pygame.draw.rect(self.screen, self.panel_color, panel_rect, border_radius=18)
        pygame.draw.rect(self.screen, self.panel_line, panel_rect, 2, border_radius=18)
        self.screen.blit(self.title_font.render(self.name, True, (240, 242, 246)), (panel_rect.x + 18, panel_rect.y + 16))
        self.screen.blit(self.small_font.render(f"Puzzle {self.puzzle_index}", True, self.text_soft), (panel_rect.x + 20, panel_rect.y + 56))

        mode_text = "Keypad Mode" if self.mode == "keypad" else "Board Mode"
        mode_color = self.cursor_keypad if self.mode == "keypad" else self.cursor_board
        mode_rect = pygame.Rect(panel_rect.x + 18, panel_rect.y + 88, panel_rect.width - 36, 34)
        pygame.draw.rect(self.screen, (40, 45, 56), mode_rect, border_radius=10)
        pygame.draw.rect(self.screen, mode_color, mode_rect, 2, border_radius=10)
        self.screen.blit(self.label_font.render(mode_text, True, mode_color), (mode_rect.x + 12, mode_rect.y + 6))

        preview_rect = pygame.Rect(panel_rect.x + 18, panel_rect.y + 148, panel_rect.width - 36, 122)
        preview_fill = (47, 53, 65)
        if (self.cursor_row, self.cursor_col) in self.primary_conflict_cells:
            preview_fill = self.primary_conflict_fill
        elif (self.cursor_row, self.cursor_col) in self.secondary_conflict_cells:
            preview_fill = self.secondary_conflict_fill
        elif self.given_cells[self.cursor_row][self.cursor_col]:
            preview_fill = (95, 88, 78)
        pygame.draw.rect(self.screen, preview_fill, preview_rect, border_radius=14)
        pygame.draw.rect(self.screen, self.panel_line, preview_rect, 2, border_radius=14)
        self.screen.blit(self.small_font.render(f"Row {self.cursor_row + 1}  Col {self.cursor_col + 1}", True, (232, 235, 241)), (preview_rect.x + 14, preview_rect.y + 12))
        value = self.board[self.cursor_row][self.cursor_col]
        preview_label = "." if value == 0 else self.format_value(value)
        preview_color = self.text_dark if preview_fill not in [self.primary_conflict_fill, self.secondary_conflict_fill] else (251, 252, 254)
        if self.given_cells[self.cursor_row][self.cursor_col]:
            preview_color = (244, 242, 235)
        preview_surface = self.preview_font.render(preview_label, True, preview_color)
        self.screen.blit(preview_surface, preview_surface.get_rect(center=(preview_rect.centerx, preview_rect.centery + 18)))

    def draw_cell_fills(self, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw every board cell background fill."""
        for row in range(self.side):
            for col in range(self.side):
                rect = cell_rects[(row, col)]
                fill = self.given_fill if self.given_cells[row][col] else self.edit_fill
                if (row, col) in self.secondary_conflict_cells:
                    fill = self.secondary_conflict_fill
                if (row, col) in self.primary_conflict_cells:
                    fill = self.primary_conflict_fill
                pygame.draw.rect(self.screen, fill, rect)

    def draw_cell_values(self, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw every visible board value above the cell fills."""
        for row in range(self.side):
            for col in range(self.side):
                rect = cell_rects[(row, col)]
                value = self.board[row][col]
                if value != 0:
                    text_color = self.given_text if self.given_cells[row][col] else self.edit_text
                    font = self.given_font if self.given_cells[row][col] else self.cell_font
                    if (row, col) in self.primary_conflict_cells:
                        text_color = (252, 252, 252)
                    text = font.render(self.format_value(value), True, text_color)
                    self.screen.blit(text, text.get_rect(center=rect.center))

    def draw_cells(self, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw board cell fills, middle rule art, and numbers."""
        self.draw_cell_fills(cell_rects)
        self.draw_rule_midlays(cell_rects)
        self.draw_cell_values(cell_rects)

    def draw_grid_lines(self, cell_size: int, board_left: int, board_top: int) -> None:
        """Draw regular grid lines and thicker box boundaries."""
        board_width = cell_size * self.side
        board_height = cell_size * self.side
        for index in range(self.side + 1):
            line_width = 1
            line_color = (129, 134, 146)
            if index % self.box_rows == 0:
                line_width = 3
                line_color = (63, 68, 79)
            y = board_top + index * cell_size
            pygame.draw.line(self.screen, line_color, (board_left, y), (board_left + board_width, y), line_width)

        for index in range(self.side + 1):
            line_width = 1
            line_color = (129, 134, 146)
            if index % self.box_cols == 0:
                line_width = 3
                line_color = (63, 68, 79)
            x = board_left + index * cell_size
            pygame.draw.line(self.screen, line_color, (x, board_top), (x, board_top + board_height), line_width)

    def draw_cursors(self, cell_rects: dict[CellPos, pygame.Rect], panel_rect: pygame.Rect) -> None:
        """Draw the active board cursor and keypad selection."""
        cursor_rect = cell_rects[(self.cursor_row, self.cursor_col)]
        border_color = self.cursor_keypad if self.mode == "keypad" else self.cursor_board
        pygame.draw.rect(self.screen, border_color, cursor_rect, 4)

        if self.mode != "keypad":
            return

        keypad_rects = self.get_keypad_rects(panel_rect)
        selected_value = self.get_keypad_value(self.keypad_row, self.keypad_col)
        for row in range(self.keypad_rows):
            for col in range(self.keypad_cols):
                rect = keypad_rects[(row, col)]
                value = self.get_keypad_value(row, col)
                fill = self.keypad_fill if value != 0 else (84, 90, 102)
                text_color = self.text_dark
                if row == self.keypad_row and col == self.keypad_col:
                    fill = self.keypad_selected_fill
                    text_color = self.keypad_selected_text
                pygame.draw.rect(self.screen, fill, rect, border_radius=10)
                pygame.draw.rect(self.screen, self.panel_line, rect, 2, border_radius=10)
                if value != 0:
                    label = self.label_font.render(self.format_value(value), True, text_color)
                    self.screen.blit(label, label.get_rect(center=rect.center))

    def get_keypad_rects(self, panel_rect: pygame.Rect) -> dict[CellPos, pygame.Rect]:
        """Return rectangles for keypad buttons inside the side panel."""
        keypad_top = panel_rect.y + 292
        gap = 10
        size = min((panel_rect.width - 36 - gap * (self.keypad_cols - 1)) // self.keypad_cols, 58)
        total_width = size * self.keypad_cols + gap * (self.keypad_cols - 1)
        left = panel_rect.x + (panel_rect.width - total_width) // 2
        return {(row, col): pygame.Rect(left + col * (size + gap), keypad_top + row * (size + gap), size, size) for row in range(self.keypad_rows) for col in range(self.keypad_cols)}

    def draw_rule_underlays(self, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Allow rules to draw background overlays for future variants."""
        for rule in self.rules:
            rule.draw_underlay(self, cell_rects)

    def draw_rule_midlays(self, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Allow rules to draw between cell fills and numbers."""
        for rule in self.rules:
            rule.draw_midlay(self, cell_rects)

    def draw_rule_overlays(self, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Allow rules to draw foreground overlays for future variants."""
        for rule in self.rules:
            rule.draw_overlay(self, cell_rects)

    def draw_win_overlay(self) -> None:
        """Draw a short solved overlay before the next puzzle appears."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((4, 9, 14, 148))
        self.screen.blit(overlay, (0, 0))
        text = self.win_font.render("Solved", True, self.win_color)
        self.screen.blit(text, text.get_rect(center=(self.width // 2, self.height // 2 - 12)))
        next_text = self.label_font.render("Next puzzle loading...", True, (228, 233, 239))
        self.screen.blit(next_text, next_text.get_rect(center=(self.width // 2, self.height // 2 + 36)))

    def draw(self) -> None:
        """Render the board, side panel, keypad, and win overlay."""
        self.draw_background()
        cell_size, board_left, board_top, panel_rect = self.get_layout()
        cell_rects = self.get_cell_rects(cell_size, board_left, board_top)
        self.draw_panel(panel_rect)
        self.draw_rule_underlays(cell_rects)
        self.draw_cells(cell_rects)
        self.draw_rule_overlays(cell_rects)
        self.draw_grid_lines(cell_size, board_left, board_top)
        self.draw_cursors(cell_rects, panel_rect)
        if self.win:
            self.draw_win_overlay()

    def getPrompt(self) -> str:
        """Return the training prompt with controls and active rule text."""
        rule_lines = []
        for rule in self.rules:
            text = rule.get_prompt_text()
            if text and text not in rule_lines:
                rule_lines.append(text)
        return " ".join([
            f"This is {self.name}.",
            "Use Arrow keys to move the board cursor.",
            "Press W to open the number keypad.",
            "In keypad mode, use Arrow keys to choose a number and press A to place it.",
            "Press W again to leave keypad mode without placing a number.",
            "Press D to delete the current editable cell in either mode.",
            "A wrong entry turns the edited cell red and the related cells light red.",
            "Fill every empty cell while obeying these rules:",
            *rule_lines,
        ])

    def get_empty_cells(self) -> list[CellPos]:
        """Return all currently empty cells."""
        return [(row, col) for row in range(self.side) for col in range(self.side) if self.board[row][col] == 0]

    def get_wrong_cells(self) -> list[CellPos]:
        """Return editable cells that are wrong or currently violating a rule."""
        wrong = []
        for row in range(self.side):
            for col in range(self.side):
                if self.given_cells[row][col] or self.board[row][col] == 0:
                    continue
                if self.board[row][col] != self.solution[row][col]:
                    wrong.append((row, col))
                    continue
                if len(self.get_rule_conflicts(self.board, row, col, self.board[row][col])) > 0:
                    wrong.append((row, col))
        return wrong

    def choose_target_cell(self, candidates: list[CellPos]) -> CellPos:
        """Pick a nearby target cell with a little randomness."""
        ranked = []
        for row, col in candidates:
            distance = abs(row - self.cursor_row) + abs(col - self.cursor_col)
            ranked.append((distance + random.random() * 0.5, row, col))
        ranked.sort()
        _, row, col = ranked[0]
        return row, col

    def plan_cursor_path(self, target_row: int, target_col: int) -> list[str]:
        """Create Arrow-key moves from the current cursor position to one cell."""
        plan = []
        if self.mode == "keypad":
            plan.append("W")
        row = self.cursor_row
        col = self.cursor_col
        while row < target_row:
            plan.append("LD")
            row += 1
        while row > target_row:
            plan.append("LU")
            row -= 1
        while col < target_col:
            plan.append("LR")
            col += 1
        while col > target_col:
            plan.append("LL")
            col -= 1
        return plan

    def plan_keypad_entry(self, target_row: int, target_col: int, value: int) -> list[str]:
        """Create a full action plan to place one value through the keypad."""
        plan = self.plan_cursor_path(target_row, target_col)
        plan.append("W")
        keypad_row, keypad_col = self.get_default_keypad_position()
        desired_index = value - 1
        desired_row = desired_index // self.keypad_cols
        desired_col = desired_index % self.keypad_cols
        while keypad_row < desired_row:
            plan.append("LD")
            keypad_row += 1
        while keypad_row > desired_row:
            plan.append("LU")
            keypad_row -= 1
        while keypad_col < desired_col:
            plan.append("LR")
            keypad_col += 1
        while keypad_col > desired_col:
            plan.append("LL")
            keypad_col -= 1
        plan.append("A")
        return plan

    def plan_delete(self, target_row: int, target_col: int) -> list[str]:
        """Create a full action plan to delete one cell."""
        plan = self.plan_cursor_path(target_row, target_col)
        plan.append("D")
        return plan

    def choose_conflicting_value(self, target_row: int, target_col: int) -> int:
        """Pick a wrong value that visibly violates at least one rule."""
        variant_only_choices = []
        mixed_choices = []
        primary_only_choices = []
        for value in self.digits:
            if value == self.solution[target_row][target_col]:
                continue
            primary_conflicts = self.get_rule_conflicts(self.board, target_row, target_col, value, self.primary_rules)
            variant_conflicts = self.get_rule_conflicts(self.board, target_row, target_col, value, self.variant_rules)
            if len(primary_conflicts) == 0 and len(variant_conflicts) > 0:
                variant_only_choices.append(value)
            elif len(primary_conflicts) > 0 and len(variant_conflicts) > 0:
                mixed_choices.append(value)
            elif len(primary_conflicts) > 0:
                primary_only_choices.append(value)
        if len(variant_only_choices) > 0:
            return random.choice(variant_only_choices)
        if len(mixed_choices) > 0:
            return random.choice(mixed_choices)
        if len(primary_only_choices) == 0:
            return 0
        return random.choice(primary_only_choices)

    def build_auto_plan(self) -> list[str]:
        """Build a noisy but eventually successful action plan."""
        wrong_cells = self.get_wrong_cells()
        if len(wrong_cells) > 0:
            if self.auto_error_hold > 0:
                self.auto_error_hold -= 1
                return []
            target_row, target_col = self.choose_target_cell(wrong_cells)
            if random.random() < 0.3:
                return self.plan_delete(target_row, target_col)
            return self.plan_keypad_entry(target_row, target_col, self.solution[target_row][target_col])

        empty_cells = self.get_empty_cells()
        if len(empty_cells) == 0:
            return []

        target_row, target_col = self.choose_target_cell(empty_cells)
        if random.random() < 0.16:
            mistake_value = self.choose_conflicting_value(target_row, target_col)
            if mistake_value != 0:
                self.auto_error_cell = (target_row, target_col)
                self.auto_error_hold = random.randint(8, 16)
                return self.plan_keypad_entry(target_row, target_col, mistake_value)
        self.auto_error_cell = None
        return self.plan_keypad_entry(target_row, target_col, self.solution[target_row][target_col])

    def getAutoAction(self) -> ActionState:
        """Return an imperfect autoplay action that sometimes causes visible mistakes."""
        action = self.BLANK_ACTION.copy()

        if self.frame_index % self.moveInterval != 0:
            return action
        if self.win:
            return action
        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action
        if len(self.auto_plan) == 0:
            self.auto_plan = self.build_auto_plan()
            if len(self.auto_plan) == 0:
                self.auto_wait_frames = random.randint(1, 3)
                return action

        next_move = self.auto_plan.pop(0)
        action[next_move] = True
        if next_move in ["A", "W", "D"]:
            self.auto_wait_frames = random.randint(1, 2)
        else:
            self.auto_wait_frames = random.randint(0, 1)
        return action


if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay
    run_autoplay(SudokuBase)
