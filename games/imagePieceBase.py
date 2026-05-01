from __future__ import annotations

import io, os, random, sys, urllib.request, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class ImagePiece:
    """Store one cut-out part of an image together with its puzzle position and drawing state."""

    def __init__(self, id: int, source_row: int, source_col: int, row: int, col: int, surface: pygame.Surface, source_rect: pygame.Rect, home_center: tuple[float, float], fixed_center: bool = False) -> None:
        """Create a reusable piece that can move, rotate, or stay pinned to its original center."""
        self.id = id
        self.source_row = source_row
        self.source_col = source_col
        self.row = row
        self.col = col
        self.surface = surface
        self.source_rect = source_rect.copy()
        self.home_center = home_center
        self.center = home_center
        self.start_center = home_center
        self.target_center = home_center
        self.fixed_center = fixed_center
        self.angle = 0
        self.start_angle = 0
        self.target_angle = 0
        self.is_moving = False
        self.is_rotating = False
        self.visible = True
        self.center_offset = surface.get_rect().center

    def set_center(self, center: tuple[float, float]) -> None:
        """Place the piece center immediately unless the piece is pinned to its home center."""
        if self.fixed_center:
            self.center = self.home_center
            return
        self.center = center
        self.start_center = center
        self.target_center = center
        self.is_moving = False

    def set_grid_position(self, row: int, col: int, center: tuple[float, float] | None = None) -> None:
        """Update the logical board slot and optionally place the piece at that slot's center."""
        self.row = row
        self.col = col
        if center is not None:
            self.set_center(center)

    def move_to_center(self, center: tuple[float, float]) -> None:
        """Start a linear motion toward a screen-space center."""
        if self.fixed_center:
            self.center = self.home_center
            self.start_center = self.home_center
            self.target_center = self.home_center
            self.is_moving = False
            return
        self.start_center = self.center
        self.target_center = center
        self.is_moving = True

    def move_to_grid_position(self, row: int, col: int, center: tuple[float, float]) -> None:
        """Change the logical slot and animate toward the new slot center."""
        self.row = row
        self.col = col
        self.move_to_center(center)

    def rotate_to(self, angle: float) -> None:
        """Start a linear rotation toward an absolute angle in degrees."""
        self.start_angle = self.angle
        self.target_angle = angle
        self.is_rotating = True

    def rotate_quarter_turns(self, turns: int = 1) -> None:
        """Rotate the piece by a number of quarter turns."""
        self.rotate_to(self.angle + turns * 90)

    def update_motion(self, progress: float) -> None:
        """Interpolate active movement and rotation using a progress value from 0 to 1."""
        if self.is_moving:
            self.center = (self.start_center[0] + (self.target_center[0] - self.start_center[0]) * progress, self.start_center[1] + (self.target_center[1] - self.start_center[1]) * progress)
            if progress >= 1:
                self.center = self.target_center
                self.is_moving = False
        if self.is_rotating:
            self.angle = self.start_angle + (self.target_angle - self.start_angle) * progress
            if progress >= 1:
                self.angle = self.target_angle
                self.is_rotating = False

    def is_home(self) -> bool:
        """Return whether the piece is in its original grid slot and upright."""
        return self.row == self.source_row and self.col == self.source_col and self.angle % 360 == 0

    def get_draw_rect(self) -> pygame.Rect:
        """Return the unrotated draw rectangle for the current center."""
        return pygame.Rect(round(self.center[0] - self.center_offset[0]), round(self.center[1] - self.center_offset[1]), self.surface.get_width(), self.surface.get_height())

    def contains_point(self, point: tuple[int, int]) -> bool:
        """Return whether a screen point touches an opaque pixel of the unrotated piece."""
        rect = self.get_draw_rect()
        if not rect.collidepoint(point):
            return False
        local = point[0] - rect.left, point[1] - rect.top
        return self.surface.get_at(local).a > 0

    def draw(self, screen: pygame.Surface, shadow: bool = True) -> None:
        """Draw the piece on the target screen, rotating around its current center."""
        if not self.visible:
            return
        if shadow:
            shadow_surface = self.surface.copy()
            shadow_surface.fill((0, 0, 0, 70), special_flags=pygame.BLEND_RGBA_MULT)
            shadow_rect = self.get_draw_rect().move(3, 4)
            screen.blit(shadow_surface, shadow_rect)
        if self.angle % 360 == 0:
            screen.blit(self.surface, self.get_draw_rect())
            return
        rotated = pygame.transform.rotate(self.surface, self.angle)
        screen.blit(rotated, rotated.get_rect(center=(round(self.center[0]), round(self.center[1]))))


