import math, os, random, sys, pygame

import cv2
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class SimpleMoveBase(GameBase):
    name = "Simple Move"
    variantsPath = "simpleMoves"

    def __init__(self, headless: bool = False) -> None:
        """Initialize the grid, movement keys, object style, and animation settings."""
        self.key_order = ("W", "A", "S", "D", "LU", "LL", "LD", "LR")
        self.key_names = {"W": "W", "A": "A", "S": "S", "D": "D", "LU": "Up Arrow", "LL": "Left Arrow", "LD": "Down Arrow", "LR": "Right Arrow"}
        keys = random.sample(self.key_order, 4)
        self.direction_keys = {"up": keys[0], "down": keys[1], "left": keys[2], "right": keys[3]}
        self.grid_cols = random.randint(6, 9)
        self.grid_rows = random.randint(4, 6)
        self.move_anim_total_frames = 8
        self.object_style = random.choice(["cursor", "simple", "complex"])
        self.object_radius = self.height // 18
        super().__init__(headless=headless)
        self.theme = self._make_theme()
        self.reset()

    def _make_theme(self) -> dict[str, tuple[int, int, int]]:
        """Choose a simple theme for the grid and object."""
        themes = [
            {"bg": (234, 238, 243), "cell_a": (250, 252, 255), "cell_b": (239, 244, 249), "line": (186, 197, 210), "object": (54, 122, 202), "object_dark": (26, 68, 126), "object_light": (148, 204, 255), "cursor": (245, 248, 252), "cursor_edge": (34, 42, 52), "shadow": (155, 166, 181)},
            {"bg": (27, 34, 43), "cell_a": (46, 56, 68), "cell_b": (39, 49, 61), "line": (88, 101, 118), "object": (250, 188, 67), "object_dark": (165, 105, 26), "object_light": (255, 230, 145), "cursor": (240, 244, 247), "cursor_edge": (8, 12, 18), "shadow": (11, 15, 20)},
            {"bg": (244, 234, 222), "cell_a": (255, 249, 240), "cell_b": (239, 223, 204), "line": (198, 176, 154), "object": (69, 165, 114), "object_dark": (28, 94, 64), "object_light": (156, 231, 184), "cursor": (255, 252, 246), "cursor_edge": (83, 59, 46), "shadow": (188, 162, 136)},
        ]
        return random.choice(themes)

    def reset(self) -> None:
        """Reset the object position and autoplay state without changing the prompt."""
        self.frame_index = 0
        self.row = random.randrange(self.grid_rows)
        self.col = random.randrange(self.grid_cols)
        self.display_row = self.row
        self.display_col = self.col
        self.start_row = self.row
        self.start_col = self.col
        self.animating = False
        self.anim_frame = 0
        self.prev_action = self.BLANK_ACTION.copy()
        self.auto_ticks_left = random.randint(1, 5)

    def update(self, action: ActionState) -> bool:
        """Advance animation and start a new grid move from a movement key press."""
        self.frame_index += 1
        pressed_action = self._pressed_action(action)
        if self.animating:
            self._advance_animation()
        if not self.animating:
            direction = self._direction_from_action(pressed_action)
            if direction is not None:
                self._start_move(direction)
        return False

    def _pressed_action(self, action: ActionState) -> ActionState:
        """Return keys that became pressed on this frame."""
        pressed_action = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action[key]:
                pressed_action[key] = True
        self.prev_action = action.copy()
        return pressed_action

    def _direction_from_action(self, action: ActionState) -> str | None:
        """Return the first prompted movement direction contained in an action."""
        for direction in ("up", "down", "left", "right"):
            if action[self.direction_keys[direction]]:
                return direction
        return None

    def _direction_delta(self, direction: str) -> tuple[int, int]:
        """Return the row and column delta for one movement direction."""
        if direction == "up":
            return -1, 0
        if direction == "down":
            return 1, 0
        if direction == "left":
            return 0, -1
        return 0, 1

    def _start_move(self, direction: str) -> None:
        """Start an animated one-cell move when the target cell is inside the grid."""
        dr, dc = self._direction_delta(direction)
        target_row = self.row + dr
        target_col = self.col + dc
        if 0 <= target_row < self.grid_rows and 0 <= target_col < self.grid_cols:
            self.start_row = self.row
            self.start_col = self.col
            self.row = target_row
            self.col = target_col
            self.display_row = self.start_row
            self.display_col = self.start_col
            self.animating = True
            self.anim_frame = 0

    def _advance_animation(self) -> None:
        """Move the displayed object position toward the target cell."""
        self.anim_frame += 1
        t = self._anim_progress()
        self.display_row = self.start_row + (self.row - self.start_row) * t
        self.display_col = self.start_col + (self.col - self.start_col) * t
        if self.anim_frame >= self.move_anim_total_frames:
            self.animating = False
            self.display_row = self.row
            self.display_col = self.col

    def _anim_progress(self) -> float:
        """Return an eased progress value for the active movement animation."""
        t = self.anim_frame / self.move_anim_total_frames
        return 1.0 - (1.0 - t) * (1.0 - t)

    def draw(self) -> None:
        """Draw the grid and animated object."""
        self.screen.fill(self.theme["bg"])
        tile_size, offset_x, offset_y = self._grid_info()
        self._draw_grid(tile_size, offset_x, offset_y)
        x, y = self._cell_center(self.display_row, self.display_col, tile_size, offset_x, offset_y)
        self._draw_object(x, y, tile_size)

    def _grid_info(self) -> tuple[int, int, int]:
        """Return tile size and top-left offset for the centered grid."""
        tile_size = self.height // (self.grid_rows + 3)
        board_w = self.grid_cols * tile_size
        board_h = self.grid_rows * tile_size
        return tile_size, (self.width - board_w) // 2, (self.height - board_h) // 2

    def _draw_grid(self, tile_size: int, offset_x: int, offset_y: int) -> None:
        """Draw a clear checkerboard grid."""
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                rect = pygame.Rect(offset_x + col * tile_size, offset_y + row * tile_size, tile_size, tile_size)
                color = self.theme["cell_a"] if (row + col) % 2 == 0 else self.theme["cell_b"]
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, self.theme["line"], rect, 1)

    def _cell_center(self, row: float, col: float, tile_size: int, offset_x: int, offset_y: int) -> tuple[float, float]:
        """Return the pixel center for a grid row and column."""
        return offset_x + (col + 0.5) * tile_size, offset_y + (row + 0.5) * tile_size

    def _draw_object(self, x: float, y: float, tile_size: int) -> None:
        """Draw the selected object style at the given center."""
        radius = tile_size // 3
        if self.object_style == "cursor":
            self._draw_cursor_object(x, y, radius)
        elif self.object_style == "simple":
            self._draw_simple_object(x, y, radius)
        else:
            self._draw_complex_object(x, y, radius)

    def _draw_cursor_object(self, x: float, y: float, radius: int) -> None:
        """Draw a cursor-like object."""
        points = [(x - radius * 0.45, y - radius * 0.7), (x + radius * 0.65, y), (x + radius * 0.08, y + radius * 0.1), (x + radius * 0.35, y + radius * 0.72), (x + radius * 0.05, y + radius * 0.84), (x - radius * 0.18, y + radius * 0.2), (x - radius * 0.64, y + radius * 0.54)]
        pygame.draw.polygon(self.screen, self.theme["cursor_edge"], points)
        inner = [(x - radius * 0.32, y - radius * 0.44), (x + radius * 0.37, y - radius * 0.01), (x - radius * 0.04, y + radius * 0.04), (x + radius * 0.2, y + radius * 0.58), (x + radius * 0.07, y + radius * 0.64), (x - radius * 0.16, y + radius * 0.08), (x - radius * 0.43, y + radius * 0.32)]
        pygame.draw.polygon(self.screen, self.theme["cursor"], inner)

    def _draw_simple_object(self, x: float, y: float, radius: int) -> None:
        """Draw a simple round object."""
        pygame.draw.circle(self.screen, self.theme["shadow"], (round(x + radius * 0.16), round(y + radius * 0.2)), radius)
        pygame.draw.circle(self.screen, self.theme["object_dark"], (round(x), round(y + radius * 0.08)), radius)
        pygame.draw.circle(self.screen, self.theme["object"], (round(x), round(y)), radius)
        pygame.draw.circle(self.screen, self.theme["object_light"], (round(x - radius * 0.32), round(y - radius * 0.32)), radius // 4)

    def _draw_complex_object(self, x: float, y: float, radius: int) -> None:
        """Draw a more detailed gem-like object."""
        star = []
        for index in range(10):
            angle = -math.pi / 2 + index * math.pi / 5
            point_radius = radius if index % 2 == 0 else radius * 0.55
            star.append((x + math.cos(angle) * point_radius, y + math.sin(angle) * point_radius))
        pygame.draw.polygon(self.screen, self.theme["shadow"], [(px + radius * 0.12, py + radius * 0.18) for px, py in star])
        pygame.draw.polygon(self.screen, self.theme["object_dark"], star)
        inner = [(x + (px - x) * 0.76, y + (py - y) * 0.76) for px, py in star]
        pygame.draw.polygon(self.screen, self.theme["object"], inner)
        pygame.draw.line(self.screen, self.theme["object_light"], (x - radius * 0.35, y - radius * 0.2), (x + radius * 0.25, y - radius * 0.45), radius // 8)
        pygame.draw.circle(self.screen, self.theme["object_light"], (round(x + radius * 0.18), round(y + radius * 0.16)), radius // 6)

    def frameToState(self, frame_rgb: np.ndarray) -> dict[str, float | int | None]:
        """Recover the grid size and visible object position from pixels."""
        center = self._recover_object_center(frame_rgb)
        grid = self._recover_grid_geometry(frame_rgb)
        if center is None or grid is None:
            return {"rows": None, "cols": None, "row": None, "col": None}

        center_x, center_y = center
        rows, cols, tile_size, offset_x, offset_y = grid
        row = (center_y - offset_y) / tile_size - 0.5
        col = (center_x - offset_x) / tile_size - 0.5
        return {"rows": rows, "cols": cols, "row": round(row, 2), "col": round(col, 2)}

    def expectedFrameToState(self) -> dict[str, float | int]:
        """Return the expected parser result for the current rendered state."""
        return {"rows": self.grid_rows, "cols": self.grid_cols, "row": round(float(self.display_row), 2), "col": round(float(self.display_col), 2)}

    def statesMatch(self, gt_state, pred_state, last_gt_state, last_pred_state) -> bool:
        """Allow small parser and video drift around the visible object position."""
        if not isinstance(gt_state, dict) or not isinstance(pred_state, dict):
            return False
        if gt_state.get("rows") != pred_state.get("rows") or gt_state.get("cols") != pred_state.get("cols"):
            return False
        if gt_state.get("row") is None or pred_state.get("row") is None or gt_state.get("col") is None or pred_state.get("col") is None:
            return False
        return abs(float(gt_state["row"]) - float(pred_state["row"])) <= 0.2 and abs(float(gt_state["col"]) - float(pred_state["col"])) <= 0.2

    def _recover_object_center(self, frame_rgb: np.ndarray) -> tuple[float, float] | None:
        """Find the small non-grid object as a compact connected component."""
        height, width = frame_rgb.shape[:2]
        if height == 0 or width == 0:
            return None

        quantized = (frame_rgb // 16).astype(np.int32)
        color_bins = quantized[:, :, 0] * 256 + quantized[:, :, 1] * 16 + quantized[:, :, 2]
        values, counts = np.unique(color_bins, return_counts=True)
        dominant = values[counts >= max(50, int(height * width * 0.01))]
        if dominant.size < min(4, len(values)):
            dominant = values[np.argsort(counts)[-min(4, len(values)) :]]
        mask = ~np.isin(color_bins, dominant)

        kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        component_count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        best_label = None
        best_score = -1.0
        min_area = max(20, int(height * width * 0.0002))
        max_box = max(8, min(height, width) // 5)
        for label in range(1, component_count):
            x, y, component_w, component_h, area = stats[label]
            if area < min_area or component_w < 4 or component_h < 4:
                continue
            if component_w > max_box or component_h > max_box:
                continue
            fill_ratio = area / max(1, component_w * component_h)
            score = area * fill_ratio
            if score > best_score:
                best_score = score
                best_label = label

        if best_label is None:
            return None
        center_x, center_y = centroids[best_label]
        return float(center_x), float(center_y)

    def _recover_grid_geometry(self, frame_rgb: np.ndarray) -> tuple[int, int, float, int, int] | None:
        """Recover rows, columns, tile size, and board offset from the visible grid."""
        height, width = frame_rgb.shape[:2]
        if height == 0 or width == 0:
            return None

        background = self._corner_color(frame_rgb)
        difference = np.abs(frame_rgb.astype(np.int16) - background).sum(axis=2)
        mask = difference > 10
        x_hits = np.flatnonzero(mask.sum(axis=0) > height * 0.05)
        y_hits = np.flatnonzero(mask.sum(axis=1) > width * 0.05)
        if x_hits.size == 0 or y_hits.size == 0:
            return None

        left, right = int(x_hits[0]), int(x_hits[-1]) + 1
        top, bottom = int(y_hits[0]), int(y_hits[-1]) + 1
        board_w = right - left
        board_h = bottom - top

        row_ratios = {rows: (rows * (self.height // (rows + 3))) / self.height for rows in range(4, 7)}
        height_ratio = board_h / height
        rows = min(row_ratios, key=lambda candidate: abs(row_ratios[candidate] - height_ratio))
        tile_size = board_h / rows
        cols = max(1, round(board_w / tile_size))
        return rows, cols, tile_size, left, top

    def _corner_color(self, frame_rgb: np.ndarray) -> np.ndarray:
        """Estimate the background color from the frame corners."""
        height, width = frame_rgb.shape[:2]
        patch = max(3, min(height, width) // 30)
        corners = [
            frame_rgb[:patch, :patch],
            frame_rgb[:patch, width - patch :],
            frame_rgb[height - patch :, :patch],
            frame_rgb[height - patch :, width - patch :],
        ]
        pixels = np.concatenate([corner.reshape(-1, 3) for corner in corners], axis=0)
        return np.median(pixels, axis=0).astype(np.int16)

    def _decoy_keys(self) -> list[str]:
        """Return action keys that are not assigned to movement."""
        return [key for key in self.key_order if key not in self.direction_keys.values()]

    def _choose_auto_key(self) -> str:
        """Choose a movement key or a harmless decoy key."""
        if random.random() < 0.22:
            return random.choice(self._decoy_keys())
        direction = random.choice(["up", "down", "left", "right"])
        return self.direction_keys[direction]

    def getPrompt(self) -> str:
        """Return the prompt describing the discrete movement controls."""
        return f"This is Simple Move. The object moves on a {self.grid_cols} by {self.grid_rows} grid. Pressing {self.key_names[self.direction_keys['up']]} moves the object one cell up, pressing {self.key_names[self.direction_keys['down']]} moves it one cell down, pressing {self.key_names[self.direction_keys['left']]} moves it one cell left, and pressing {self.key_names[self.direction_keys['right']]} moves it one cell right. The object animates between grid cells. Pressing any other action key does nothing."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Emit single-frame movement or decoy pulses only on moveInterval frames."""
        action = self.BLANK_ACTION.copy()
        if frame_index % self.moveInterval != 0:
            return action
        if self.animating:
            return action
        if self.auto_ticks_left > 0:
            self.auto_ticks_left -= 1
            return action
        key = self._choose_auto_key()
        self.auto_ticks_left = random.randint(1, 4)
        action[key] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(SimpleMoveBase)
