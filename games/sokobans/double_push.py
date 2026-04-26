from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import BoxMove, MovePlan, SokobanBase


class DoublePushSokoban(SokobanBase):
    name = "Double Push Sokoban"

    def plan_box_push(self, chain: list, dr: int, dc: int) -> MovePlan | None:
        if len(chain) != 1:
            return None
        box = chain[0]
        target_r = box.r
        target_c = box.c
        for _ in range(2):
            next_r = target_r + dr
            next_c = target_c + dc
            if not self._is_empty_cell(next_r, next_c):
                break
            target_r = next_r
            target_c = next_c
        if (target_r, target_c) == (box.r, box.c):
            return None
        return MovePlan(player_to=(box.r, box.c), box_moves=[BoxMove(box, target_r, target_c)], removed_walls=[])

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. Variant rule: a pushed box tries to move two cells forward and stops early only if a wall or another box blocks the second step. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(DoublePushSokoban)