class ImagePieceGameBase(GameBase):
    """Pygame base class for image-piece games such as jigsaw puzzles, 15 puzzles, rotations, and row shifts."""

    name = "Image Piece Base"
    variantsPath = "imagePieces"
    excludeFromVariants = True
    use_local_pattern_image = False
    
    def __init_subclass__(cls, **kwargs) -> None:
        """Allow concrete subclasses to appear in variant selection unless they opt out themselves."""
        super().__init_subclass__(**kwargs)
        if "excludeFromVariants" not in cls.__dict__:
            cls.excludeFromVariants = False

    def __init__(self, headless: bool = False) -> None:
        """Initialize the pygame layer and shared image-piece game state."""
        self.image_url = ""
        self.prev_action = self.BLANK_ACTION.copy()
        super().__init__(headless=headless)

    def get_random_image(self, width: int | None = None, height: int | None = None) -> pygame.Surface:
        """Download and return a random Picsum image as a pygame surface."""
        if width is None:
            width = self.width
        if height is None:
            height = self.height
        random_token = random.randint(0, 1_000_000_000)
        image_url = f"https://picsum.photos/{width}/{height}?random={random_token}"
        self.image_url = image_url
        with urllib.request.urlopen(image_url, timeout=20) as response:
            image_bytes = response.read()
        image = pygame.image.load(io.BytesIO(image_bytes), image_url).convert()
        return pygame.transform.smoothscale(image, (width, height))

    def get_random_pattern_image(self, width: int | None = None, height: int | None = None) -> pygame.Surface:
        """Create a local random patterned image for testing without network access."""
        if width is None:
            width = self.width
        if height is None:
            height = self.height
        self.image_url = "local-random-pattern"
        image = pygame.Surface((width, height)).convert()
        top_color = (random.randint(50, 190), random.randint(50, 190), random.randint(50, 190))
        bottom_color = (random.randint(50, 220), random.randint(50, 220), random.randint(50, 220))
        for y in range(height):
            ratio = y / height
            color = (round(top_color[0] + (bottom_color[0] - top_color[0]) * ratio), round(top_color[1] + (bottom_color[1] - top_color[1]) * ratio), round(top_color[2] + (bottom_color[2] - top_color[2]) * ratio))
            pygame.draw.line(image, color, (0, y), (width, y))
        for _ in range(18):
            color = (random.randint(30, 250), random.randint(30, 250), random.randint(30, 250))
            rect = pygame.Rect(random.randint(0, width - width // 6), random.randint(0, height - height // 6), random.randint(width // 10, width // 3), random.randint(height // 10, height // 3))
            pygame.draw.rect(image, color, rect, border_radius=random.randint(4, 28))
        for _ in range(24):
            color = (random.randint(20, 255), random.randint(20, 255), random.randint(20, 255))
            center = (random.randint(0, width), random.randint(0, height))
            pygame.draw.circle(image, color, center, random.randint(width // 30, width // 10), width=random.randint(0, 5))
        for _ in range(36):
            color = (random.randint(20, 255), random.randint(20, 255), random.randint(20, 255))
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            pygame.draw.line(image, color, start, end, random.randint(2, 8))
        for col in range(0, width, width // 8):
            pygame.draw.line(image, (255, 255, 255), (col, 0), (col, height), 1)
        for row in range(0, height, height // 6):
            pygame.draw.line(image, (0, 0, 0), (0, row), (width, row), 1)
        return image

    def get_centered_board_rect(self, board_width: int, board_height: int) -> pygame.Rect:
        """Return a rectangle centered on the game screen."""
        return pygame.Rect((self.width - board_width) // 2, (self.height - board_height) // 2, board_width, board_height)

    def get_grid_rects(self, width: int, height: int, rows: int, cols: int) -> list[list[pygame.Rect]]:
        """Return image-space grid rectangles that cover the full width and height."""
        x_edges = [round(index * width / cols) for index in range(cols + 1)]
        y_edges = [round(index * height / rows) for index in range(rows + 1)]
        return [[pygame.Rect(x_edges[col], y_edges[row], x_edges[col + 1] - x_edges[col], y_edges[row + 1] - y_edges[row]) for col in range(cols)] for row in range(rows)]

    def get_board_grid_rects(self, board_rect: pygame.Rect, rows: int, cols: int) -> list[list[pygame.Rect]]:
        """Return screen-space grid rectangles inside a board rectangle."""
        image_rects = self.get_grid_rects(board_rect.width, board_rect.height, rows, cols)
        return [[rect.move(board_rect.left, board_rect.top) for rect in row] for row in image_rects]

    def get_cell_center(self, board_rect: pygame.Rect, rows: int, cols: int, row: int, col: int) -> tuple[float, float]:
        """Return the screen-space center of one board cell."""
        cell_rect = self.get_board_grid_rects(board_rect, rows, cols)[row][col]
        return cell_rect.center

    def split_image_into_square_pieces(self, image: pygame.Surface, rows: int, cols: int, board_rect: pygame.Rect | None = None, fixed_centers: bool = False) -> list[ImagePiece]:
        """Cut an image into rectangular pieces with transparent-free square edges."""
        if board_rect is None:
            board_rect = self.get_centered_board_rect(image.get_width(), image.get_height())
        grid_rects = self.get_grid_rects(image.get_width(), image.get_height(), rows, cols)
        pieces = []
        piece_id = 0
        for row in range(rows):
            for col in range(cols):
                source_rect = grid_rects[row][col]
                pieces.append(self.create_square_piece(piece_id, row, col, image, source_rect, board_rect, fixed_centers))
                piece_id += 1
        return pieces

    def split_image_into_jigsaw_pieces(self, image: pygame.Surface, rows: int, cols: int, board_rect: pygame.Rect | None = None, fixed_centers: bool = False, tab_scale: float = 0.18) -> list[ImagePiece]:
        """Cut an image into jigsaw pieces with matching tabs and holes."""
        if board_rect is None:
            board_rect = self.get_centered_board_rect(image.get_width(), image.get_height())
        grid_rects = self.get_grid_rects(image.get_width(), image.get_height(), rows, cols)
        edge_map = self.build_jigsaw_edges(rows, cols)
        pieces = []
        piece_id = 0
        for row in range(rows):
            for col in range(cols):
                source_rect = grid_rects[row][col]
                pieces.append(self.create_jigsaw_piece(piece_id, row, col, image, source_rect, board_rect, edge_map[row][col], fixed_centers, tab_scale))
                piece_id += 1
        return pieces

    def build_jigsaw_edges(self, rows: int, cols: int) -> list[list[dict[str, int]]]:
        """Create matching jigsaw edge signs where 1 is a tab, -1 is a hole, and 0 is flat."""
        edge_map = [[{"top": 0, "right": 0, "bottom": 0, "left": 0} for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            for col in range(cols):
                if col < cols - 1:
                    value = random.choice([-1, 1])
                    edge_map[row][col]["right"] = value
                    edge_map[row][col + 1]["left"] = -value
                if row < rows - 1:
                    value = random.choice([-1, 1])
                    edge_map[row][col]["bottom"] = value
                    edge_map[row + 1][col]["top"] = -value
        return edge_map

    def create_square_piece(self, piece_id: int, row: int, col: int, image: pygame.Surface, source_rect: pygame.Rect, board_rect: pygame.Rect, fixed_center: bool) -> ImagePiece:
        """Create one rectangular image piece from a source rectangle."""
        surface = pygame.Surface(source_rect.size, pygame.SRCALPHA)
        surface.blit(image, (0, 0), source_rect)
        pygame.draw.rect(surface, (255, 255, 255, 135), surface.get_rect(), 1)
        center = board_rect.left + source_rect.centerx, board_rect.top + source_rect.centery
        return ImagePiece(piece_id, row, col, row, col, surface, source_rect, center, fixed_center)

    def create_jigsaw_piece(self, piece_id: int, row: int, col: int, image: pygame.Surface, source_rect: pygame.Rect, board_rect: pygame.Rect, edges: dict[str, int], fixed_center: bool, tab_scale: float) -> ImagePiece:
        """Create one jigsaw-shaped image piece from a source rectangle and edge signs."""
        tab_radius = round((source_rect.width if source_rect.width < source_rect.height else source_rect.height) * tab_scale)
        surface = pygame.Surface((source_rect.width + tab_radius * 2, source_rect.height + tab_radius * 2), pygame.SRCALPHA)
        expanded_rect = pygame.Rect(source_rect.left - tab_radius, source_rect.top - tab_radius, surface.get_width(), surface.get_height())
        clipped_rect = expanded_rect.clip(image.get_rect())
        surface.blit(image, (clipped_rect.left - expanded_rect.left, clipped_rect.top - expanded_rect.top), clipped_rect)
        mask = self.make_jigsaw_shape_mask(source_rect.width, source_rect.height, tab_radius, edges)
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.draw_mask_outline(surface, mask)
        center = board_rect.left + source_rect.centerx, board_rect.top + source_rect.centery
        return ImagePiece(piece_id, row, col, row, col, surface, source_rect, center, fixed_center)

    def make_jigsaw_shape_mask(self, piece_width: int, piece_height: int, tab_radius: int, edges: dict[str, int]) -> pygame.Surface:
        """Build an alpha mask for one jigsaw piece."""
        mask = pygame.Surface((piece_width + tab_radius * 2, piece_height + tab_radius * 2), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        base_rect = pygame.Rect(tab_radius, tab_radius, piece_width, piece_height)
        pygame.draw.rect(mask, (255, 255, 255, 255), base_rect)
        centers = {"top": (base_rect.centerx, base_rect.top), "right": (base_rect.right, base_rect.centery), "bottom": (base_rect.centerx, base_rect.bottom), "left": (base_rect.left, base_rect.centery)}
        for side, value in edges.items():
            if value == 1:
                pygame.draw.circle(mask, (255, 255, 255, 255), centers[side], tab_radius)
            elif value == -1:
                pygame.draw.circle(mask, (0, 0, 0, 0), centers[side], tab_radius)
        return mask

    def draw_mask_outline(self, surface: pygame.Surface, mask_surface: pygame.Surface) -> None:
        """Draw a subtle outline around a piece mask."""
        mask = pygame.mask.from_surface(mask_surface)
        outline = mask.outline()
        if len(outline) > 1:
            pygame.draw.lines(surface, (255, 255, 255, 150), True, outline, 2)
            pygame.draw.lines(surface, (0, 0, 0, 70), True, outline, 1)

    def arrange_pieces_by_grid(self, pieces: list[ImagePiece], rows: int, cols: int) -> list[list[ImagePiece | None]]:
        """Return a board matrix using the pieces' current row and column values."""
        board = [[None for _ in range(cols)] for _ in range(rows)]
        for piece in pieces:
            board[piece.row][piece.col] = piece
        return board

    def piece_at(self, pieces: list[ImagePiece], row: int, col: int) -> ImagePiece | None:
        """Return the piece occupying one board slot."""
        for piece in pieces:
            if piece.row == row and piece.col == col:
                return piece
        return None

    def move_piece_to_cell(self, piece: ImagePiece, row: int, col: int, board_rect: pygame.Rect, rows: int, cols: int, animate: bool = True) -> None:
        """Move one piece to a board cell immediately or by animation."""
        center = self.get_cell_center(board_rect, rows, cols, row, col)
        if animate:
            piece.move_to_grid_position(row, col, center)
            return
        piece.set_grid_position(row, col, center)

    def swap_piece_slots(self, first_piece: ImagePiece, second_piece: ImagePiece, board_rect: pygame.Rect, rows: int, cols: int, animate: bool = True) -> None:
        """Swap two pieces' logical slots and centers."""
        first_row, first_col = first_piece.row, first_piece.col
        second_row, second_col = second_piece.row, second_piece.col
        self.move_piece_to_cell(first_piece, second_row, second_col, board_rect, rows, cols, animate)
        self.move_piece_to_cell(second_piece, first_row, first_col, board_rect, rows, cols, animate)

    def shift_row(self, pieces: list[ImagePiece], row: int, amount: int, board_rect: pygame.Rect, rows: int, cols: int, animate: bool = True) -> None:
        """Shift every piece in one row and wrap pieces around the row."""
        row_pieces = [piece for piece in pieces if piece.row == row]
        for piece in row_pieces:
            next_col = (piece.col + amount) % cols
            self.move_piece_to_cell(piece, row, next_col, board_rect, rows, cols, animate)

    def shift_column(self, pieces: list[ImagePiece], col: int, amount: int, board_rect: pygame.Rect, rows: int, cols: int, animate: bool = True) -> None:
        """Shift every piece in one column and wrap pieces around the column."""
        column_pieces = [piece for piece in pieces if piece.col == col]
        for piece in column_pieces:
            next_row = (piece.row + amount) % rows
            self.move_piece_to_cell(piece, next_row, col, board_rect, rows, cols, animate)

    def update_piece_motion(self, pieces: list[ImagePiece], progress: float) -> None:
        """Advance movement and rotation for every image piece."""
        for piece in pieces:
            piece.update_motion(progress)

    def draw_pieces(self, pieces: list[ImagePiece], shadow: bool = True) -> None:
        """Draw all visible image pieces on the game screen."""
        for piece in pieces:
            piece.draw(self.screen, shadow)

    def get_pressed_action(self, action: ActionState) -> ActionState:
        """Convert held actions into edge-triggered key presses."""
        pressed = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action.get(key, False):
                pressed[key] = True
        self.prev_action = action.copy()
        return pressed

    def action_to_grid_delta(self, action: ActionState) -> tuple[int, int]:
        """Return the first directional grid delta represented by an action state."""
        if action["W"] or action["LU"]:
            return -1, 0
        if action["S"] or action["LD"]:
            return 1, 0
        if action["A"] or action["LL"]:
            return 0, -1
        if action["D"] or action["LR"]:
            return 0, 1
        return 0, 0

    def direction_to_action(self, direction: tuple[int, int]) -> ActionState:
        """Return an action state for one row-column direction."""
        action = self.BLANK_ACTION.copy()
        if direction == (-1, 0):
            action["W"] = True
        elif direction == (1, 0):
            action["S"] = True
        elif direction == (0, -1):
            action["A"] = True
        elif direction == (0, 1):
            action["D"] = True
        return action
