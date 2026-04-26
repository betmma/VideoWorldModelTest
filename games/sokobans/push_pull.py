from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import SokobanBase


class PushPullSokoban(SokobanBase):
    name = "Push Pull Sokoban"

    def allows_pull(self) -> bool:
        return True

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. Variant rule: you can both push a box by walking into it and pull a box by stepping away while it is directly behind you. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(PushPullSokoban)
