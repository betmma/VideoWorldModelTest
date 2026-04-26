from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import BoxMove, MovePlan, SokobanBase


class JumpPushSokoban(SokobanBase):
    name = "Jump Push Sokoban"

    def plan_box_push(self, chain: list, dr: int, dc: int) -> MovePlan | None:
        if len(chain) != 1:
            return None
        box = chain[0]
        target_r = box.r + dr * 2
        target_c = box.c + dc * 2
        if not self._is_empty_cell(target_r, target_c):
            return None
        return MovePlan(player_to=(box.r, box.c), box_moves=[BoxMove(box, target_r, target_c)], removed_walls=[])

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. Variant rule: a pushed box jumps exactly two cells forward, skipping over the middle cell, and the push fails if the landing cell is not empty. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(JumpPushSokoban)
