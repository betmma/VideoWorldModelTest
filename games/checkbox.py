import os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class CheckboxGame(GameBase):
    name = "Checkbox"

    def __init__(self, headless: bool = False) -> None:
        """Initialize the checkbox game with one target key and one checkbox."""
        self.key_order = ("W", "A", "S", "D", "LU", "LL", "LD", "LR")
        self.key_names = {"W": "W", "A": "A", "S": "S", "D": "D", "LU": "Up Arrow", "LL": "Left Arrow", "LD": "Down Arrow", "LR": "Right Arrow"}
        self.target_key = random.choice(self.key_order)
        super().__init__(headless=headless)
        self.theme = self._make_theme()
        self.reset()

    def _make_theme(self) -> dict[str, tuple[int, int, int]]:
        """Choose a simple color theme for the checkbox."""
        themes = [
            {"bg": (238, 241, 245), "box": (250, 252, 255), "edge": (55, 67, 82), "check": (42, 144, 92), "shadow": (186, 194, 204)},
            {"bg": (32, 39, 48), "box": (230, 235, 240), "edge": (222, 228, 235), "check": (255, 196, 70), "shadow": (14, 18, 24)},
            {"bg": (246, 235, 224), "box": (255, 250, 244), "edge": (96, 70, 56), "check": (60, 129, 188), "shadow": (205, 184, 166)},
        ]
        return random.choice(themes)

    def reset(self) -> None:
        """Reset the checkbox state and autoplay timers without changing the target key."""
        self.frame_index = 0
        self.checked = random.choice([False, True])
        self.prev_target_pressed = False
        self.auto_key = None
        self.auto_frames_left = random.randint(8, 24)

    def update(self, action: ActionState) -> bool:
        """Toggle the checkbox only on the target key's press edge."""
        self.frame_index += 1
        target_pressed = action[self.target_key]
        if target_pressed and not self.prev_target_pressed:
            self.checked = not self.checked
        self.prev_target_pressed = target_pressed
        return False

    def draw(self) -> None:
        """Draw only the checkbox on the screen."""
        self.screen.fill(self.theme["bg"])
        rect = self._checkbox_rect()
        pygame.draw.rect(self.screen, self.theme["shadow"], rect.move(self.height // 90, self.height // 90), border_radius=self.height // 80)
        pygame.draw.rect(self.screen, self.theme["box"], rect, border_radius=self.height // 80)
        pygame.draw.rect(self.screen, self.theme["edge"], rect, width=self.height // 65, border_radius=self.height // 80)
        if self.checked:
            self._draw_check(rect)

    def _checkbox_rect(self) -> pygame.Rect:
        """Return the centered checkbox rectangle."""
        size = self.height // 4
        return pygame.Rect((self.width - size) // 2, (self.height - size) // 2, size, size)

    def _draw_check(self, rect: pygame.Rect) -> None:
        """Draw the check mark inside the checkbox."""
        stroke = self.height // 35
        points = [(rect.left + rect.width * 25 // 100, rect.top + rect.height * 53 // 100), (rect.left + rect.width * 43 // 100, rect.top + rect.height * 70 // 100), (rect.left + rect.width * 77 // 100, rect.top + rect.height * 31 // 100)]
        pygame.draw.lines(self.screen, self.theme["check"], False, points, stroke)

    def getPrompt(self) -> str:
        """Return the prompt describing which key toggles the checkbox."""
        return f"This is Checkbox. The screen contains one checkbox. Pressing {self.key_names[self.target_key]} checks the checkbox if it is unchecked, or unchecks it if it is checked. Pressing any other action key does nothing."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Generate target and decoy key presses only on moveInterval frames."""
        action = self.BLANK_ACTION.copy()
        if frame_index % self.moveInterval != 0:
            return action
        if self.auto_frames_left <= 0:
            self.auto_key = random.choice(self.key_order)
            self.auto_frames_left = random.randint(2, 7)
        if self.auto_key is not None:
            action[self.auto_key] = True
            self.auto_key = None
        self.auto_frames_left -= 1
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(CheckboxGame)
