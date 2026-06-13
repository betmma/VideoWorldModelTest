import os, random, sys, pygame

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class ProgressBarBase(GameBase):
    name = "Progress Bar"
    variantsPath = "progressBars"

    def __init__(self, headless: bool = False) -> None:
        """Initialize the progress bar controls, theme, and discrete segment count."""
        self.key_order = ("W", "A", "S", "D", "LU", "LL", "LD", "LR")
        self.key_names = {"W": "W", "A": "A", "S": "S", "D": "D", "LU": "Up Arrow", "LL": "Left Arrow", "LD": "Down Arrow", "LR": "Right Arrow"}
        self.increase_key, self.decrease_key = random.sample(self.key_order, 2)
        self.segment_count = random.randint(6, 10)
        super().__init__(headless=headless)
        self.theme = self._make_theme()
        self.reset()

    def _make_theme(self) -> dict[str, tuple[int, int, int]]:
        """Choose a compact visual theme for the progress bar."""
        themes = [
            {"bg": (236, 239, 244), "shell": (45, 55, 70), "empty": (215, 221, 229), "fill": (56, 159, 108), "line": (245, 248, 252), "shadow": (172, 182, 194)},
            {"bg": (29, 35, 45), "shell": (230, 236, 242), "empty": (73, 84, 99), "fill": (250, 191, 73), "line": (23, 28, 36), "shadow": (11, 14, 19)},
            {"bg": (246, 236, 222), "shell": (93, 70, 57), "empty": (226, 207, 184), "fill": (63, 132, 190), "line": (255, 250, 244), "shadow": (201, 181, 158)},
        ]
        return random.choice(themes)

    def reset(self) -> None:
        """Reset the fill level and autoplay timer without changing the prompt."""
        self.frame_index = 0
        self.level = random.randint(0, self.segment_count)
        self.prev_increase_pressed = False
        self.prev_decrease_pressed = False
        self.auto_ticks_left = random.randint(2, 7)

    def update(self, action: ActionState) -> bool:
        """Apply one-segment changes only on increase or decrease key press edges."""
        self.frame_index += 1
        increase_pressed = action[self.increase_key]
        decrease_pressed = action[self.decrease_key]
        if increase_pressed and not self.prev_increase_pressed and self.level < self.segment_count:
            self.level += 1
        if decrease_pressed and not self.prev_decrease_pressed and self.level > 0:
            self.level -= 1
        self.prev_increase_pressed = increase_pressed
        self.prev_decrease_pressed = decrease_pressed
        return False

    def draw(self) -> None:
        """Draw the segmented progress bar."""
        self.screen.fill(self.theme["bg"])
        rect = self._bar_rect()
        self._draw_bar_shell(rect)
        self._draw_discrete_segments(rect)

    def _bar_rect(self) -> pygame.Rect:
        """Return the centered progress bar rectangle."""
        width = self.width * 7 // 10
        height = self.height // 6
        return pygame.Rect((self.width - width) // 2, (self.height - height) // 2, width, height)

    def _draw_bar_shell(self, rect: pygame.Rect) -> None:
        """Draw the outer bar shell and shadow."""
        pygame.draw.rect(self.screen, self.theme["shadow"], rect.move(self.height // 80, self.height // 80), border_radius=self.height // 65)
        pygame.draw.rect(self.screen, self.theme["shell"], rect, border_radius=self.height // 65)

    def _inner_rect(self, rect: pygame.Rect) -> pygame.Rect:
        """Return the drawable area inside the progress bar shell."""
        pad = self.height // 35
        return rect.inflate(-pad * 2, -pad * 2)

    def _draw_discrete_segments(self, rect: pygame.Rect) -> None:
        """Draw individual filled or empty segments with visible gaps."""
        inner = self._inner_rect(rect)
        gap = self.height // 80
        segment_width = (inner.width - gap * (self.segment_count - 1)) // self.segment_count
        for index in range(self.segment_count):
            x = inner.left + index * (segment_width + gap)
            segment = pygame.Rect(x, inner.top, segment_width, inner.height)
            color = self.theme["fill"] if index < self.level else self.theme["empty"]
            pygame.draw.rect(self.screen, color, segment, border_radius=self.height // 120)
            pygame.draw.rect(self.screen, self.theme["line"], segment, width=1, border_radius=self.height // 120)

    def frameToState(self, frame_rgb: np.ndarray) -> dict[str, int]:
        """Recover the visible discrete segment count and filled segment count."""
        inner = self._frame_inner_rect(frame_rgb)
        segment_count = self._recover_segment_count(frame_rgb, inner)
        segment_colors = self._sample_segment_colors(frame_rgb, inner, segment_count)
        chromas = [self._color_chroma(color) for color in segment_colors]
        if not chromas:
            return {"segments": 0, "filled": 0}

        if max(chromas) - min(chromas) < 25:
            filled = segment_count if float(np.mean(chromas)) >= 55 else 0
        else:
            threshold = (max(chromas) + min(chromas)) / 2
            filled_mask = [chroma >= threshold for chroma in chromas]
            filled = self._best_prefix_count(filled_mask)
        return {"segments": segment_count, "filled": filled}

    def expectedFrameToState(self) -> dict[str, int]:
        """Return the expected parsed state for the current rendered frame."""
        return {"segments": self.segment_count, "filled": self.level}

    def _frame_inner_rect(self, frame_rgb: np.ndarray) -> pygame.Rect:
        """Return the expected inner bar rectangle for an arbitrary frame size."""
        frame_height, frame_width = frame_rgb.shape[:2]
        bar_width = frame_width * 7 // 10
        bar_height = frame_height // 6
        rect = pygame.Rect((frame_width - bar_width) // 2, (frame_height - bar_height) // 2, bar_width, bar_height)
        pad = frame_height // 35
        return rect.inflate(-pad * 2, -pad * 2)

    def _recover_segment_count(self, frame_rgb: np.ndarray, inner: pygame.Rect) -> int:
        """Infer the number of visible segments from the contrast at candidate gaps."""
        best_count = 6
        best_score = -1.0
        frame_height = frame_rgb.shape[0]
        for segment_count in range(6, 11):
            segment_colors = self._sample_segment_colors(frame_rgb, inner, segment_count)
            gap_colors = self._sample_gap_colors(frame_rgb, inner, segment_count, frame_height)
            if len(segment_colors) != segment_count or len(gap_colors) != segment_count - 1:
                continue
            score = 0.0
            for index, gap_color in enumerate(gap_colors):
                left_distance = self._color_distance(gap_color, segment_colors[index])
                right_distance = self._color_distance(gap_color, segment_colors[index + 1])
                score += min(left_distance, right_distance)
            score /= max(1, len(gap_colors))
            if score > best_score:
                best_score = score
                best_count = segment_count
        return best_count

    def _sample_segment_colors(self, frame_rgb: np.ndarray, inner: pygame.Rect, segment_count: int) -> list[np.ndarray]:
        """Sample one stable center patch from each candidate segment."""
        frame_height = frame_rgb.shape[0]
        gap = frame_height // 80
        segment_width = (inner.width - gap * (segment_count - 1)) // segment_count
        if segment_width <= 0:
            return []
        colors = []
        for index in range(segment_count):
            x = inner.left + index * (segment_width + gap) + segment_width // 2
            colors.append(self._sample_color(frame_rgb, x, inner.centery, max(1, min(segment_width, inner.height) // 6)))
        return colors

    def _sample_gap_colors(self, frame_rgb: np.ndarray, inner: pygame.Rect, segment_count: int, frame_height: int) -> list[np.ndarray]:
        """Sample the candidate gaps between segments."""
        gap = frame_height // 80
        segment_width = (inner.width - gap * (segment_count - 1)) // segment_count
        if segment_width <= 0 or gap <= 0:
            return []
        colors = []
        for index in range(segment_count - 1):
            x = inner.left + (index + 1) * segment_width + index * gap + gap // 2
            colors.append(self._sample_color(frame_rgb, x, inner.centery, max(1, gap // 3)))
        return colors

    def _sample_color(self, frame_rgb: np.ndarray, x: int, y: int, radius: int) -> np.ndarray:
        """Return the median RGB color around a point."""
        height, width = frame_rgb.shape[:2]
        left = max(0, x - radius)
        right = min(width, x + radius + 1)
        top = max(0, y - radius)
        bottom = min(height, y + radius + 1)
        return np.median(frame_rgb[top:bottom, left:right].reshape(-1, 3), axis=0)

    def _color_chroma(self, color: np.ndarray) -> float:
        """Return a simple saturation-like colorfulness score."""
        return float(np.max(color) - np.min(color))

    def _color_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Return a simple RGB distance."""
        return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).sum())

    def _best_prefix_count(self, mask: list[bool]) -> int:
        """Return the prefix length that best explains a left-to-right fill mask."""
        total_true = sum(mask)
        true_prefix = 0
        best_count = 0
        best_mismatches = total_true
        for count in range(1, len(mask) + 1):
            if mask[count - 1]:
                true_prefix += 1
            mismatches = count - true_prefix + total_true - true_prefix
            if mismatches < best_mismatches:
                best_mismatches = mismatches
                best_count = count
        return best_count

    def _decoy_keys(self) -> list[str]:
        """Return action keys that do not affect this progress bar."""
        return [key for key in self.key_order if key not in (self.increase_key, self.decrease_key)]

    def _choose_auto_key(self) -> str:
        """Choose a useful key or a decoy key for the next autoplay pulse."""
        if random.random() < 0.25:
            return random.choice(self._decoy_keys())
        if self.level <= 1:
            return self.increase_key
        if self.level >= self.segment_count - 1:
            return self.decrease_key
        return random.choice([self.increase_key, self.decrease_key])

    def getPrompt(self) -> str:
        """Return the prompt describing the discrete progress bar controls."""
        return f"This is Progress Bar. The bar has {self.segment_count} discrete segments. Pressing {self.key_names[self.increase_key]} increases the filled portion by one segment. Pressing {self.key_names[self.decrease_key]} decreases the filled portion by one segment. Pressing any other action key does nothing."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Emit one-frame key pulses only on moveInterval frames."""
        action = self.BLANK_ACTION.copy()
        if frame_index % self.moveInterval != 0:
            return action
        if self.auto_ticks_left > 0:
            self.auto_ticks_left -= 1
            return action
        key = self._choose_auto_key()
        self.auto_ticks_left = random.randint(1, 5)
        action[key] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(ProgressBarBase)
