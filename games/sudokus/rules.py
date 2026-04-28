from __future__ import annotations

import os, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sudoku import CellPos, CellGroup, SudokuBase, SudokuRule, UniqueGroupRule, PairRelationRule, SumGroupRule, ViewCountRule


def orthogonal_pairs(side: int) -> list[tuple[CellPos, CellPos]]:
    """Return every orthogonally adjacent pair exactly once."""
    pairs = []
    for row in range(side):
        for col in range(side):
            if row + 1 < side:
                pairs.append(((row, col), (row + 1, col)))
            if col + 1 < side:
                pairs.append(((row, col), (row, col + 1)))
    return pairs


def knight_pairs(side: int) -> list[tuple[CellPos, CellPos]]:
    """Return every knight-move pair exactly once."""
    pairs = []
    for row in range(side):
        for col in range(side):
            for row_step, col_step in [(1, 2), (2, 1), (2, -1), (1, -2)]:
                next_row = row + row_step
                next_col = col + col_step
                if 0 <= next_row < side and 0 <= next_col < side:
                    pairs.append(((row, col), (next_row, next_col)))
    return pairs


def region_groups_from_map(region_map: list[list[int]]) -> list[CellGroup]:
    """Convert a 2D region-id map into ordered cell groups."""
    groups: dict[int, CellGroup] = {}
    for row, region_row in enumerate(region_map):
        for col, region_id in enumerate(region_row):
            groups.setdefault(region_id, []).append((row, col))
    return [groups[region_id] for region_id in sorted(groups)]


class TintedGroupRule(UniqueGroupRule):
    """Unique-group rule that also tints its cells for visibility."""

    def __init__(self, prompt_text: str, groups: list[CellGroup], tint_color: tuple[int, int, int, int]) -> None:
        """Store the rule groups and overlay tint color."""
        super().__init__(prompt_text, groups)
        self.tint_color = tint_color

    def draw_overlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw a translucent tint on every cell touched by the rule."""
        overlay = pygame.Surface((game.width, game.height), pygame.SRCALPHA)
        cells = set()
        for group in self.groups:
            cells.update(group)
        for cell in cells:
            pygame.draw.rect(overlay, self.tint_color, cell_rects[cell])
        game.screen.blit(overlay, (0, 0))


class DifferentPairRule(PairRelationRule):
    """Pair rule that forbids equal digits on marked pairs."""

    def relation_holds(self, left_value: int, right_value: int) -> bool:
        """Return whether the two digits are different."""
        return left_value != right_value


class ConsecutiveBarsRule(PairRelationRule):
    """Pair rule that marks orthogonal neighbors that must be consecutive."""

    def __init__(self, prompt_text: str, pairs: list[tuple[CellPos, CellPos]]) -> None:
        """Store consecutive pairs and their draw colors."""
        super().__init__(prompt_text, pairs)
        self.line_color = (248, 248, 248, 220)
        self.outline_color = (72, 78, 88, 180)

    def relation_holds(self, left_value: int, right_value: int) -> bool:
        """Return whether the two digits differ by exactly one."""
        return abs(left_value - right_value) == 1

    def draw_overlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw a white bar between every marked consecutive pair."""
        overlay = pygame.Surface((game.width, game.height), pygame.SRCALPHA)
        for left, right in self.pairs:
            left_rect = cell_rects[left]
            right_rect = cell_rects[right]
            if left[0] == right[0]:
                center_y = left_rect.centery
                start = (left_rect.right - 4, center_y-3)
                end = (right_rect.left + 4, center_y-3)
                pygame.draw.line(overlay, self.outline_color, start, end, 3)
                start = (left_rect.right - 4, center_y+3)
                end = (right_rect.left + 4, center_y+3)
                pygame.draw.line(overlay, self.outline_color, start, end, 3)
            else:
                center_x = left_rect.centerx
                start = (center_x-3, left_rect.bottom - 4)
                end = (center_x-3, right_rect.top + 4)
                pygame.draw.line(overlay, self.outline_color, start, end, 3)
                start = (center_x+3, left_rect.bottom - 4)
                end = (center_x+3, right_rect.top + 4)
                pygame.draw.line(overlay, self.outline_color, start, end, 3)
        game.screen.blit(overlay, (0, 0))


