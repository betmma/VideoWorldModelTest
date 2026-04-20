import os
import sys
import random
import pygame
from abc import ABC, abstractmethod

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase

class Constraint(ABC):
    @abstractmethod
    def get_deductions(self, revealed_state: list[list[bool]], flagged_state: list[list[bool]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Returns (safe_cells, mine_cells) deduced by this single constraint."""
        pass

class SumConstraint(Constraint):
    def __init__(self, area: set[tuple[int, int]], allowed_counts: set[int]):
        self.area = area
        self.allowed_counts = allowed_counts

    def get_deductions(self, revealed_state: list[list[bool]], flagged_state: list[list[bool]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        flags = sum(1 for r, c in self.area if flagged_state[r][c])
        hidden = [(r, c) for r, c in self.area if not revealed_state[r][c] and not flagged_state[r][c]]
        
        if not hidden:
            return [], []
            
        rem_counts = {c - flags for c in self.allowed_counts if 0 <= c - flags <= len(hidden)}
        
        if not rem_counts:
            return [], []
            
        if max(rem_counts) == 0:
            return hidden, []
        elif min(rem_counts) == len(hidden):
            return [], hidden
        return [], []

class LinearConstraint(Constraint):
    def __init__(self, weights: dict[tuple[int, int], int], allowed_values: set[int]):
        self.weights = weights
        self.allowed_values = allowed_values

    def get_deductions(self, revealed_state: list[list[bool]], flagged_state: list[list[bool]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        flag_val = sum(w for (r, c), w in self.weights.items() if flagged_state[r][c])
        hidden_weights = {pos: w for pos, w in self.weights.items() if not revealed_state[pos[0]][pos[1]] and not flagged_state[pos[0]][pos[1]]}
        
        if not hidden_weights:
            return [], []
            
        max_possible = sum(w for w in hidden_weights.values() if w > 0)
        min_possible = sum(w for w in hidden_weights.values() if w < 0)
        
        rem_values = {v - flag_val for v in self.allowed_values}
        
        if all(v == max_possible for v in rem_values):
            safe = [pos for pos, w in hidden_weights.items() if w < 0]
            mines = [pos for pos, w in hidden_weights.items() if w > 0]
            return safe, mines
            
        if all(v == min_possible for v in rem_values):
            safe = [pos for pos, w in hidden_weights.items() if w > 0]
            mines = [pos for pos, w in hidden_weights.items() if w < 0]
            return safe, mines
            
        return [], []

class PatternConstraint(Constraint):
    def __init__(self, ordered_area: list[tuple[int, int]], valid_states: list[tuple[bool, ...]]):
        self.ordered_area = ordered_area
        self.valid_states = valid_states

    def get_deductions(self, revealed_state: list[list[bool]], flagged_state: list[list[bool]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        surviving_states = []
        for state in self.valid_states:
            valid = True
            for i, (r, c) in enumerate(self.ordered_area):
                is_mine = state[i]
                if flagged_state[r][c] and not is_mine:
                    valid = False; break
                if revealed_state[r][c] and is_mine:
                    valid = False; break
            if valid:
                surviving_states.append(state)
                
        if not surviving_states:
            return [], []
            
        safe_cells = []
        mine_cells = []
        
        for i, (r, c) in enumerate(self.ordered_area):
            if revealed_state[r][c] or flagged_state[r][c]:
                continue
                
            all_true = all(state[i] for state in surviving_states)
            all_false = all(not state[i] for state in surviving_states)
            
            if all_true:
                mine_cells.append((r, c))
            elif all_false:
                safe_cells.append((r, c))
                
        return safe_cells, mine_cells

class Cell:
    def __init__(self, r: int, c: int):
        self.r = r
        self.c = c
        self.is_mine = False
        self.clue = 0
        self.revealed = False
        self.flagged = False

class MinesweeperBase(GameBase):
    name = "Minesweeper"
    variantsPath = "minesweepers"
    
    def __init__(self, headless: bool = False) -> None:
        self.tile_size = 40
        self.mine_density = 0.2
        super().__init__(headless=headless)
        self.prev_action = self.BLANK_ACTION.copy()
        
        # UI fonts
        pygame.font.init()
        self.font = pygame.font.SysFont("consolas", 24, bold=True)
        self.large_font = pygame.font.SysFont("consolas", 42, bold=True)
        
        self.colors = {
            1: (0, 0, 255),
            2: (0, 128, 0),
            3: (255, 0, 0),
            4: (0, 0, 128),
            5: (128, 0, 0),
            6: (0, 128, 128),
            7: (0, 0, 0),
            8: (128, 128, 128),
            -1: (200, 130, 0),   # Orange
            -2: (130, 0, 130),   # Purple
            -3: (200, 0, 200),   # Magenta/Fuchsia
            -4: (0, 200, 0),     # Bright Lime
            -5: (200, 200, 0),   # Gold
            -6: (0, 200, 200),   # Cyan
            -7: (50, 200, 100), 
            -8: (50, 50, 50)     # Dark Charcoal
        }
        
        self.reset()

    def reset(self) -> None:
        self.grid: list[list[Cell]] = []
        self.grid_h = 0
        self.grid_w = 0
        self.cursor_r = 0
        self.cursor_c = 0
        self.game_over = False
        self.win = False
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.frame_index = 0
        
        # Auto-agent states
        self.auto_plan: list[str] = []
        self.auto_wait_frames = 0
        
        self._create_level()

    def get_adjacent(self, r: int, c: int) -> list[tuple[int, int]]:
        """Return adjacent coordinates. Overridable by variants."""
        adj = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                    adj.append((nr, nc))
        return adj

    def get_fast_open_adjacent(self, r: int, c: int) -> list[tuple[int, int]]:
        """Return adjacent coordinates for fast open (A key). Overridable."""
        return self.get_adjacent(r, c)

    def _create_level(self) -> None:
        """Procedurally generate a solvable board."""
        max_attempts = 500
        for _ in range(max_attempts):
            w = random.randint(5, 10)
            h = random.randint(5, 10)
            if h > w:
                w, h = h, w
            
            # Subclasses can override generate_board
            if self.generate_board(w, h):
                if self.check_solvable():
                    self.cursor_r = self.grid_h // 2
                    self.cursor_c = self.grid_w // 2
                    return
        
        print("Warning: Could not generate a solvable board without guessing after many attempts.")
        # Just use the last generated board if it fails

    def generate_board(self, w: int, h: int) -> bool:
        """Generate grid and place mines. Returns True if successful."""
        self.grid_w = w
        self.grid_h = h
        self.grid = [[Cell(r, c) for c in range(w)] for r in range(h)]
        
        num_mines = max(1, int(w * h * self.mine_density))
        
        cells = [(r, c) for r in range(h) for c in range(w)]
        mine_cells = random.sample(cells, num_mines)
        for r, c in mine_cells:
            self.grid[r][c].is_mine = True
            
        self.calculate_clues()
        return True

    def calculate_clues(self) -> None:
        """Calculate clues for each cell. Overridable by variants."""
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if self.grid[r][c].is_mine:
                    continue
                clue = 0
                for nr, nc in self.get_adjacent(r, c):
                    if self.grid[nr][nc].is_mine:
                        clue += 1
                self.grid[r][c].clue = clue

    def get_active_constraints(self, revealed_state: list[list[bool]], flagged_state: list[list[bool]]) -> list[Constraint]:
        constraints = []
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if revealed_state[r][c] and not self.is_empty_clue(self.grid[r][c].clue):
                    adj = self.get_adjacent(r, c)
                    constraints.append(SumConstraint(set(adj), {self.grid[r][c].clue}))
        return constraints

    def _get_logic_deductions(self, revealed_state: list[list[bool]], flagged_state: list[list[bool]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        safe_deductions = set()
        mine_deductions = set()
        
        constraints = self.get_active_constraints(revealed_state, flagged_state)
        sum_constraints = []
        
        # 1. Single-constraint deduction
        for const in constraints:
            s, m = const.get_deductions(revealed_state, flagged_state)
            safe_deductions.update(s)
            mine_deductions.update(m)
            if isinstance(const, SumConstraint):
                sum_constraints.append(const)
                
        # 2. Subset deduction for SumConstraints
        if not safe_deductions and not mine_deductions:
            active_sums = []
            for sc in sum_constraints:
                flags = sum(1 for r, c in sc.area if flagged_state[r][c])
                hidden = {pos for pos in sc.area if not revealed_state[pos[0]][pos[1]] and not flagged_state[pos[0]][pos[1]]}
                if hidden:
                    valid_rems = {c - flags for c in sc.allowed_counts if 0 <= c - flags <= len(hidden)}
                    if valid_rems:
                        active_sums.append((hidden, valid_rems))
                    
            for i in range(len(active_sums)):
                h1, rem1 = active_sums[i]
                for j in range(i + 1, len(active_sums)):
                    h2, rem2 = active_sums[j]
                    
                    if not h1.isdisjoint(h2):
                        I = h1 & h2
                        d1 = h1 - h2
                        d2 = h2 - h1
                        
                        valid_k = []
                        for k in range(len(I) + 1):
                            c1_ok = any(0 <= v1 - k <= len(d1) for v1 in rem1)
                            c2_ok = any(0 <= v2 - k <= len(d2) for v2 in rem2)
                            if c1_ok and c2_ok:
                                valid_k.append(k)
                                
                        if not valid_k:
                            continue
                            
                        if max(valid_k) == 0:
                            safe_deductions.update(I)
                        elif min(valid_k) == len(I):
                            mine_deductions.update(I)
                            
                        d1_mines = [v1 - k for k in valid_k for v1 in rem1 if 0 <= v1 - k <= len(d1)]
                        if d1_mines:
                            if max(d1_mines) == 0:
                                safe_deductions.update(d1)
                            elif min(d1_mines) == len(d1):
                                mine_deductions.update(d1)
                                
                        d2_mines = [v2 - k for k in valid_k for v2 in rem2 if 0 <= v2 - k <= len(d2)]
                        if d2_mines:
                            if max(d2_mines) == 0:
                                safe_deductions.update(d2)
                            elif min(d2_mines) == len(d2):
                                mine_deductions.update(d2)
                            
        return list(safe_deductions), list(mine_deductions)

    def check_solvable(self) -> bool:
        """Try to solve the board to ensure no guessing is required."""
        safe_cells = [(r, c) for r in range(self.grid_h) for c in range(self.grid_w) if not self.grid[r][c].is_mine]
        if not safe_cells:
            return False
        
        # Make a deep copy of revealed/flagged states to simulate solving
        revealed_state = [[False for _ in range(self.grid_w)] for _ in range(self.grid_h)]
        flagged_state = [[False for _ in range(self.grid_w)] for _ in range(self.grid_h)]
        
        def count_unrevealed_safe():
            return sum(1 for r, c in safe_cells if not revealed_state[r][c])

        # We allow up to a certain number of initially revealed safe cells
        max_starting_tiles = max(1, len(safe_cells) // 4)
        starting_tiles_used = 0
        
        while count_unrevealed_safe() > 0:
            # Run deduction loop
            changed = True
            while changed:
                changed = False
                safe_deducs, mine_deducs = self._get_logic_deductions(revealed_state, flagged_state)
                if safe_deducs or mine_deducs:
                    changed = True
                    for nr, nc in safe_deducs:
                        if not revealed_state[nr][nc] and not flagged_state[nr][nc]:
                            self._simulate_reveal(nr, nc, revealed_state)
                    for nr, nc in mine_deducs:
                        if not revealed_state[nr][nc] and not flagged_state[nr][nc]:
                            flagged_state[nr][nc] = True

            if count_unrevealed_safe() == 0:
                break
                
            # If stuck, try to add one more starting tile
            if starting_tiles_used < max_starting_tiles:
                unrevealed_safes = [(r, c) for r, c in safe_cells if not revealed_state[r][c]]
                if unrevealed_safes:
                    sr, sc = random.choice(unrevealed_safes)
                    self._simulate_reveal(sr, sc, revealed_state)
                    # Actually apply it to the real grid as an initial tile
                    self.reveal_cell(sr, sc, play_anim=False)
                    starting_tiles_used += 1
                else:
                    break
            else:
                return False # Failed to solve within allowed starting tiles
                
        return True

    def _simulate_reveal(self, r: int, c: int, revealed_state: list[list[bool]]) -> None:
        """Helper for solvability check."""
        queue = [(r, c)]
        revealed_state[r][c] = True
        
        while queue:
            cr, cc = queue.pop(0)
            if self.is_empty_clue(self.grid[cr][cc].clue) and not self.grid[cr][cc].is_mine:
                for nr, nc in self.get_adjacent(cr, cc):
                    if not revealed_state[nr][nc] and not self.grid[nr][nc].is_mine:
                        revealed_state[nr][nc] = True
                        queue.append((nr, nc))

    def is_empty_clue(self, clue) -> bool:
        return clue == 0

    def can_auto_reveal(self, r: int, c: int) -> bool:
        return True

    def can_fast_open(self, r: int, c: int) -> bool:
        return True

    def is_clue_satisfied(self, r: int, c: int) -> bool:
        adj = self.get_fast_open_adjacent(r, c)
        flags = sum(1 for nr, nc in adj if self.grid[nr][nc].flagged)
        return flags == self.grid[r][c].clue

    def format_clue(self, clue) -> str:
        return str(clue)

    def get_clue_font(self, clue):
        return self.font

    def get_clue_color(self, clue):
        return self.colors.get(clue, (0, 0, 0)) if isinstance(clue, int) else (0, 0, 0)

    def reveal_cell(self, r: int, c: int, play_anim: bool = True) -> None:
        if self.grid[r][c].revealed or self.grid[r][c].flagged:
            return
            
        self.grid[r][c].revealed = True
        
        if self.grid[r][c].is_mine:
            self.game_over = True
            return
            
        # Recursive 0 reveal
        if self.is_empty_clue(self.grid[r][c].clue) and self.can_auto_reveal(r, c):
            for nr, nc in self.get_adjacent(r, c):
                if not self.grid[nr][nc].revealed and not self.grid[nr][nc].flagged:
                    self.reveal_cell(nr, nc, play_anim)

    def check_win_condition(self) -> None:
        if self.game_over:
            return
            
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                if not self.grid[r][c].is_mine and not self.grid[r][c].revealed:
                    return
        self.win = True

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1
        
        pressed_action = self.BLANK_ACTION.copy()
        for k, v in action.items():
            if v and not self.prev_action.get(k, False):
                pressed_action[k] = True
        self.prev_action = action.copy()

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.game_over or self.win:
            if not self.end_reported:
                self.end_reported = True
                self.end_event_pending = True
                
            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= 120:
                self.reset()
            return False

        # Movement
        dr, dc = 0, 0
        if pressed_action["LU"]: dr = -1
        elif pressed_action["LD"]: dr = 1
        elif pressed_action["LL"]: dc = -1
        elif pressed_action["LR"]: dc = 1
        
        if dr != 0 or dc != 0:
            nr = self.cursor_r + dr
            nc = self.cursor_c + dc
            if 0 <= nr < self.grid_h and 0 <= nc < self.grid_w:
                self.cursor_r = nr
                self.cursor_c = nc

        # Actions
        target = self.grid[self.cursor_r][self.cursor_c]
        if pressed_action["W"]: # Reveal
            if not target.revealed and not target.flagged:
                self.reveal_cell(self.cursor_r, self.cursor_c)
                self.check_win_condition()
                
        elif pressed_action["S"]: # Flag
            if not target.revealed:
                target.flagged = not target.flagged
                
        elif pressed_action["A"]: # Fast Open
            if target.revealed and not self.is_empty_clue(target.clue) and self.can_fast_open(self.cursor_r, self.cursor_c):
                if self.is_clue_satisfied(self.cursor_r, self.cursor_c):
                    adj = self.get_fast_open_adjacent(self.cursor_r, self.cursor_c)
                    for nr, nc in adj:
                        if not self.grid[nr][nc].revealed and not self.grid[nr][nc].flagged:
                            self.reveal_cell(nr, nc)
                    self.check_win_condition()

        return False

    def draw(self) -> None:
        self.screen.fill((40, 40, 45))
        
        title = self.font.render(f"Minesweeper - {self.name}", True, (200, 200, 200))
        self.screen.blit(title, title.get_rect(midtop=(self.width // 2, 10)))
        
        # Calculate offset and tile size to center board
        board_w = self.grid_w * self.tile_size
        board_h = self.grid_h * self.tile_size
        offset_x = (self.width - board_w) // 2
        offset_y = (self.height - board_h) // 2
        
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                cell = self.grid[r][c]
                x = offset_x + c * self.tile_size
                y = offset_y + r * self.tile_size
                rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
                
                if cell.revealed:
                    pygame.draw.rect(self.screen, (200, 200, 200), rect)
                    pygame.draw.rect(self.screen, (150, 150, 150), rect, 1)
                    
                    if cell.is_mine:
                        # Mine (exploded)
                        pygame.draw.circle(self.screen, (255, 0, 0), rect.center, self.tile_size // 3)
                    elif not self.is_empty_clue(cell.clue):
                        # Number
                        color = self.get_clue_color(cell.clue)
                        txt = self.get_clue_font(cell.clue).render(self.format_clue(cell.clue), True, color)
                        self.screen.blit(txt, txt.get_rect(center=rect.center))
                else:
                    # Unrevealed bevel
                    pygame.draw.rect(self.screen, (180, 180, 180), rect)
                    pygame.draw.polygon(self.screen, (255, 255, 255), [(x, y), (x + self.tile_size, y), (x + self.tile_size - 4, y + 4), (x + 4, y + 4)]) # Top
                    pygame.draw.polygon(self.screen, (255, 255, 255), [(x, y), (x, y + self.tile_size), (x + 4, y + self.tile_size - 4), (x + 4, y + 4)]) # Left
                    pygame.draw.polygon(self.screen, (100, 100, 100), [(x, y + self.tile_size), (x + self.tile_size, y + self.tile_size), (x + self.tile_size - 4, y + self.tile_size - 4), (x + 4, y + self.tile_size - 4)]) # Bottom
                    pygame.draw.polygon(self.screen, (100, 100, 100), [(x + self.tile_size, y), (x + self.tile_size, y + self.tile_size), (x + self.tile_size - 4, y + self.tile_size - 4), (x + self.tile_size - 4, y + 4)]) # Right
                    
                    if cell.flagged:
                        # Flag
                        pygame.draw.polygon(self.screen, (255, 0, 0), [(x + 10, y + 8), (x + 30, y + 15), (x + 10, y + 22)])
                        pygame.draw.line(self.screen, (0, 0, 0), (x + 10, y + 8), (x + 10, y + 32), 2)
                        
                # Cursor
                if r == self.cursor_r and c == self.cursor_c:
                    pygame.draw.rect(self.screen, (255, 255, 0), rect, 3)

        if (self.win or self.game_over) and self.end_screen_frames > 15:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            
            txt_str = "You Win!" if self.win else "Game Over"
            color = (50, 255, 50) if self.win else (255, 50, 50)
            txt = self.large_font.render(txt_str, True, color)
            self.screen.blit(txt, txt.get_rect(center=(self.width // 2, self.height // 2 - 20)))

    def getPrompt(self) -> str:
        return f"This is {self.name}. "+\
            "Use Arrow keys to move the cursor. "+\
            "Press W to reveal a tile. Press S to flag a mine. "+\
            ("Press A to fast open adjacent tiles if the number of flags matches the clue." if self.can_fast_open() else "")+\
            "When game ends, press A or left arrow key to restart."
        

    def deduce_step(self) -> list[tuple[int, int, str]]:
        """
        Analyze the board and deduce certain moves.
        Returns a list of deduced actions: (r, c, "W"|"S"|"A")
        "W" = Reveal, "S" = Flag, "A" = Fast Open
        """
        revealed_state = [[self.grid[r][c].revealed for c in range(self.grid_w)] for r in range(self.grid_h)]
        flagged_state = [[self.grid[r][c].flagged for c in range(self.grid_w)] for r in range(self.grid_h)]
        
        deductions = []
        for r in range(self.grid_h):
            for c in range(self.grid_w):
                cell = self.grid[r][c]
                if cell.revealed and not self.is_empty_clue(cell.clue):
                    if self.can_fast_open(r, c):
                        adj = self.get_fast_open_adjacent(r, c)
                        hidden = sum(1 for nr, nc in adj if not revealed_state[nr][nc] and not flagged_state[nr][nc])
                        if hidden > 0 and self.is_clue_satisfied(r, c):
                            deductions.append((r, c, "A"))
                        
        if deductions:
            return list(set(deductions))
            
        safe_deducs, mine_deducs = self._get_logic_deductions(revealed_state, flagged_state)
        for nr, nc in mine_deducs:
            deductions.append((nr, nc, "S"))
        for nr, nc in safe_deducs:
            deductions.append((nr, nc, "W"))
            
        return list(set(deductions))

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if self.frame_index % self.moveInterval != 0:
            return action

        if self.auto_wait_frames > 0:
            self.auto_wait_frames -= 1
            return action

        if self.game_over or self.win:
            if self.end_screen_frames > 15 and random.random() < 0.2:
                action["A"] = True
            return action

        # 20% chance to recalculate deductions even if we have a plan
        if len(self.auto_plan) == 0 or random.random() < 0.2:
            deduced_moves = self.deduce_step()
            if deduced_moves:
                # Find the closest deduced move
                best_dist = 9999
                best_move = None
                for dr, dc, move_type in deduced_moves:
                    dist = abs(dr - self.cursor_r) + abs(dc - self.cursor_c)
                    if dist < best_dist:
                        best_dist = dist
                        best_move = (dr, dc, move_type)
                
                if best_move:
                    tr, tc, move_type = best_move
                    
                    # Generate path to target
                    new_plan = []
                    curr_r, curr_c = self.cursor_r, self.cursor_c
                    while curr_r < tr:
                        new_plan.append("LD")
                        curr_r += 1
                    while curr_r > tr:
                        new_plan.append("LU")
                        curr_r -= 1
                    while curr_c < tc:
                        new_plan.append("LR")
                        curr_c += 1
                    while curr_c > tc:
                        new_plan.append("LL")
                        curr_c -= 1
                    
                    new_plan.append(move_type)
                    self.auto_plan = new_plan
                    # Wait slightly longer since we did a deduction step
                    self.auto_wait_frames = random.randint(1, 3)
                    return action

        if self.auto_plan:
            move = self.auto_plan.pop(0)
            action[move] = True
            self.auto_wait_frames = random.randint(0, 1)
        else:
            # Fallback: random movement or reveal if completely stuck
            if random.random() < 0.05:
                # Random reveal
                moves = ["W", "LU", "LL", "LD", "LR"]
                action[random.choice(moves)] = True
            else:
                moves = ["LU", "LL", "LD", "LR"]
                action[random.choice(moves)] = True
            self.auto_wait_frames = random.randint(0, 1)

        return action

if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug
    # run_human_debug(MinesweeperBase)
    run_autoplay(MinesweeperBase)
