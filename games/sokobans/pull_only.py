from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.sokoban import SokobanBase


class PullOnlySokoban(SokobanBase):
    name = "Pull Sokoban"

    def allows_push(self) -> bool:
        return False

    def allows_pull(self) -> bool:
        return True

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. Boxes cannot be pushed. A box moves only when you step away from it while it is directly behind you, so you pull it into your previous cell. Place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay

    run_autoplay(PullOnlySokoban)
