from __future__ import annotations

import os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.imagePieceBase import ActionState, ImagePiece, ImagePieceGameBase


class FifteenPuzzle(ImagePieceGameBase):
    """Sliding image puzzle with one empty slot."""

    name = "15 Puzzle"
    rows = 4
    cols = 4
    board_size = 376
    moveInterval = 4

    def __init__(self, headless: bool = False) -> None:
        """Create the shared visual settings and first sliding puzzle."""
        self.fps = 30
        self.anim_total_frames = 8
        self.end_event_frame = 28
        self.end_screen_auto_reset = 120
        self.background_color = (23, 28, 36)
        self.board_fill = (12, 16, 22)
        self.board_line = (190, 207, 226)
        self.blank_color = (7, 10, 15)
        self.win_color = (113, 223, 174)
        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        self.win_font = pygame.font.SysFont("trebuchetms", 58, bold=True)
        self.reset()

    def reset(self) -> None:
        """Build a fresh scrambled sliding puzzle."""
        self.frame_index = 0
        self.animating = False
        self.anim_frame = 0
        self.solved = False
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.auto_wait_frames = 2
        self.prev_action = self.BLANK_ACTION.copy()
        self.board_rect = self.get_centered_board_rect(self.board_size, self.board_size)
        self.reference_image = self.get_random_pattern_image(self.board_size, self.board_size) if self.use_local_pattern_image else self.get_random_image(self.board_size, self.board_size)
        all_pieces = self.split_image_into_square_pieces(self.reference_image, self.rows, self.cols, self.board_rect)
        self.blank_home = (self.rows - 1, self.cols - 1)
        self.pieces = [piece for piece in all_pieces if (piece.source_row, piece.source_col) != self.blank_home]
        self.board = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        for piece in self.pieces:
            self.board[piece.row][piece.col] = piece
        self.blank_row, self.blank_col = self.blank_home
        self.board[self.blank_row][self.blank_col] = None
        self.scramble_board()

    def getPrompt(self) -> str:
        """Return the prompt with controls and puzzle rules."""
        return "This is 15 Puzzle. The picture is split into a four by four grid with one empty slot. Use the Arrow keys to slide the empty slot up, left, down, or right by moving the adjacent image tile into it. Restore the whole image to win."

    def scramble_board(self) -> None:
        """Scramble the board through legal moves while recording the reverse solution."""
        self.auto_moves = []
        last_direction = None
        for _ in range(random.randint(34, 56)):
            legal = self.get_legal_blank_directions()
            if last_direction is not None and len(legal) > 1 and self.opposite_direction(last_direction) in legal:
                legal.remove(self.opposite_direction(last_direction))
            direction = random.choice(legal)
            self.move_blank(direction, False)
            self.auto_moves.insert(0, self.opposite_direction(direction))
            last_direction = direction

    def get_legal_blank_directions(self) -> list[tuple[int, int]]:
        """Return directions the empty slot can move."""
        directions = []
        for direction in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            row = self.blank_row + direction[0]
            col = self.blank_col + direction[1]
            if 0 <= row < self.rows and 0 <= col < self.cols:
                directions.append(direction)
        return directions

    def move_blank(self, direction: tuple[int, int], animate: bool) -> bool:
        """Move the empty slot by swapping it with an adjacent tile."""
        next_row = self.blank_row + direction[0]
        next_col = self.blank_col + direction[1]
        if not (0 <= next_row < self.rows and 0 <= next_col < self.cols):
            return False
        piece = self.board[next_row][next_col]
        self.board[self.blank_row][self.blank_col] = piece
        self.board[next_row][next_col] = None
        if animate:
            piece.move_to_grid_position(self.blank_row, self.blank_col, self.get_cell_center(self.board_rect, self.rows, self.cols, self.blank_row, self.blank_col))
            self.animating = True
            self.anim_frame = 0
        else:
            piece.set_grid_position(self.blank_row, self.blank_col, self.get_cell_center(self.board_rect, self.rows, self.cols, self.blank_row, self.blank_col))
        self.blank_row = next_row
        self.blank_col = next_col
        return True

    def update(self, action: ActionState) -> bool:
        """Advance animation, input, solved timing, and restart timing."""
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
        direction = self.pressed_to_direction(pressed)
        if direction is not None:
            self.move_blank(direction, True)
        return False

    def update_animation(self) -> None:
        """Advance the active tile slide animation."""
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

    def pressed_to_direction(self, action: ActionState) -> tuple[int, int] | None:
        """Convert a pressed arrow key to an empty-slot direction."""
        if action["LU"]:
            return -1, 0
        if action["LD"]:
            return 1, 0
        if action["LL"]:
            return 0, -1
        if action["LR"]:
            return 0, 1
        return None

    def direction_to_arrow_action(self, direction: tuple[int, int]) -> ActionState:
        """Convert a direction into an arrow-key action."""
        action = self.BLANK_ACTION.copy()
        if direction == (-1, 0):
            action["LU"] = True
        elif direction == (1, 0):
            action["LD"] = True
        elif direction == (0, -1):
            action["LL"] = True
        elif direction == (0, 1):
            action["LR"] = True
        return action

    def opposite_direction(self, direction: tuple[int, int]) -> tuple[int, int]:
        """Return the opposite row-column direction."""
        return -direction[0], -direction[1]

    def is_solved(self) -> bool:
        """Return whether every visible piece and the blank slot are home."""
        return (self.blank_row, self.blank_col) == self.blank_home and all(piece.is_home() for piece in self.pieces)

    def draw(self) -> None:
        """Draw the sliding puzzle board and win overlay."""
        self.draw_background()
        self.draw_board()
        self.draw_pieces(self.pieces)
        if self.solved:
            self.draw_win_overlay()

    def draw_background(self) -> None:
        """Draw the puzzle background."""
        self.screen.fill(self.background_color)
        pygame.draw.rect(self.screen, (35, 43, 54), pygame.Rect(18, 18, self.width - 36, self.height - 36), border_radius=14)

    def draw_board(self) -> None:
        """Draw the target frame and empty slot."""
        pygame.draw.rect(self.screen, (0, 0, 0), self.board_rect.move(5, 7), border_radius=10)
        pygame.draw.rect(self.screen, self.board_fill, self.board_rect, border_radius=10)
        for row in range(self.rows):
            for col in range(self.cols):
                rect = self.get_board_grid_rects(self.board_rect, self.rows, self.cols)[row][col]
                pygame.draw.rect(self.screen, self.board_line, rect, 1)
        blank_rect = self.get_board_grid_rects(self.board_rect, self.rows, self.cols)[self.blank_row][self.blank_col]
        pygame.draw.rect(self.screen, self.blank_color, blank_rect.inflate(-5, -5), border_radius=6)

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

    def getAutoAction(self) -> ActionState:
        """Return the next logical reverse-scramble autoplay action."""
        action = self.BLANK_ACTION.copy()
        if self.frame_index == 0 or self.solved or self.animating:
            return action
        if self.frame_index % self.moveInterval != 0:
            return action
        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action
        if len(self.auto_moves) == 0:
            return action
        direction = self.auto_moves.pop(0)
        self.auto_wait_frames = random.randint(0, 2)
        return self.direction_to_arrow_action(direction)


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(FifteenPuzzle)
