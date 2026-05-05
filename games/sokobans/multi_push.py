from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import SokobanBase


class MultiPushSokoban(SokobanBase):
    name = "Multi Push Sokoban"

    def get_push_chain_limit(self) -> int:
        return self.grid_w * self.grid_h

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. If there is free space in front of the line, you can push a whole line of touching boxes at once. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(MultiPushSokoban)
