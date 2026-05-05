from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import BoxMove, MovePlan, SokobanBase


class SwapPushSokoban(SokobanBase):
    name = "Swap Push Sokoban"

    def plan_box_push(self, chain: list, dr: int, dc: int) -> MovePlan | None:
        if len(chain) != 1:
            return None
        box = chain[0]
        return MovePlan(player_to=(box.r, box.c), box_moves=[BoxMove(box, self.player_r, self.player_c)], removed_walls=[])

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. When you push a box, the player moves into the box's cell and the box moves into the player's previous cell. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(SwapPushSokoban)