class WhispersLineRule(PairRelationRule):
    """Pair rule for a German-whispers line."""

    def __init__(self, prompt_text: str, line_cells: list[CellPos]) -> None:
        """Store one line path and create its adjacent-cell pairs."""
        pairs = [(line_cells[index], line_cells[index + 1]) for index in range(len(line_cells) - 1)]
        super().__init__(prompt_text, pairs)
        self.line_cells = line_cells
        self.line_color = (96, 212, 116, 190)
        self.node_color = (62, 172, 88, 220)

    def relation_holds(self, left_value: int, right_value: int) -> bool:
        """Return whether the two digits differ by at least five."""
        return abs(left_value - right_value) >= 5

    def draw_midlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw the green whispers line between cell fills and numbers."""
        overlay = pygame.Surface((game.width, game.height), pygame.SRCALPHA)
        points = [cell_rects[cell].center for cell in self.line_cells]
        if len(points) >= 2:
            pygame.draw.lines(overlay, self.line_color, False, points, 10)
        for point in points:
            pygame.draw.circle(overlay, self.node_color, point, 7)
        game.screen.blit(overlay, (0, 0))


class InequalitySignsRule(SudokuRule):
    """Directed pair rule drawn with > < ^ and v symbols."""

    def __init__(self, prompt_text: str, greater_pairs: list[tuple[CellPos, CellPos]]) -> None:
        """Store every greater-than relation and index it by cell."""
        super().__init__(prompt_text)
        self.greater_pairs = greater_pairs
        self.pairs_by_cell: dict[CellPos, list[tuple[CellPos, CellPos]]] = {}
        for greater_cell, smaller_cell in greater_pairs:
            self.pairs_by_cell.setdefault(greater_cell, []).append((greater_cell, smaller_cell))
            self.pairs_by_cell.setdefault(smaller_cell, []).append((greater_cell, smaller_cell))

    def find_related_cells(self, board: list[list[int]], row: int, col: int) -> set[CellPos]:
        """Return the two cells for any violated inequality touching the current cell."""
        value = board[row][col]
        if value == 0:
            return set()
        related = set()
        for greater_cell, smaller_cell in self.pairs_by_cell.get((row, col), []):
            greater_value = board[greater_cell[0]][greater_cell[1]]
            smaller_value = board[smaller_cell[0]][smaller_cell[1]]
            if greater_value != 0 and smaller_value != 0 and greater_value <= smaller_value:
                related.add(greater_cell)
                related.add(smaller_cell)
        return related

    def draw_overlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw one inequality symbol between each directed pair."""
        for greater_cell, smaller_cell in self.greater_pairs:
            greater_rect = cell_rects[greater_cell]
            smaller_rect = cell_rects[smaller_cell]
            if greater_cell[0] == smaller_cell[0]:
                symbol = ">" if greater_cell[1] < smaller_cell[1] else "<"
                center = ((greater_rect.centerx + smaller_rect.centerx) // 2, greater_rect.centery)
            else:
                symbol = "v" if greater_cell[0] < smaller_cell[0] else "^"
                center = (greater_rect.centerx, (greater_rect.centery + smaller_rect.centery) // 2)
            text = game.label_font.render(symbol, True, (70, 88, 110))
            game.screen.blit(text, text.get_rect(center=center))


class SkyscraperClueRule(ViewCountRule):
    """View-count rule drawn as clues around the outside of the grid."""

    def __init__(self, prompt_text: str, entries: list[tuple[CellGroup, int, str]]) -> None:
        """Store clue entries in viewing order together with their edge side."""
        lines = [line for line, clue, side in entries]
        clues = [clue for line, clue, side in entries]
        super().__init__(prompt_text, lines, clues)
        self.entries = entries

    def draw_overlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw every outer skyscraper clue just beyond the board edge."""
        for line, clue, side in self.entries:
            anchor_cell = line[0]
            rect = cell_rects[anchor_cell]
            if side == "top":
                center = (rect.centerx, rect.top - 12)
            elif side == "bottom":
                center = (rect.centerx, rect.bottom + 12)
            elif side == "left":
                center = (rect.left - 12, rect.centery)
            else:
                center = (rect.right + 12, rect.centery)
            text = game.small_font.render(str(clue), True, (90, 160, 228))
            game.screen.blit(text, text.get_rect(center=center))


class CageSumRule(SumGroupRule):
    """Sum-cage rule used by killer Sudoku."""

    def __init__(self, prompt_text: str, groups: list[CellGroup], targets: list[int]) -> None:
        """Store cages, their sums, and cage drawing colors."""
        super().__init__(prompt_text, groups, targets, require_unique_digits=True)
        self.line_color = (38, 41, 47)
        self.text_color = (48, 52, 60)

    def draw_overlay(self, game: SudokuBase, cell_rects: dict[CellPos, pygame.Rect]) -> None:
        """Draw cage outlines and small target totals."""
        overlay = pygame.Surface((game.width, game.height), pygame.SRCALPHA)
        for group, target in zip(self.groups, self.targets):
            members = set(group)
            for row, col in group:
                rect = cell_rects[(row, col)]
                if (row - 1, col) not in members:
                    pygame.draw.line(overlay, self.line_color, (rect.left + 4, rect.top + 4), (rect.right - 4, rect.top + 4), 2)
                if (row + 1, col) not in members:
                    pygame.draw.line(overlay, self.line_color, (rect.left + 4, rect.bottom - 4), (rect.right - 4, rect.bottom - 4), 2)
                if (row, col - 1) not in members:
                    pygame.draw.line(overlay, self.line_color, (rect.left + 4, rect.top + 4), (rect.left + 4, rect.bottom - 4), 2)
                if (row, col + 1) not in members:
                    pygame.draw.line(overlay, self.line_color, (rect.right - 4, rect.top + 4), (rect.right - 4, rect.bottom - 4), 2)
            label_cell = min(group)
            label_rect = cell_rects[label_cell]
            label = game.small_font.render(str(target), True, self.text_color)
            overlay.blit(label, (label_rect.x + 6, label_rect.y + 2))
        game.screen.blit(overlay, (0, 0))
