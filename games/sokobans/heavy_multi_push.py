from __future__ import annotations

import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import Box, SokobanBase


class HeavyMultiPushSokoban(SokobanBase):
    name = "Heavy Multi Push Sokoban"

    def get_default_level_map(self) -> list[str]:
        return [
            "#########",
            "# . .   #",
            "# $X$   #",
            "#   @ . #",
            "#########",
        ]

    def create_box_from_char(self, char: str, r: int, c: int) -> Box | None:
        if char in "$*":
            return self._make_box(r, c)
        if char == "X":
            return self._make_box(r, c, kind="heavy")
        return None

    def _make_box(self, r: int, c: int, kind: str = "normal") -> Box:
        box = super()._make_box(r, c, kind=kind)
        if kind == "heavy":
            box.color = random.choice([(112, 116, 132), (124, 128, 148), (96, 102, 118)])
        return box

    def get_push_chain_limit(self) -> int:
        return self.grid_w * self.grid_h

    def can_push_box(self, box: Box, chain_len: int) -> bool:
        return box.kind != "heavy" or chain_len > 1

    def choose_random_box_kinds(self, box_count: int) -> list[str]:
        kinds = ["heavy"] + ["normal"] * (box_count - 1)
        random.shuffle(kinds)
        return kinds

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. Variant rule: you can push whole lines of touching boxes, and gray heavy boxes only move when they are part of a multi-box push. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(HeavyMultiPushSokoban)
