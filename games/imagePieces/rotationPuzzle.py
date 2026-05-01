from __future__ import annotations

import os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.imagePieceBase import ActionState, ImagePiece, ImagePieceGameBase


class RotationPuzzle(ImagePieceGameBase):
    """Image puzzle where fixed-center tiles must be rotated upright."""

    name = "Rotation Puzzle"
    board_width = 456
    board_height = 342
    moveInterval = 4

    def __init__(self, headless: bool = False) -> None:
        """Create visual settings and the first rotation puzzle."""
        self.fps = 30
        self.anim_total_frames = 8
        self.auto_wrong_chance = 0.08
        self.end_event_frame = 28
        self.end_screen_auto_reset = 120
        self.background_color = (20, 25, 34)
        self.board_fill = (12, 16, 22)
        self.board_line = (186, 205, 226)
        self.cursor_color = (255, 214, 82)
        self.win_color = (113, 223, 174)
        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        self.win_font = pygame.font.SysFont("trebuchetms", 58, bold=True)
        self.reset()

    def reset(self) -> None:
        """Build a new fixed-center rotation puzzle."""
        self.randomize_grid_shape()
        self.frame_index = 0
        self.animating = False
        self.anim_frame = 0
        self.rotating_piece: ImagePiece | None = None
        self.solved = False
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.auto_plan = []
        self.auto_wait_frames = 2
        self.prev_action = self.BLANK_ACTION.copy()
        self.board_rect = self.get_centered_board_rect(self.board_width, self.board_height)
        self.reference_image = self.get_random_pattern_image(self.board_width, self.board_height) if self.use_local_pattern_image else self.get_random_image(self.board_width, self.board_height)
        self.slot_rects = self.get_board_grid_rects(self.board_rect, self.rows, self.cols)
        self.pieces = self.split_image_into_square_pieces(self.reference_image, self.rows, self.cols, self.board_rect, True)
        for piece in self.pieces:
            piece.angle = random.choice([0, 90, 180, 270])
            piece.target_angle = piece.angle
            piece.start_angle = piece.angle
        self.pieces[0].angle = random.choice([90, 180, 270])
        self.pieces[0].target_angle = self.pieces[0].angle
        self.cursor_row = random.randint(0, self.rows - 1)
        self.cursor_col = random.randint(0, self.cols - 1)

    def randomize_grid_shape(self) -> None:
        """Choose a fresh grid size for the next round."""
        self.rows, self.cols = random.choice([(3, 3), (3, 4), (4, 4)])

    def getPrompt(self) -> str:
        """Return the prompt with controls and puzzle rules."""
        return "This is Rotation Puzzle. The image is cut into fixed-position square tiles. Use the Arrow keys to move the cursor. Press W to rotate the selected tile clockwise by a quarter turn. Rotate every tile upright to restore the picture and win."

    def update(self, action: ActionState) -> bool:
        """Advance rotation animation, input, solved timing, and restart timing."""
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
        """Apply cursor movement and selected-tile rotation."""
        if pressed["LU"] and self.cursor_row > 0:
            self.cursor_row -= 1
        elif pressed["LD"] and self.cursor_row < self.rows - 1:
            self.cursor_row += 1
        elif pressed["LL"] and self.cursor_col > 0:
            self.cursor_col -= 1
        elif pressed["LR"] and self.cursor_col < self.cols - 1:
            self.cursor_col += 1
        if pressed["W"]:
            self.rotate_selected_piece()

    def rotate_selected_piece(self) -> None:
        """Start rotating the selected tile clockwise."""
        piece = self.piece_at(self.pieces, self.cursor_row, self.cursor_col)
        self.rotating_piece = piece
        piece.rotate_quarter_turns(1)
        self.animating = True
        self.anim_frame = 0

    def update_animation(self) -> None:
        """Advance the active rotation animation."""
        self.anim_frame += 1
        progress = self.anim_frame / self.anim_total_frames
        self.update_piece_motion(self.pieces, progress)
        if self.anim_frame >= self.anim_total_frames:
            self.animating = False
            self.update_piece_motion(self.pieces, 1)
            self.rotating_piece.angle = self.rotating_piece.angle % 360
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
        """Return whether every tile is upright."""
        return all(piece.angle % 360 == 0 for piece in self.pieces)

    def draw(self) -> None:
        """Draw the rotation puzzle and win overlay."""
        self.draw_background()
        self.draw_board()
        self.draw_pieces(self.pieces)
        self.draw_cursor()
        if self.solved:
            self.draw_win_overlay()

    def draw_background(self) -> None:
        """Draw the puzzle background."""
        self.screen.fill(self.background_color)
        pygame.draw.rect(self.screen, (34, 42, 54), pygame.Rect(18, 18, self.width - 36, self.height - 36), border_radius=14)

    def draw_board(self) -> None:
        """Draw the target board and slot outlines."""
        pygame.draw.rect(self.screen, (0, 0, 0), self.board_rect.move(5, 7), border_radius=10)
        pygame.draw.rect(self.screen, self.board_fill, self.board_rect, border_radius=10)
        ghost = self.reference_image.copy()
        ghost.set_alpha(28)
        self.screen.blit(ghost, self.board_rect.topleft)
        for row in range(self.rows):
            for col in range(self.cols):
                pygame.draw.rect(self.screen, self.board_line, self.slot_rects[row][col], 1)

    def draw_cursor(self) -> None:
        """Draw the selected tile cursor."""
        rect = self.slot_rects[self.cursor_row][self.cursor_col].inflate(8, 8)
        pygame.draw.rect(self.screen, self.cursor_color, rect, 4, border_radius=7)

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
        """Return logical autoplay actions that rotate tiles upright."""
        action = self.BLANK_ACTION.copy()
        if self.frame_index == 0 or self.solved or self.animating:
            return action
        if self.frame_index % self.moveInterval != 0:
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
        """Build cursor moves and W presses for one useful rotation."""
        solved_pieces = [piece for piece in self.pieces if piece.angle % 360 == 0]
        unsolved_pieces = [piece for piece in self.pieces if piece.angle % 360 != 0]
        if len(unsolved_pieces) == 0:
            return []
        if len(solved_pieces) > 0 and random.random() < self.auto_wrong_chance:
            piece = random.choice(solved_pieces)
            turns = 1
        else:
            unsolved_pieces.sort(key=lambda piece: piece.id)
            piece = unsolved_pieces[0]
            turns = (-piece.angle // 90) % 4
        return self.plan_cursor_route(piece.row, piece.col) + ["W" for _ in range(turns)]

    def plan_cursor_route(self, target_row: int, target_col: int) -> list[str]:
        """Return arrow-key steps from the current cursor cell to a target cell."""
        plan = []
        row = self.cursor_row
        col = self.cursor_col
        while row > target_row:
            plan.append("LU")
            row -= 1
        while row < target_row:
            plan.append("LD")
            row += 1
        while col > target_col:
            plan.append("LL")
            col -= 1
        while col < target_col:
            plan.append("LR")
            col += 1
        return plan


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(RotationPuzzle)
