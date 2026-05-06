from __future__ import annotations

import os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.imagePieceBase import ActionState, ImagePiece, ImagePieceGameBase


class JigsawPuzzle(ImagePieceGameBase):
    """Jigsaw puzzle game where arrow keys move a cursor and W picks up or drops image pieces."""

    name = "Jigsaw Puzzle"
    rows = 3
    cols = 4
    board_width = 456
    board_height = 342
    moveInterval = 1

    def __init__(self, headless: bool = False) -> None:
        """Create colors, timing values, and the first scattered puzzle."""
        self.fps = 30
        self.cursor_speed = 9
        self.cursor_radius = 11
        self.auto_wrong_chance = 0.18
        self.end_event_frame = 28
        self.end_screen_auto_reset = 120
        self.background_color = (18, 23, 31)
        self.table_color = (38, 47, 58)
        self.board_fill = (12, 16, 22)
        self.board_line = (185, 204, 226)
        self.cursor_color = (255, 214, 82)
        self.target_color = (113, 223, 174)
        self.hover_color = (94, 176, 255)
        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        self.win_font = pygame.font.SysFont("trebuchetms", 58, bold=True)
        self.reset()

    def reset(self) -> None:
        """Start a new puzzle using either a local test pattern or a downloaded random image."""
        self.randomize_grid_shape()
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_event_pending = False
        self.solved = False
        self.held_piece: ImagePiece | None = None
        self.auto_plan = []
        self.auto_wait_frames = 12
        self.prev_action = self.BLANK_ACTION.copy()
        self.board_rect = self.get_centered_board_rect(self.board_width, self.board_height)
        self.reference_image = self.get_random_pattern_image(self.board_width, self.board_height) if self.use_local_pattern_image else self.get_random_image(self.board_width, self.board_height)
        self.slot_rects = self.get_board_grid_rects(self.board_rect, self.rows, self.cols)
        self.pieces = self.split_image_into_jigsaw_pieces(self.reference_image, self.rows, self.cols, self.board_rect)
        self.scatter_pieces()
        self.cursor_x, self.cursor_y = self.pieces[0].center

    def randomize_grid_shape(self) -> None:
        """Choose a fresh jigsaw grid size for the next round."""
        self.rows, self.cols = random.choice([(2, 3), (3, 3), (3, 4), (4, 4), (4, 5)])

    def getPrompt(self) -> str:
        """Return the training prompt with rules and controls."""
        return "This is Jigsaw Puzzle. Image pieces start scattered along the sides of the screen. Use the Arrow keys to move the cursor. Press W to pick up the piece under the cursor, move it to the matching place in the target picture, and press W again to put it down. Place every piece in its correct target slot to complete the puzzle."

    def update(self, action: ActionState) -> bool:
        """Advance cursor movement, pickup/drop input, autoplay-visible state, and solved timing."""
        self.frame_index += 1
        if self.end_event_pending:
            self.end_event_pending = False
            return True
        pressed = self.get_pressed_action(action)
        self.move_cursor_from_action(action)
        if self.held_piece is not None:
            self.held_piece.set_center((self.cursor_x, self.cursor_y))
        if pressed["W"]:
            self.toggle_pickup_drop()
        if not self.solved and self.is_solved():
            self.solved = True
            self.end_screen_frames = 0
        if self.solved:
            self.end_screen_frames += 1
            if self.end_screen_frames == self.end_event_frame:
                self.end_event_pending = True
            if self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
        return False

    def move_cursor_from_action(self, action: ActionState) -> None:
        """Move the free cursor using held arrow-key actions."""
        if action["LL"]:
            self.cursor_x -= self.cursor_speed
        if action["LR"]:
            self.cursor_x += self.cursor_speed
        if action["LU"]:
            self.cursor_y -= self.cursor_speed
        if action["LD"]:
            self.cursor_y += self.cursor_speed
        if self.cursor_x < self.cursor_radius:
            self.cursor_x = self.cursor_radius
        if self.cursor_x > self.width - self.cursor_radius:
            self.cursor_x = self.width - self.cursor_radius
        if self.cursor_y < self.cursor_radius:
            self.cursor_y = self.cursor_radius
        if self.cursor_y > self.height - self.cursor_radius:
            self.cursor_y = self.height - self.cursor_radius

    def toggle_pickup_drop(self) -> None:
        """Pick up the top loose or misplaced piece, or drop the currently held piece."""
        if self.held_piece is not None:
            self.drop_held_piece()
            return
        piece = self.get_top_piece_under_cursor()
        if piece is not None:
            self.pick_up_piece(piece)

    def get_top_piece_under_cursor(self) -> ImagePiece | None:
        """Return the topmost non-locked piece under the cursor."""
        point = (round(self.cursor_x), round(self.cursor_y))
        for piece in reversed(self.pieces):
            if piece.is_home():
                continue
            if piece.contains_point(point):
                return piece
        return None

    def pick_up_piece(self, piece: ImagePiece) -> None:
        """Pick up one piece and move it above the other pieces for drawing."""
        piece.row = -1
        piece.col = -1
        piece.set_center((self.cursor_x, self.cursor_y))
        self.pieces.remove(piece)
        self.pieces.append(piece)
        self.held_piece = piece

    def drop_held_piece(self) -> None:
        """Drop the held piece into an empty board slot or onto the table."""
        piece = self.held_piece
        cell = self.get_cursor_board_cell()
        if cell is not None and self.piece_at_slot(cell[0], cell[1]) is None:
            center = self.get_cell_center(self.board_rect, self.rows, self.cols, cell[0], cell[1])
            piece.set_grid_position(cell[0], cell[1], center)
        else:
            piece.row = -1
            piece.col = -1
            piece.set_center((self.cursor_x, self.cursor_y))
        self.held_piece = None

    def get_cursor_board_cell(self) -> tuple[int, int] | None:
        """Return the board cell currently under the cursor."""
        point = (round(self.cursor_x), round(self.cursor_y))
        if not self.board_rect.collidepoint(point):
            return None
        for row in range(self.rows):
            for col in range(self.cols):
                if self.slot_rects[row][col].collidepoint(point):
                    return row, col
        return None

    def piece_at_slot(self, row: int, col: int) -> ImagePiece | None:
        """Return the piece currently snapped into one board slot."""
        for piece in self.pieces:
            if piece is not self.held_piece and piece.row == row and piece.col == col:
                return piece
        return None

    def is_solved(self) -> bool:
        """Return whether every piece is in its original slot."""
        return self.held_piece is None and all(piece.is_home() for piece in self.pieces)

    def scatter_pieces(self) -> None:
        """Scatter all pieces along the left and right sides of the screen."""
        shuffled = self.pieces[:]
        random.shuffle(shuffled)
        side_count = (len(shuffled) + 1) // 2
        usable_height = self.height - 80
        for index, piece in enumerate(shuffled):
            side_index = index // 2
            left_side = index % 2 == 0
            x = self.board_rect.left / 2 if left_side else (self.board_rect.right + self.width) / 2
            y = 40 + side_index * usable_height / (side_count - 1)
            x += random.randint(-32, 32)
            y += random.randint(-18, 18)
            piece.row = -1
            piece.col = -1
            piece.set_center((x, y))

    def draw(self) -> None:
        """Render the target board, pieces, solved glow, and cursor."""
        self.draw_background()
        self.draw_target_board()
        self.draw_scattered_pieces()
        if self.solved:
            self.draw_solved_glow()
        self.draw_cursor()

    def draw_background(self) -> None:
        """Draw a quiet tabletop background."""
        self.screen.fill(self.background_color)
        table_rect = pygame.Rect(16, 16, self.width - 32, self.height - 32)
        pygame.draw.rect(self.screen, self.table_color, table_rect, border_radius=14)
        for x in range(16, self.width - 16, 38):
            pygame.draw.line(self.screen, (45, 55, 67), (x, 16), (x + 90, self.height - 16), 1)

    def draw_target_board(self) -> None:
        """Draw the faint target picture and slot outlines."""
        shadow_rect = self.board_rect.move(5, 7)
        pygame.draw.rect(self.screen, (0, 0, 0), shadow_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.board_fill, self.board_rect, border_radius=10)
        ghost = self.reference_image.copy()
        ghost.set_alpha(42)
        self.screen.blit(ghost, self.board_rect.topleft)
        hover_cell = self.get_cursor_board_cell()
        for row in range(self.rows):
            for col in range(self.cols):
                rect = self.slot_rects[row][col]
                color = self.hover_color if hover_cell == (row, col) else self.board_line
                width = 3 if hover_cell == (row, col) else 1
                pygame.draw.rect(self.screen, color, rect, width, border_radius=4)

    def draw_scattered_pieces(self) -> None:
        """Draw all puzzle pieces, with the held piece drawn last."""
        for piece in self.pieces:
            if piece is not self.held_piece:
                piece.draw(self.screen, True)
        if self.held_piece is not None:
            self.held_piece.draw(self.screen, True)

    def draw_solved_glow(self) -> None:
        """Draw the winning screen."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((80, 220, 150, 42))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, self.target_color, self.board_rect.inflate(16, 16), 6, border_radius=14)
        text = self.win_font.render("You win", True, (246, 255, 249))
        shadow = self.win_font.render("You win", True, (12, 31, 22))
        text_rect = text.get_rect(center=(self.width // 2, self.height // 2))
        self.screen.blit(shadow, shadow.get_rect(center=(text_rect.centerx + 3, text_rect.centery + 4)))
        self.screen.blit(text, text_rect)

    def draw_cursor(self) -> None:
        """Draw the free cursor as a small crosshair."""
        center = (round(self.cursor_x), round(self.cursor_y))
        pygame.draw.circle(self.screen, self.cursor_color, center, self.cursor_radius, 3)
        pygame.draw.line(self.screen, self.cursor_color, (center[0] - 16, center[1]), (center[0] - 5, center[1]), 2)
        pygame.draw.line(self.screen, self.cursor_color, (center[0] + 5, center[1]), (center[0] + 16, center[1]), 2)
        pygame.draw.line(self.screen, self.cursor_color, (center[0], center[1] - 16), (center[0], center[1] - 5), 2)
        pygame.draw.line(self.screen, self.cursor_color, (center[0], center[1] + 5), (center[0], center[1] + 16), 2)

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Return autoplay actions that move pieces home, sometimes placing one wrong before correcting it."""
        action = self.BLANK_ACTION.copy()
        if self.frame_index == 0 or self.solved:
            return action
        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action
        if len(self.auto_plan) == 0:
            self.auto_plan = self.build_auto_plan()
            if len(self.auto_plan) == 0:
                self.auto_wait_frames = random.randint(8, 18)
                return action
        return self.advance_auto_plan(action)

    def build_auto_plan(self) -> list[tuple]:
        """Build a high-level cursor plan for the next unsolved piece."""
        if self.held_piece is not None:
            return [("move", self.held_piece.home_center[0], self.held_piece.home_center[1]), ("press", "W"), ("wait", random.randint(5, 10))]
        piece = self.choose_auto_piece()
        if piece is None:
            return []
        blocker = self.piece_at_slot(piece.source_row, piece.source_col)
        if blocker is not None and blocker is not piece:
            side_center = self.get_random_side_center()
            return [("move", blocker.center[0], blocker.center[1]), ("press", "W"), ("move", side_center[0], side_center[1]), ("press", "W"), ("wait", random.randint(5, 10))]
        plan = [("move", piece.center[0], piece.center[1]), ("press", "W"), ("wait", random.randint(3, 7))]
        wrong_cell = self.choose_wrong_empty_cell(piece) if random.random() < self.auto_wrong_chance else None
        if wrong_cell is not None:
            wrong_center = self.get_cell_center(self.board_rect, self.rows, self.cols, wrong_cell[0], wrong_cell[1])
            plan.extend([("move", wrong_center[0], wrong_center[1]), ("press", "W"), ("wait", random.randint(8, 16)), ("move", wrong_center[0], wrong_center[1]), ("press", "W"), ("wait", random.randint(3, 7))])
        plan.extend([("move", piece.home_center[0], piece.home_center[1]), ("press", "W"), ("wait", random.randint(8, 16))])
        return plan

    def choose_auto_piece(self) -> ImagePiece | None:
        """Choose the next unsolved piece, keeping the solve order easy to see."""
        unsolved = [piece for piece in self.pieces if not piece.is_home()]
        if len(unsolved) == 0:
            return None
        unsolved.sort(key=lambda piece: piece.id)
        return unsolved[0]

    def choose_wrong_empty_cell(self, piece: ImagePiece) -> tuple[int, int] | None:
        """Choose an empty board slot that is not the piece's home slot."""
        candidates = []
        for row in range(self.rows):
            for col in range(self.cols):
                if row == piece.source_row and col == piece.source_col:
                    continue
                if self.piece_at_slot(row, col) is None:
                    candidates.append((row, col))
        if len(candidates) == 0:
            return None
        return random.choice(candidates)

    def get_random_side_center(self) -> tuple[float, float]:
        """Return a random cursor destination away from the target board."""
        y = random.randint(38, self.height - 38)
        if random.choice([True, False]):
            return random.randint(42, self.board_rect.left - 42), y
        return random.randint(self.board_rect.right + 42, self.width - 42), y

    def advance_auto_plan(self, action: ActionState) -> ActionState:
        """Advance one high-level autoplay step and return the frame action."""
        step = self.auto_plan[0]
        if step[0] == "wait":
            frames_left = step[1] - 1
            if frames_left <= 0:
                self.auto_plan.pop(0)
            else:
                self.auto_plan[0] = ("wait", frames_left)
            return action
        if step[0] == "press":
            action[step[1]] = True
            self.auto_plan.pop(0)
            return action
        target_x = step[1]
        target_y = step[2]
        dx = target_x - self.cursor_x
        dy = target_y - self.cursor_y
        if abs(dx) <= self.cursor_speed and abs(dy) <= self.cursor_speed:
            self.auto_plan.pop(0)
            return action
        if dx < -self.cursor_speed:
            action["LL"] = True
        elif dx > self.cursor_speed:
            action["LR"] = True
        if dy < -self.cursor_speed:
            action["LU"] = True
        elif dy > self.cursor_speed:
            action["LD"] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(JigsawPuzzle)
