from __future__ import annotations

import os,sys,random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.zuma import ZumaBase

class OrderedTrioZuma(ZumaBase):
    name = "Zuma Ordered Trio"

    def _choose_active_colors(self) -> list[tuple[int, int, int]]:
        self.match_order_head_to_tail = random.sample([0, 1, 2], 3)
        self.match_order_tail_to_head = list(reversed(self.match_order_head_to_tail))
        return random.sample(random.choice(self.color_libraries), 3)

    def _on_round_reset(self) -> None:
        return None

    def _available_ammo_tokens(self) -> list[int]:
        return self._autoplay_token_options()

    def _find_match_group(self, tokens: list[int], focus_index: int | None) -> tuple[int, int] | None:
        pattern = self.match_order_tail_to_head
        pattern_len = len(pattern)
        if len(tokens) < pattern_len:
            return None

        if focus_index is not None and 0 <= focus_index < len(tokens):
            start_min = max(0, focus_index - pattern_len + 1)
            start_max = min(focus_index, len(tokens) - pattern_len)
            for start in range(start_min, start_max + 1):
                if tokens[start : start + pattern_len] == pattern:
                    return start, start + pattern_len - 1

        for start in range(len(tokens) - pattern_len + 1):
            if tokens[start : start + pattern_len] == pattern:
                return start, start + pattern_len - 1
        return None

    def _is_setup_after_insert(self, tokens: list[int], insert_index: int) -> bool:
        if not (0 <= insert_index < len(tokens)) or len(tokens) < 2:
            return False

        setup_pairs = [
            self.match_order_tail_to_head[:2],
            self.match_order_tail_to_head[1:],
        ]
        start_min = max(0, insert_index - 1)
        start_max = min(insert_index, len(tokens) - 2)
        for start in range(start_min, start_max + 1):
            if tokens[start : start + 2] in setup_pairs:
                return True
        return False

    def _draw_hud_rule(self, hud_color: tuple[int, int, int]) -> None:
        label = self.small_font.render("Match", True, hud_color)
        radius = 8
        gap = 6
        balls_width = len(self.match_order_head_to_tail) * radius * 2 + (len(self.match_order_head_to_tail) - 1) * gap
        total_width = label.get_width() + 12 + balls_width
        start_x = self.width // 2 - total_width*2
        rule_y=64
        label_rect = label.get_rect(midleft=(start_x, rule_y))
        self.screen.blit(label, label_rect)

        ball_x = label_rect.right + 12 + radius
        for index, token in enumerate(self.match_order_head_to_tail):
            self._draw_ball(ball_x + index * (radius * 2 + gap), rule_y-4, radius, token)

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. A or Left rotates the stone frog left, and D or Right rotates it right. "
            "Press W or Up Arrow to shoot the loaded colored ball into the moving chain. Press S or Down Arrow to swap the loaded ball with the reserve ball. Variant rule: each round only uses three colors, and a group disappears only when three touching balls match the displayed head-to-tail color order exactly. The displayed order changes each round. Clear the whole chain before the front reaches the tunnel at the end of the track. After winning or losing, press A or Left Arrow to restart."
        )

if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_autoplay(OrderedTrioZuma)