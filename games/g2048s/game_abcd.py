from __future__ import annotations
import os,sys,math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.g2048 import Game2048,Tile
def number_to_letter(n: int) -> str:
    return chr(ord('A') + int(math.log2(n))-1)
    
class LetterTile(Tile):
    def draw(self,*args,**kwargs) -> None:
        value=self.value
        self.value=number_to_letter(self.value)
        super().draw(*args,**kwargs)
        self.value=value

class GameABCD(Game2048):
    name = "ABCD"
    def _make_tile(self, value, r: int, c: int) -> Tile:
        return LetterTile(value, r, c)
    def getPrompt(self) -> str:
        return f"This is {self.name}. Use W/A/S/D or Arrow keys to slide all tiles in one direction. When two tiles with the same letter collide, they merge into one tile with the next letter. After each valid move, a new tile appears in an empty cell. The game ends when there are no valid moves left. Reach the {number_to_letter(self.target_tile)} tile to win!"
        
if __name__ == "__main__":
    print(GameABCD().getPrompt())
    from pygameRunner import run_human_debug
    run_human_debug(GameABCD)
