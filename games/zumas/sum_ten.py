from __future__ import annotations

import os,sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.zuma import ZumaBase


class SumTenZuma(ZumaBase):
    name = "Zuma Sum Ten"

    number_palette = [
        (242, 104, 92),
        (245, 166, 70),
        (246, 212, 92),
        (120, 196, 108),
        (72, 187, 174),
        (82, 152, 236),
        (122, 111, 232),
        (187, 104, 219),
        (235, 116, 169),
    ]

    def _autoplay_token_options(self) -> list[int]:
        return list(range(1, 10))
    
    def _available_ammo_tokens(self):
        return list(range(1, 10))

    def _token_fill_color(self, token: int) -> tuple[int, int, int]:
        return self.number_palette[(token - 1) % len(self.number_palette)]

    def _draw_ball_overlay(self, x: float, y: float, radius: float, token: int) -> None:
        label = self.small_font.render(str(token), True, (28, 24, 22))
        self.screen.blit(label, label.get_rect(center=(int(x), int(y))))

    def _find_match_group(self, tokens: list[int], focus_index: int | None) -> tuple[int, int] | None:
        candidates: list[tuple[int, int]] = []
        for left in range(len(tokens)):
            total = 0
            for right in range(left, len(tokens)):
                total += tokens[right]
                if total == 10:
                    candidates.append((left, right))
                if total >= 10:
                    break

        if focus_index is not None:
            focused = [pair for pair in candidates if pair[0] <= focus_index <= pair[1]]
            if focused:
                focused.sort(key=lambda pair: (pair[1] - pair[0], pair[0]))
                return focused[0]

        if not candidates:
            return None
        candidates.sort(key=lambda pair: (pair[0], pair[1] - pair[0]))
        return candidates[0]

    def _is_setup_after_insert(self, tokens: list[int], insert_index: int) -> bool:
        return False

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. A or Left rotates the stone frog left, and D or Right rotates it right. "
            "Press W or Up Arrow to shoot the loaded numbered ball into the moving chain. Press S or Down Arrow to swap the loaded ball with the reserve ball. Variant rule: any touching contiguous segment whose numbers sum to 10 disappears, which can trigger more clears after gaps close. Clear the whole chain before the front reaches the tunnel at the end of the track. After winning or losing, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(SumTenZuma)
