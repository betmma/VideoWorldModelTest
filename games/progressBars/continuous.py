import os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from pygameBase import ActionState
from games.progressBar import ProgressBarBase


class ContinuousProgressBar(ProgressBarBase):
    name = "Continuous Progress Bar"

    def __init__(self, headless: bool = False) -> None:
        """Initialize the continuous progress speed before the shared bar setup."""
        self.fill_speed = random.choice([0.35, 0.45, 0.55])
        super().__init__(headless=headless)

    def reset(self) -> None:
        """Reset the smooth fill level and autoplay timer without changing controls."""
        self.frame_index = 0
        self.fill = random.random()
        self.auto_key = None
        self.auto_ticks_left = random.randint(2, 7)

    def update(self, action: ActionState) -> bool:
        """Move the fill smoothly while the increase or decrease key is held."""
        self.frame_index += 1
        if action[self.increase_key]:
            self.fill += self.fill_speed / self.fps
        if action[self.decrease_key]:
            self.fill -= self.fill_speed / self.fps
        if self.fill > 1.0:
            self.fill = 1.0
        if self.fill < 0.0:
            self.fill = 0.0
        return False

    def draw(self) -> None:
        """Draw a continuous progress bar."""
        self.screen.fill(self.theme["bg"])
        rect = self._bar_rect()
        self._draw_bar_shell(rect)
        self._draw_continuous_fill(rect)

    def _draw_continuous_fill(self, rect: pygame.Rect) -> None:
        """Draw the smooth filled and empty parts of the bar."""
        inner = self._inner_rect(rect)
        pygame.draw.rect(self.screen, self.theme["empty"], inner, border_radius=self.height // 120)
        filled_width = round(inner.width * self.fill)
        filled = pygame.Rect(inner.left, inner.top, filled_width, inner.height)
        pygame.draw.rect(self.screen, self.theme["fill"], filled, border_radius=self.height // 120)
        pygame.draw.rect(self.screen, self.theme["line"], inner, width=1, border_radius=self.height // 120)

    def _choose_auto_key(self) -> str | None:
        """Choose a held key or blank wait for continuous autoplay."""
        if random.random() < 0.18:
            return None
        if random.random() < 0.25:
            return random.choice(self._decoy_keys())
        if self.fill < 0.18:
            return self.increase_key
        if self.fill > 0.82:
            return self.decrease_key
        return random.choice([self.increase_key, self.decrease_key])

    def getPrompt(self) -> str:
        """Return the prompt describing the continuous progress bar controls."""
        return f"This is Continuous Progress Bar. Pressing and holding {self.key_names[self.increase_key]} increases the filled portion smoothly. Pressing and holding {self.key_names[self.decrease_key]} decreases the filled portion smoothly. The filling speed is {round(self.fill_speed * 100)} percent of the bar per second while the key is held. Pressing any other action key does nothing."

    def getAutoAction(self, frame_index: int) -> ActionState:
        """Switch held keys only on moveInterval frames and hold them between switches."""
        action = self.BLANK_ACTION.copy()
        if frame_index % self.moveInterval == 0:
            if self.auto_ticks_left <= 0:
                self.auto_key = self._choose_auto_key()
                self.auto_ticks_left = random.randint(3, 12)
            else:
                self.auto_ticks_left -= 1
        if self.auto_key is not None:
            action[self.auto_key] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(ContinuousProgressBar)
