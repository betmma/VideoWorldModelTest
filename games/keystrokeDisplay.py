import os, random, sys

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class KeystrokeDisplay(GameBase):
    name = "Keystroke Display"

    def __init__(self, headless: bool = False) -> None:
        """Initialize the key display, fonts, theme, and autoplay state."""
        self.key_order = ("W", "A", "S", "D", "LU", "LL", "LD", "LR")
        self.key_labels = {"W": "W", "A": "A", "S": "S", "D": "D", "LU": "UP", "LL": "LEFT", "LD": "DOWN", "LR": "RIGHT"}
        super().__init__(headless=headless)
        pygame.font.init()
        self.key_font = pygame.font.SysFont("consolas", self.height // 12, bold=True)
        self.word_font = pygame.font.SysFont("consolas", self.height // 25, bold=True)
        self.theme = self._make_theme()
        self.reset()

    def _make_theme(self) -> dict[str, tuple[int, int, int]]:
        """Choose one simple visual theme for the current run."""
        themes = [
            {"bg_top": (22, 28, 34), "bg_bottom": (68, 54, 46), "key": (222, 226, 228), "edge": (132, 142, 150), "text": (31, 36, 42), "lit": (255, 203, 72), "lit_edge": (201, 132, 30), "lit_text": (42, 30, 14), "shadow": (9, 12, 15)},
            {"bg_top": (18, 43, 54), "bg_bottom": (31, 75, 56), "key": (235, 239, 232), "edge": (124, 151, 134), "text": (22, 44, 38), "lit": (106, 215, 246), "lit_edge": (32, 129, 173), "lit_text": (5, 35, 54), "shadow": (7, 18, 22)},
            {"bg_top": (47, 31, 55), "bg_bottom": (72, 46, 52), "key": (232, 224, 216), "edge": (153, 128, 139), "text": (43, 32, 39), "lit": (122, 238, 153), "lit_edge": (42, 156, 84), "lit_text": (11, 49, 28), "shadow": (15, 10, 18)},
        ]
        return random.choice(themes)

    def reset(self) -> None:
        """Reset the display state and begin with a short blank autoplay wait."""
        self.frame_index = 0
        self.current_key = None
        self.auto_key = None
        self.auto_frames_left = random.randint(8, 22)

    def update(self, action: ActionState) -> bool:
        """Advance one frame and display at most one active key from the action."""
        self.frame_index += 1
        self.current_key = self._active_key_from_action(action)
        return False

    def _active_key_from_action(self, action: ActionState) -> str | None:
        """Return the first active key so the display never lights multiple keys."""
        for key in self.key_order:
            if action[key]:
                return key
        return None

    def draw(self) -> None:
        """Draw the background and the eight keycaps."""
        self._draw_background()
        for key, rect in self._key_layout():
            self._draw_key(key, rect, key == self.current_key)

    def _draw_background(self) -> None:
        """Draw a quiet gradient background behind the keycaps."""
        top = self.theme["bg_top"]
        bottom = self.theme["bg_bottom"]
        denom = self.height - 1
        for y in range(self.height):
            color = ((top[0] * (denom - y) + bottom[0] * y) // denom, (top[1] * (denom - y) + bottom[1] * y) // denom, (top[2] * (denom - y) + bottom[2] * y) // denom)
            pygame.draw.line(self.screen, color, (0, y), (self.width, y))

    def _key_layout(self) -> list[tuple[str, pygame.Rect]]:
        """Build the two familiar keyboard clusters for WASD and arrows."""
        key_size = self.height // 7
        gap = self.height // 32
        left_x = self.width * 31 // 100
        right_x = self.width * 69 // 100
        center_y = self.height * 57 // 100
        top_y = center_y - key_size - gap
        left_offset = key_size + gap
        right_offset = key_size + gap
        return [
            ("W", self._key_rect(left_x, top_y, key_size)),
            ("A", self._key_rect(left_x - left_offset, center_y, key_size)),
            ("S", self._key_rect(left_x, center_y, key_size)),
            ("D", self._key_rect(left_x + left_offset, center_y, key_size)),
            ("LU", self._key_rect(right_x, top_y, key_size)),
            ("LL", self._key_rect(right_x - right_offset, center_y, key_size)),
            ("LD", self._key_rect(right_x, center_y, key_size)),
            ("LR", self._key_rect(right_x + right_offset, center_y, key_size)),
        ]

    def _key_rect(self, center_x: int, center_y: int, key_size: int) -> pygame.Rect:
        """Create a key rectangle centered at the requested position."""
        return pygame.Rect(center_x - key_size // 2, center_y - key_size // 2, key_size, key_size)

    def _draw_key(self, key: str, rect: pygame.Rect, active: bool) -> None:
        """Draw one keycap in its normal or illuminated state."""
        shadow_rect = rect.move(0, self.height // 80)
        pygame.draw.rect(self.screen, self.theme["shadow"], shadow_rect, border_radius=self.height // 70)

        key_rect = rect.move(0, self.height // 160 if active else 0)
        fill = self.theme["lit"] if active else self.theme["key"]
        edge = self.theme["lit_edge"] if active else self.theme["edge"]
        text_color = self.theme["lit_text"] if active else self.theme["text"]
        pygame.draw.rect(self.screen, edge, key_rect, border_radius=self.height // 70)
        pygame.draw.rect(self.screen, fill, key_rect.inflate(-self.height // 80, -self.height // 80), border_radius=self.height // 90)

        label = self.key_labels[key]
        font = self.key_font if len(label) == 1 else self.word_font
        text = font.render(label, True, text_color)
        self.screen.blit(text, text.get_rect(center=key_rect.center))

    def getPrompt(self) -> str:
        """Return the prompt describing the key display rule."""
        return "This is Keystroke Display. The screen shows eight keycaps: W, A, S, D, Up Arrow, Left Arrow, Down Arrow, and Right Arrow. When an action key is held, only the matching keycap lights up. When no action key is held, all keycaps are unlit."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Alternate between blank waits and natural single-key holds."""
        action = self.BLANK_ACTION.copy()
        if frame_index%self.moveInterval !=0:
            action[self.auto_key] = True
            return action
        if self.auto_frames_left <= 0:
            if self.auto_key is None:
                self.auto_key = random.choice(self.key_order)
                self.auto_frames_left = random.randint(10, 34)
            else:
                self.auto_key = None
                self.auto_frames_left = random.randint(5, 20)
        if self.auto_key is not None:
            action[self.auto_key] = True
        self.auto_frames_left -= 1
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(KeystrokeDisplay)
