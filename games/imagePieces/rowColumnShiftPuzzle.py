from __future__ import annotations

import os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.imagePieceBase import ActionState, ImagePieceGameBase


class RowColumnShiftPuzzle(ImagePieceGameBase):
    """Image puzzle where selected rows and columns loop around when shifted."""

    name = "Row Column Shift Puzzle"
    board_width = 456
    board_height = 342
    moveInterval = 4

    def __init__(self, headless: bool = False) -> None:
        """Create visual settings and the first loop-shift puzzle."""
        self.fps = 30
        self.anim_total_frames = 10
        self.end_event_frame = 28
        self.end_screen_auto_reset = 120
        self.background_color = (19, 25, 34)
        self.board_fill = (12, 16, 22)
        self.board_line = (184, 203, 226)
        self.cursor_color = (255, 214, 82)
        self.mode_color = (113, 223, 174)
        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        self.win_font = pygame.font.SysFont("trebuchetms", 58, bold=True)
        self.reset()

    def reset(self) -> None:
        """Build a new scrambled row-column shift puzzle."""
        self.randomize_grid_shape()
        self.frame_index = 0
        self.animating = False
        self.anim_frame = 0
        self.solved = False
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.auto_plan = []
        self.auto_wait_frames = 2
        self.prev_action = self.BLANK_ACTION.copy()
        self.mode = random.choice(["row", "column"])
        self.cursor_row = random.randint(0, self.rows - 1)
        self.cursor_col = random.randint(0, self.cols - 1)
        self.board_rect = self.get_centered_board_rect(self.board_width, self.board_height)
        self.reference_image = self.get_random_pattern_image(self.board_width, self.board_height) if self.use_local_pattern_image else self.get_random_image(self.board_width, self.board_height)
        self.slot_rects = self.get_board_grid_rects(self.board_rect, self.rows, self.cols)
        self.pieces = self.split_image_into_square_pieces(self.reference_image, self.rows, self.cols, self.board_rect)
        self.scramble_board()

    def randomize_grid_shape(self) -> None:
        """Choose a fresh grid size for the next round."""
        self.rows, self.cols = random.choice([(3, 4), (4, 4), (4, 5)])

    def getPrompt(self) -> str:
        """Return the prompt with controls and puzzle rules."""
        return "This is Row Column Shift Puzzle. The image is cut into a grid. In row mode, Left and Right shift the selected row and wrap pieces around while Up and Down move to another row. In column mode, Up and Down shift the selected column and wrap pieces around while Left and Right move to another column. Press W to switch between row mode and column mode. Restore the image to win."

    def scramble_board(self) -> None:
        """Scramble the puzzle through reversible row and column shifts."""
        self.auto_operations = []
        for _ in range(random.randint(18, 30)):
            axis = random.choice(["row", "column"])
            if axis == "row":
                index = random.randint(0, self.rows - 1)
            else:
                index = random.randint(0, self.cols - 1)
            amount = random.choice([-1, 1])
            self.apply_shift(axis, index, amount, False)
            self.auto_operations.insert(0, (axis, index, -amount))

    def apply_shift(self, axis: str, index: int, amount: int, animate: bool) -> None:
        """Shift one row or column and optionally animate the movement."""
        if axis == "row":
            self.shift_row(self.pieces, index, amount, self.board_rect, self.rows, self.cols, animate)
        else:
            self.shift_column(self.pieces, index, amount, self.board_rect, self.rows, self.cols, animate)
        if animate:
            self.animating = True
            self.anim_frame = 0

    def update(self, action: ActionState) -> bool:
        """Advance shift animation, input, solved timing, and restart timing."""
        self.frame_index += 1
        if self.end_event_pending:
            self.end_event_pending = False
            return True
        if self.animating:
            self.update_animation()
            return False
        if self.solved:
            self.update_win_state()
            return False
        pressed = self.get_pressed_action(action)
        self.handle_input(pressed)
        return False

    def handle_input(self, pressed: ActionState) -> None:
        """Apply mode toggle, cursor movement, and loop shifts."""
        if pressed["W"]:
            self.toggle_mode()
            return
        if self.mode == "row":
            self.handle_row_mode_input(pressed)
        else:
            self.handle_column_mode_input(pressed)

    def toggle_mode(self) -> None:
        """Switch between row shifting and column shifting."""
        self.mode = "column" if self.mode == "row" else "row"

    def handle_row_mode_input(self, pressed: ActionState) -> None:
        """Handle controls while row mode is active."""
        if pressed["LU"] and self.cursor_row > 0:
            self.cursor_row -= 1
        elif pressed["LD"] and self.cursor_row < self.rows - 1:
            self.cursor_row += 1
        elif pressed["LL"]:
            self.apply_shift("row", self.cursor_row, -1, True)
        elif pressed["LR"]:
            self.apply_shift("row", self.cursor_row, 1, True)

    def handle_column_mode_input(self, pressed: ActionState) -> None:
        """Handle controls while column mode is active."""
        if pressed["LL"] and self.cursor_col > 0:
            self.cursor_col -= 1
        elif pressed["LR"] and self.cursor_col < self.cols - 1:
            self.cursor_col += 1
        elif pressed["LU"]:
            self.apply_shift("column", self.cursor_col, -1, True)
        elif pressed["LD"]:
            self.apply_shift("column", self.cursor_col, 1, True)

    def update_animation(self) -> None:
        """Advance the active row or column shift animation."""
        self.anim_frame += 1
        progress = self.anim_frame / self.anim_total_frames
        self.update_piece_motion(self.pieces, progress)
        if self.anim_frame >= self.anim_total_frames:
            self.animating = False
            self.update_piece_motion(self.pieces, 1)
            if self.is_solved():
                self.solved = True
                self.end_screen_frames = 0

    def update_win_state(self) -> None:
        """Advance the visible win screen and reset after a short pause."""
        self.end_screen_frames += 1
        if self.end_screen_frames == self.end_event_frame:
            self.end_event_pending = True
        if self.end_screen_frames >= self.end_screen_auto_reset:
            self.reset()

    def is_solved(self) -> bool:
        """Return whether every piece is back in its source slot."""
        return all(piece.is_home() for piece in self.pieces)

    def draw(self) -> None:
        """Draw the loop-shift puzzle and win overlay."""
        self.draw_background()
        self.draw_board()
        self.draw_pieces(self.pieces)
        self.draw_cursor()
        if self.solved:
            self.draw_win_overlay()

    def draw_background(self) -> None:
        """Draw the puzzle background."""
        self.screen.fill(self.background_color)
        pygame.draw.rect(self.screen, (33, 42, 54), pygame.Rect(18, 18, self.width - 36, self.height - 36), border_radius=14)

    def draw_board(self) -> None:
        """Draw the target board and grid lines."""
        pygame.draw.rect(self.screen, (0, 0, 0), self.board_rect.move(5, 7), border_radius=10)
        pygame.draw.rect(self.screen, self.board_fill, self.board_rect, border_radius=10)
        ghost = self.reference_image.copy()
        ghost.set_alpha(30)
        self.screen.blit(ghost, self.board_rect.topleft)
        for row in range(self.rows):
            for col in range(self.cols):
                pygame.draw.rect(self.screen, self.board_line, self.slot_rects[row][col], 1)

    def draw_cursor(self) -> None:
        """Draw the selected row or column without text."""
        cell_rect = self.slot_rects[self.cursor_row][self.cursor_col]
        if self.mode == "row":
            row_rect = pygame.Rect(self.board_rect.left, cell_rect.top, self.board_rect.width, cell_rect.height)
            pygame.draw.rect(self.screen, self.mode_color, row_rect.inflate(8, 8), 4, border_radius=8)
        else:
            col_rect = pygame.Rect(cell_rect.left, self.board_rect.top, cell_rect.width, self.board_rect.height)
            pygame.draw.rect(self.screen, self.mode_color, col_rect.inflate(8, 8), 4, border_radius=8)
        pygame.draw.rect(self.screen, self.cursor_color, cell_rect.inflate(8, 8), 4, border_radius=7)

    def draw_win_overlay(self) -> None:
        """Draw the winning screen."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((80, 220, 150, 42))
        self.screen.blit(overlay, (0, 0))
        text = self.win_font.render("You win", True, (246, 255, 249))
        shadow = self.win_font.render("You win", True, (12, 31, 22))
        text_rect = text.get_rect(center=(self.width // 2, self.height // 2))
        self.screen.blit(shadow, shadow.get_rect(center=(text_rect.centerx + 3, text_rect.centery + 4)))
        self.screen.blit(text, text_rect)

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Return logical autoplay actions that reverse the scramble operations."""
        action = self.BLANK_ACTION.copy()
        if self.frame_index == 0 or self.solved or self.animating:
            return action
        if frame_index % self.moveInterval != 0:
            return action
        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action
        if len(self.auto_plan) == 0:
            self.auto_plan = self.build_auto_plan()
            if len(self.auto_plan) == 0:
                return action
        key = self.auto_plan.pop(0)
        action[key] = True
        self.auto_wait_frames = random.randint(0, 1)
        return action

    def build_auto_plan(self) -> list[str]:
        """Build controls for the next reverse scramble operation."""
        if len(self.auto_operations) == 0:
            return []
        axis, index, amount = self.auto_operations.pop(0)
        plan = []
        mode = self.mode
        row = self.cursor_row
        col = self.cursor_col
        if axis == "row":
            if mode != "row":
                plan.append("W")
                mode = "row"
            while row > index:
                plan.append("LU")
                row -= 1
            while row < index:
                plan.append("LD")
                row += 1
            plan.append("LR" if amount > 0 else "LL")
        else:
            if mode != "column":
                plan.append("W")
                mode = "column"
            while col > index:
                plan.append("LL")
                col -= 1
            while col < index:
                plan.append("LR")
                col += 1
            plan.append("LD" if amount > 0 else "LU")
        return plan


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(RowColumnShiftPuzzle)
