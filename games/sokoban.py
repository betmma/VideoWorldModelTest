from __future__ import annotations

import math
import os
import random
import sys
from collections import deque
from dataclasses import dataclass

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


@dataclass
class Box:
    id: int
    r: int
    c: int
    color: tuple[int, int, int]
    kind: str = "normal"


@dataclass
class BoxMove:
    box: Box
    to_r: int
    to_c: int
    remove_after: bool = False


@dataclass
class MovePlan:
    player_to: tuple[int, int]
    box_moves: list[BoxMove]
    removed_walls: list[tuple[int, int]]


@dataclass
class BoxAnimation:
    box: Box
    from_r: int
    from_c: int
    to_r: int
    to_c: int
    color: tuple[int, int, int]
    remove_after: bool = False


@dataclass(frozen=True)
class SearchState:
    player_r: int
    player_c: int
    boxes: tuple[tuple[int, int, str], ...]
    walls: tuple[tuple[int, int], ...]


class SokobanBase(GameBase):
    name = "Sokoban"
    variantsPath = "sokobans"
    moveInterval = 4

    def __init__(self, headless: bool = False) -> None:
        self.tile_size = 54
        self.move_anim_total_frames = 7
        self.end_screen_auto_reset = 150
        self.tip_frames = 220

        self.theme_presets = [
            {
                "bg_top": (26, 34, 48),
                "bg_bottom": (12, 17, 25),
                "panel": (18, 23, 34),
                "panel_text": (241, 244, 248),
                "floor_a": (193, 180, 156),
                "floor_b": (179, 167, 145),
                "wall": (94, 103, 122),
                "wall_dark": (57, 64, 78),
                "goal": (102, 218, 182),
                "goal_glow": (148, 255, 223),
                "player": (255, 196, 87),
                "player_dark": (176, 111, 32),
                "crate": [(191, 118, 68), (168, 133, 72), (176, 101, 85)],
            },
            {
                "bg_top": (43, 28, 32),
                "bg_bottom": (18, 11, 14),
                "panel": (32, 19, 23),
                "panel_text": (247, 240, 235),
                "floor_a": (206, 185, 164),
                "floor_b": (189, 170, 151),
                "wall": (124, 85, 74),
                "wall_dark": (82, 51, 43),
                "goal": (255, 155, 112),
                "goal_glow": (255, 199, 160),
                "player": (105, 192, 241),
                "player_dark": (45, 111, 156),
                "crate": [(177, 112, 65), (151, 114, 83), (198, 136, 92)],
            },
            {
                "bg_top": (24, 42, 31),
                "bg_bottom": (9, 18, 13),
                "panel": (15, 28, 19),
                "panel_text": (239, 246, 240),
                "floor_a": (191, 184, 163),
                "floor_b": (176, 170, 149),
                "wall": (92, 117, 82),
                "wall_dark": (56, 74, 48),
                "goal": (247, 222, 92),
                "goal_glow": (255, 241, 162),
                "player": (240, 119, 119),
                "player_dark": (158, 62, 62),
                "crate": [(162, 111, 63), (139, 98, 74), (184, 125, 74)],
            },
        ]

        super().__init__(headless=headless)
        pygame.font.init()
        self.title_font = pygame.font.SysFont("consolas", 40, bold=True)
        self.hud_font = pygame.font.SysFont("consolas", 22, bold=True)
        self.body_font = pygame.font.SysFont("consolas", 22)
        self.small_font = pygame.font.SysFont("consolas", 18)
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

    def reset(self) -> None:
        self.frame_index = 0
        self.tip_timer = self.tip_frames
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.win = False
        self.steps_taken = 0

        self.theme = random.choice(self.theme_presets)
        self.background_surface = self._render_background_surface()

        self.grid_w = 0
        self.grid_h = 0
        self.walls: set[tuple[int, int]] = set()
        self.goals: set[tuple[int, int]] = set()
        self.boxes: list[Box] = []
        self.box_map: dict[tuple[int, int], Box] = {}
        self._next_box_id = 1

        self.player_r = 1
        self.player_c = 1
        self.player_display_r = 1.0
        self.player_display_c = 1.0
        self.player_anim_from = (1, 1)
        self.last_move_dr = 0
        self.last_move_dc = 1

        self.animating = False
        self.anim_frame = 0
        self.box_animations: list[BoxAnimation] = []
        self.wall_break_animations: list[tuple[int, int]] = []
        self.auto_actions: list[str] = []
        self.auto_wait_frames = 0
        self.auto_restart_wait_steps = -1
        self.prev_action = self.BLANK_ACTION.copy()

        if not self._try_load_random_level():
            self.load_from_map(self.get_default_level_map())
            self.auto_actions = self._flatten_action_segments(self._solve_push_plan())

    def get_default_level_map(self) -> list[str]:
        return [
            "#########",
            "# . #   #",
            "# $ #   #",
            "#   ### #",
            "#   $ . #",
            "#   @   #",
            "#########",
        ]

    def load_from_map(self, level_map: list[str]) -> None:
        self.grid_h = len(level_map)
        self.grid_w = len(level_map[0])
        self.walls.clear()
        self.goals.clear()
        self.boxes.clear()
        self.box_map.clear()
        self._next_box_id = 1

        for r, row in enumerate(level_map):
            for c, char in enumerate(row):
                if char == "#":
                    self.walls.add((r, c))
                if char in ".+*":
                    self.goals.add((r, c))
                if char in "@+":
                    self.player_r = r
                    self.player_c = c
                box = self.create_box_from_char(char, r, c)
                if box is not None:
                    self.boxes.append(box)
                    self.box_map[(box.r, box.c)] = box

        self.player_display_r = self.player_r
        self.player_display_c = self.player_c
        self.player_anim_from = (self.player_r, self.player_c)

    def load_from_layout(
        self,
        grid_h: int,
        grid_w: int,
        walls: set[tuple[int, int]],
        goals: set[tuple[int, int]],
        player: tuple[int, int],
        box_specs: list[tuple[int, int, str]],
    ) -> None:
        self.grid_h = grid_h
        self.grid_w = grid_w
        self.walls = walls.copy()
        self.goals = goals.copy()
        self.boxes = []
        self.box_map = {}
        self._next_box_id = 1
        self.player_r, self.player_c = player

        for r, c, kind in box_specs:
            box = self._make_box(r, c, kind=kind)
            self.boxes.append(box)
            self.box_map[(r, c)] = box

        self.player_display_r = self.player_r
        self.player_display_c = self.player_c
        self.player_anim_from = (self.player_r, self.player_c)

    def create_box_from_char(self, char: str, r: int, c: int) -> Box | None:
        if char not in "$*":
            return None
        return self._make_box(r, c)

    def _make_box(self, r: int, c: int, kind: str = "normal") -> Box:
        box = Box(
            id=self._next_box_id,
            r=r,
            c=c,
            color=random.choice(self.theme["crate"]),
            kind=kind,
        )
        self._next_box_id += 1
        return box

    def allows_push(self) -> bool:
        return True

    def allows_pull(self) -> bool:
        return False

    def get_push_chain_limit(self) -> int:
        return 1

    def can_push_box(self, box: Box, chain_len: int) -> bool:
        return True

    def plan_box_push(self, chain: list[Box], dr: int, dc: int) -> MovePlan | None:
        if not chain:
            return None
        if len(chain) > self.get_push_chain_limit():
            return None
        for box in chain:
            if not self.can_push_box(box, len(chain)):
                return None

        front_box = chain[-1]
        target_r = front_box.r + dr
        target_c = front_box.c + dc
        if not self._is_empty_cell(target_r, target_c):
            return None

        box_moves: list[BoxMove] = []
        for box in reversed(chain):
            box_moves.append(BoxMove(box, box.r + dr, box.c + dc))
        return MovePlan(
            player_to=(self.player_r + dr, self.player_c + dc),
            box_moves=box_moves,
            removed_walls=[],
        )

    def check_win_condition(self) -> bool:
        return len(self.boxes) != 0 and all((box.r, box.c) in self.goals for box in self.boxes)

    def choose_random_box_kinds(self, box_count: int) -> list[str]:
        return ["normal"] * box_count

    def _render_background_surface(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height))
        top = self.theme["bg_top"]
        bottom = self.theme["bg_bottom"]
        for y in range(self.height):
            t = y / (self.height - 1)
            color = (
                int(top[0] * (1.0 - t) + bottom[0] * t),
                int(top[1] * (1.0 - t) + bottom[1] * t),
                int(top[2] * (1.0 - t) + bottom[2] * t),
            )
            pygame.draw.line(surface, color, (0, y), (self.width, y))

        haze = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for _ in range(10):
            radius = random.randint(60, 150)
            alpha = random.randint(12, 24)
            color = (255, 255, 255, alpha)
            x = random.randint(-20, self.width + 20)
            y = random.randint(-20, self.height + 20)
            pygame.draw.circle(haze, color, (x, y), radius)
        surface.blit(haze, (0, 0))
        return surface

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.grid_h and 0 <= c < self.grid_w

    def _is_wall(self, r: int, c: int) -> bool:
        return not self._in_bounds(r, c) or (r, c) in self.walls

    def _box_at(self, r: int, c: int) -> Box | None:
        return self.box_map.get((r, c))

    def _is_empty_cell(self, r: int, c: int) -> bool:
        return not self._is_wall(r, c) and self._box_at(r, c) is None

    def _box_chain(self, start_r: int, start_c: int, dr: int, dc: int) -> list[Box]:
        chain: list[Box] = []
        r, c = start_r, start_c
        while True:
            box = self._box_at(r, c)
            if box is None:
                break
            chain.append(box)
            r += dr
            c += dc
        return chain

    def _logic_snapshot(
        self,
    ) -> tuple[int, int, set[tuple[int, int]], list[Box], dict[tuple[int, int], Box], int]:
        return (
            self.player_r,
            self.player_c,
            self.walls,
            self.boxes,
            self.box_map,
            self._next_box_id,
        )

    def _restore_logic_snapshot(
        self,
        snapshot: tuple[int, int, set[tuple[int, int]], list[Box], dict[tuple[int, int], Box], int],
    ) -> None:
        self.player_r, self.player_c, self.walls, self.boxes, self.box_map, self._next_box_id = snapshot

    def _load_search_state(self, state: SearchState) -> None:
        self.player_r = state.player_r
        self.player_c = state.player_c
        self.walls = set(state.walls)
        self.boxes = []
        self.box_map = {}
        self._next_box_id = 1

        for box_id, (r, c, kind) in enumerate(state.boxes, start=1):
            box = Box(id=box_id, r=r, c=c, color=(0, 0, 0), kind=kind)
            self.boxes.append(box)
            self.box_map[(r, c)] = box
            self._next_box_id = box_id + 1

    def _capture_search_state(self) -> SearchState:
        return SearchState(
            player_r=self.player_r,
            player_c=self.player_c,
            boxes=tuple(sorted((box.r, box.c, box.kind) for box in self.boxes)),
            walls=tuple(sorted(self.walls)),
        )

    def _run_in_search_state(self, state: SearchState, callback):
        snapshot = self._logic_snapshot()
        self._load_search_state(state)
        try:
            return callback()
        finally:
            self._restore_logic_snapshot(snapshot)

    def _direction_specs(self) -> tuple[tuple[str, int, int], ...]:
        return (("W", -1, 0), ("S", 1, 0), ("A", 0, -1), ("D", 0, 1))

    def _action_from_key(self, key: str) -> ActionState:
        action = self.BLANK_ACTION.copy()
        action[key] = True
        return action

    def _apply_loaded_plan(self, plan: MovePlan) -> None:
        self.player_r, self.player_c = plan.player_to

        for move in plan.box_moves:
            self.box_map.pop((move.box.r, move.box.c), None)

        removed_boxes: set[int] = set()
        for move in plan.box_moves:
            if move.remove_after:
                removed_boxes.add(move.box.id)
                continue
            move.box.r = move.to_r
            move.box.c = move.to_c
            self.box_map[(move.box.r, move.box.c)] = move.box

        for wall in plan.removed_walls:
            self.walls.discard(wall)

        if removed_boxes:
            self.boxes = [box for box in self.boxes if box.id not in removed_boxes]

    def _collect_box_move_edges(self, state: SearchState) -> list[tuple[SearchState, tuple[str, ...]]]:
        def worker() -> list[tuple[SearchState, tuple[str, ...]]]:
            base_state = self._capture_search_state()
            queue = deque([(base_state, ())])
            visited = {base_state}
            edge_actions: dict[SearchState, tuple[str, ...]] = {}

            while queue:
                walk_state, walk_actions = queue.popleft()
                for action_key, dr, dc in self._direction_specs():
                    self._load_search_state(walk_state)
                    plan = self._plan_move(dr, dc)
                    if plan is None:
                        continue
                    self._apply_loaded_plan(plan)
                    next_state = self._capture_search_state()
                    next_actions = walk_actions + (action_key,)
                    if plan.box_moves or plan.removed_walls:
                        edge_actions.setdefault(next_state, next_actions)
                    elif next_state not in visited:
                        visited.add(next_state)
                        queue.append((next_state, next_actions))

            return list(edge_actions.items())

        return self._run_in_search_state(state, worker)

    def _state_is_win(self, state: SearchState) -> bool:
        return self._run_in_search_state(state, self.check_win_condition)

    def _reconstruct_segments(
        self,
        parents: dict[SearchState, tuple[SearchState | None, tuple[str, ...]]],
        target: SearchState,
    ) -> list[tuple[str, ...]]:
        segments: list[tuple[str, ...]] = []
        cursor = target
        while True:
            prev_state, segment = parents[cursor]
            if prev_state is None:
                segments.reverse()
                return segments
            segments.append(segment)
            cursor = prev_state

    def _solve_push_plan(self, max_states: int = 2400) -> list[tuple[str, ...]] | None:
        start_state = self._capture_search_state()
        if self._state_is_win(start_state):
            return []

        parents: dict[SearchState, tuple[SearchState | None, tuple[str, ...]]] = {
            start_state: (None, ())
        }
        queue = deque([start_state])

        while queue and len(parents) <= max_states:
            state = queue.popleft()
            for next_state, actions in self._collect_box_move_edges(state):
                if next_state in parents:
                    continue
                parents[next_state] = (state, actions)
                if self._state_is_win(next_state):
                    return self._reconstruct_segments(parents, next_state)
                queue.append(next_state)

        return None

    def _flatten_action_segments(self, segments: list[tuple[str, ...]]) -> list[str]:
        actions: list[str] = []
        for segment in segments:
            actions.extend(segment)
        return actions

    def _build_random_layout(
        self,
    ) -> tuple[int, int, set[tuple[int, int]], tuple[int, int], list[tuple[int, int, str]]]:
        grid_h = random.randint(6, 8)
        grid_w = random.randint(7, 10)
        interior_count = (grid_h - 2) * (grid_w - 2)
        target_floor_count = random.randint(interior_count // 3, interior_count * 13 // 20)

        walker = (random.randint(1, grid_h - 2), random.randint(1, grid_w - 2))
        floors = {walker}
        while len(floors) < target_floor_count:
            dr, dc = random.choice([(dr, dc) for _, dr, dc in self._direction_specs() if 1 <= walker[0] + dr < grid_h - 1 and 1 <= walker[1] + dc < grid_w - 1])
            nr = walker[0] + dr
            nc = walker[1] + dc
            walker = (nr, nc)
            floors.add(walker)
            if random.random() < 0.18:
                side_r, side_c = random.choice([(rr, cc) for rr in range(nr - 1, nr + 2) for cc in range(nc - 1, nc + 2) if 1 <= rr < grid_h - 1 and 1 <= cc < grid_w - 1])
                floors.add((side_r, side_c))

        empty_cells = list(floors)
        open_cells = [(r, c) for r, c in empty_cells[1:] if ((r-1,c) in floors) + ((r+1,c) in floors) + ((r,c-1) in floors) + ((r,c+1) in floors) >= 3]
        random.shuffle(empty_cells)
        box_count = 3
        player = empty_cells[0]
        box_cells = open_cells[:box_count]
        if len(open_cells) < box_count:
            for cell in empty_cells[1:]:
                if cell not in box_cells:
                    box_cells.append(cell)
                if len(box_cells) >= box_count:
                    break
        box_kinds = self.choose_random_box_kinds(box_count)
        box_specs = [(r, c, kind) for (r, c), kind in zip(box_cells, box_kinds)]

        walls = {
            (r, c)
            for r in range(grid_h)
            for c in range(grid_w)
            if r in (0, grid_h - 1) or c in (0, grid_w - 1) or (r, c) not in floors
        }
        return grid_h, grid_w, walls, player, box_specs

    def _build_goal_path(self, max_states: int = 24000) -> tuple[set[tuple[int, int]], list[tuple[str, ...]]] | None:
        start_state = self._capture_search_state()
        parents: dict[SearchState, tuple[SearchState | None, tuple[str, ...]]] = {
            start_state: (None, ())
        }
        depths = {start_state: 0}
        queue = deque([start_state])
        candidates: list[SearchState] = []
        seen_boxes={start_state.boxes}
        while queue and len(parents) <= max_states:
            state = queue.popleft()
            next_depth = depths[state] + 1
            for next_state, actions in self._collect_box_move_edges(state):
                if next_state in parents:
                    continue
                parents[next_state] = (state, actions)
                depths[next_state] = next_depth
                if next_state.boxes and next_state.boxes not in seen_boxes:
                    candidates.append(next_state)
                    seen_boxes.add(next_state.boxes)
                queue.append(next_state)

        if not candidates:
            return None

        max_depth = max(depths[state] for state in candidates)
        floor_depth = max_depth - 1
        target = random.choice([state for state in candidates if depths[state] >= floor_depth])
        goals = {(r, c) for r, c, _ in target.boxes}
        return goals, self._reconstruct_segments(parents, target)

    def _try_load_random_level(self) -> bool:
        best_layout = None
        best_goals = None
        best_plan = None
        best_push_count = -1

        for _ in range(140):
            layout = self._build_random_layout()
            grid_h, grid_w, walls, player, box_specs = layout
            self.load_from_layout(grid_h, grid_w, walls, set(), player, box_specs)
            goal_data = self._build_goal_path()
            if goal_data is None:
                continue
            goals, plan = goal_data
            if len(plan) > best_push_count:
                best_layout = layout
                best_goals = goals
                best_plan = plan
                best_push_count = len(plan)
            if len(plan) >= 2:
                self.goals = goals.copy()
                self.auto_actions = self._flatten_action_segments(plan)
                return True

        if best_layout is None or best_goals is None or best_plan is None:
            return False

        grid_h, grid_w, walls, player, box_specs = best_layout
        self.load_from_layout(grid_h, grid_w, walls, best_goals.copy(), player, box_specs)
        self.auto_actions = self._flatten_action_segments(best_plan)
        return True

    def _plan_move(self, dr: int, dc: int) -> MovePlan | None:
        front_r = self.player_r + dr
        front_c = self.player_c + dc
        if self._is_wall(front_r, front_c):
            return None

        front_box = self._box_at(front_r, front_c)
        if front_box is None:
            if not self._is_empty_cell(front_r, front_c):
                return None
            plan = MovePlan(player_to=(front_r, front_c), box_moves=[], removed_walls=[])
        else:
            if not self.allows_push():
                return None
            chain = self._box_chain(front_r, front_c, dr, dc)
            plan = self.plan_box_push(chain, dr, dc)
            if plan is None:
                return None

        return self._add_pull_to_plan(plan, dr, dc)

    def _add_pull_to_plan(self, plan: MovePlan, dr: int, dc: int) -> MovePlan:
        if not self.allows_pull():
            return plan

        old_r, old_c = self.player_r, self.player_c
        back_r, back_c = old_r - dr, old_c - dc
        box = self._box_at(back_r, back_c)
        if box is None:
            return plan
        if any(move.box is box for move in plan.box_moves):
            return plan
        if any((move.to_r, move.to_c) == (old_r, old_c) for move in plan.box_moves):
            return plan

        plan.box_moves.append(BoxMove(box, old_r, old_c))
        return plan

    def try_move(self, dr: int, dc: int) -> bool:
        if self.animating or self.win:
            return False

        self.last_move_dr = dr
        self.last_move_dc = dc
        plan = self._plan_move(dr, dc)
        if plan is None:
            return False

        self._apply_move_plan(plan)
        return True

    def _apply_move_plan(self, plan: MovePlan) -> None:
        old_player = (self.player_r, self.player_c)
        move_starts = [(move.box, move.box.r, move.box.c, move.to_r, move.to_c, move.box.color, move.remove_after) for move in plan.box_moves]
        self.player_anim_from = old_player
        self.player_display_r = old_player[0]
        self.player_display_c = old_player[1]
        self.steps_taken += 1

        self.animating = True
        self.anim_frame = 0
        self.box_animations = []
        self.wall_break_animations = plan.removed_walls.copy()
        self._apply_loaded_plan(plan)

        for box, from_r, from_c, to_r, to_c, color, remove_after in move_starts:
            self.box_animations.append(
                BoxAnimation(
                    box=box,
                    from_r=from_r,
                    from_c=from_c,
                    to_r=to_r,
                    to_c=to_c,
                    color=color,
                    remove_after=remove_after,
                )
            )

    def update(self, action: ActionState) -> bool:
        self.frame_index += 1
        if self.tip_timer > 0:
            self.tip_timer -= 1

        pressed_action = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action.get(key, False):
                pressed_action[key] = True
        self.prev_action = action.copy()

        if self.animating:
            self.anim_frame += 1
            t = self._anim_progress()
            self.player_display_r = self.player_anim_from[0] + (self.player_r - self.player_anim_from[0]) * t
            self.player_display_c = self.player_anim_from[1] + (self.player_c - self.player_anim_from[1]) * t
            if self.anim_frame >= self.move_anim_total_frames:
                self.animating = False
                self.player_display_r = self.player_r
                self.player_display_c = self.player_c
                self.box_animations = []
                self.wall_break_animations = []
                if self.check_win_condition() and not self.win:
                    self.win = True
                    self.end_reported = True
                    self.end_event_pending = True

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.win and not self.animating:
            self.end_screen_frames += 1
            if pressed_action["A"] or pressed_action["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False

        if not self.animating:
            dr, dc = 0, 0
            if action["W"] or action["LU"]:
                dr = -1
            elif action["S"] or action["LD"]:
                dr = 1
            elif action["A"] or action["LL"]:
                dc = -1
            elif action["D"] or action["LR"]:
                dc = 1

            if dr != 0 or dc != 0:
                self.try_move(dr, dc)

        return False

    def _anim_progress(self) -> float:
        if not self.animating:
            return 1.0
        t = self.anim_frame / self.move_anim_total_frames
        return 1.0 - (1.0 - t) * (1.0 - t)

    def get_draw_info(self) -> tuple[int, int, int]:
        tile_size = self.tile_size
        board_w = self.grid_w * tile_size
        board_h = self.grid_h * tile_size
        max_w = self.width - 48
        max_h = self.height - 92
        if board_w > max_w or board_h > max_h:
            tile_size = max_w // self.grid_w if max_w // self.grid_w < max_h // self.grid_h else max_h // self.grid_h
            board_w = self.grid_w * tile_size
            board_h = self.grid_h * tile_size
        offset_x = (self.width - board_w) // 2
        offset_y = (self.height - board_h) // 2 + 18
        return tile_size, offset_x, offset_y

    def _draw_goal(self, x: int, y: int, size: int, pulse: float) -> None:
        cx = x + size // 2
        cy = y + size // 2
        glow_radius = int(size * 0.23 * pulse)
        ring_radius = int(size * 0.16)
        pygame.draw.circle(self.screen, self.theme["goal_glow"], (cx, cy), glow_radius)
        pygame.draw.circle(self.screen, self.theme["goal"], (cx, cy), ring_radius)
        pygame.draw.circle(self.screen, self.theme["floor_a"], (cx, cy), ring_radius // 2)

    def _draw_wall(self, x: int, y: int, size: int) -> None:
        rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(self.screen, self.theme["wall_dark"], rect, border_radius=size // 8)
        inner = rect.inflate(-(size // 10), -(size // 10))
        pygame.draw.rect(self.screen, self.theme["wall"], inner, border_radius=size // 10)
        pygame.draw.line(self.screen, (255, 255, 255), (inner.left + 2, inner.top + 2), (inner.right - 2, inner.top + 2), 1)

    def _draw_break_effect(self, cell: tuple[int, int], tile_size: int, offset_x: int, offset_y: int) -> None:
        progress = self._anim_progress()
        alpha = int(220 * (1.0 - progress))
        if alpha <= 0:
            return
        r, c = cell
        surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
        glow = (255, 232, 170, alpha)
        crack = (255, 245, 215, alpha + 20)
        center = tile_size // 2
        pygame.draw.circle(surface, glow, (center, center), int(tile_size * 0.28))
        pygame.draw.line(surface, crack, (center, center), (tile_size - 6, 6), 3)
        pygame.draw.line(surface, crack, (center, center), (6, tile_size - 6), 3)
        pygame.draw.line(surface, crack, (center, center), (tile_size - 10, tile_size - 8), 2)
        self.screen.blit(surface, (offset_x + c * tile_size, offset_y + r * tile_size))

    def _draw_box(
        self,
        display_r: float,
        display_c: float,
        size: int,
        offset_x: int,
        offset_y: int,
        color: tuple[int, int, int],
        on_goal: bool,
    ) -> None:
        px = offset_x + display_c * size
        py = offset_y + display_r * size
        shadow_rect = pygame.Rect(int(px + size * 0.12), int(py + size * 0.14), int(size * 0.72), int(size * 0.72))
        pygame.draw.ellipse(self.screen, (0, 0, 0, 60), shadow_rect)

        rect = pygame.Rect(int(px + size * 0.14), int(py + size * 0.12), int(size * 0.72), int(size * 0.72))
        dark = tuple(channel - 42 for channel in color)
        light = tuple(channel + 28 for channel in color)
        pygame.draw.rect(self.screen, dark, rect, border_radius=size // 10)
        inner = rect.inflate(-(size // 8), -(size // 8))
        pygame.draw.rect(self.screen, color, inner, border_radius=size // 12)
        pygame.draw.line(self.screen, light, (inner.left + 3, inner.top + 3), (inner.right - 3, inner.top + 3), 2)
        pygame.draw.line(self.screen, light, (inner.left + 3, inner.top + 3), (inner.left + 3, inner.bottom - 3), 2)
        band = pygame.Rect(inner.centerx - size // 16, inner.top + 4, size // 8, inner.height - 8)
        pygame.draw.rect(self.screen, dark, band, border_radius=3)
        pygame.draw.line(self.screen, dark, (inner.left + 4, inner.centery), (inner.right - 4, inner.centery), 2)
        if on_goal:
            pygame.draw.rect(self.screen, self.theme["goal"], inner.inflate(4, 4), 3, border_radius=size // 10)

    def _draw_player(self, size: int, offset_x: int, offset_y: int) -> None:
        px = offset_x + self.player_display_c * size
        py = offset_y + self.player_display_r * size
        cx = int(px + size / 2)
        cy = int(py + size / 2)
        radius = int(size * 0.28)
        pygame.draw.ellipse(
            self.screen,
            (0, 0, 0, 70),
            pygame.Rect(int(px + size * 0.18), int(py + size * 0.64), int(size * 0.54), int(size * 0.16)),
        )
        pygame.draw.circle(self.screen, self.theme["player_dark"], (cx, cy + 2), radius)
        pygame.draw.circle(self.screen, self.theme["player"], (cx, cy), radius)
        pygame.draw.circle(self.screen, (255, 239, 196), (cx - radius // 3, cy - radius // 3), radius // 4)

        facing_x = self.last_move_dc
        facing_y = self.last_move_dr
        visor_center = (
            int(cx + facing_x * radius * 0.38),
            int(cy + facing_y * radius * 0.38),
        )
        pygame.draw.circle(self.screen, (36, 42, 52), visor_center, radius // 3)
        pygame.draw.circle(self.screen, (247, 250, 252), (visor_center[0] - 1, visor_center[1] - 1), radius // 7)

    def draw(self) -> None:
        self.screen.blit(self.background_surface, (0, 0))
        tile_size, offset_x, offset_y = self.get_draw_info()
        board_w = self.grid_w * tile_size
        board_h = self.grid_h * tile_size
        panel = pygame.Rect(offset_x - 12, offset_y - 12, board_w + 24, board_h + 24)
        pygame.draw.rect(self.screen, self.theme["panel"], panel, border_radius=18)

        for r in range(self.grid_h):
            for c in range(self.grid_w):
                x = offset_x + c * tile_size
                y = offset_y + r * tile_size
                base_color = self.theme["floor_a"] if (r + c) % 2 == 0 else self.theme["floor_b"]
                pygame.draw.rect(self.screen, base_color, pygame.Rect(x, y, tile_size, tile_size))
                if (r, c) in self.walls:
                    self._draw_wall(x, y, tile_size)
                if (r, c) in self.goals:
                    pulse = 0.92 + 0.12 * (1.0 + math.sin(self.frame_index * 0.12 + r * 0.7 + c * 0.4))
                    self._draw_goal(x, y, tile_size, pulse)

        for cell in self.wall_break_animations:
            self._draw_break_effect(cell, tile_size, offset_x, offset_y)

        anim_lookup = {anim.box.id: anim for anim in self.box_animations if not anim.remove_after}
        for box in self.boxes:
            anim = anim_lookup.get(box.id)
            if anim is None:
                display_r = box.r
                display_c = box.c
            else:
                t = self._anim_progress()
                display_r = anim.from_r + (anim.to_r - anim.from_r) * t
                display_c = anim.from_c + (anim.to_c - anim.from_c) * t
            self._draw_box(display_r, display_c, tile_size, offset_x, offset_y, box.color, (box.r, box.c) in self.goals)

        for anim in self.box_animations:
            if not anim.remove_after:
                continue
            t = self._anim_progress()
            display_r = anim.from_r + (anim.to_r - anim.from_r) * t
            display_c = anim.from_c + (anim.to_c - anim.from_c) * t
            self._draw_box(display_r, display_c, tile_size, offset_x, offset_y, anim.color, False)

        self._draw_player(tile_size, offset_x, offset_y)

        matched = sum(1 for box in self.boxes if (box.r, box.c) in self.goals)
        remaining = len(self.boxes) - matched
        hud = pygame.Rect(0, 0, self.width, 48)
        pygame.draw.rect(self.screen, self.theme["panel"], hud)
        pygame.draw.line(self.screen, (255, 255, 255, 32), (0, 48), (self.width, 48), 1)
        left_text = self.hud_font.render(f"{self.name}   Goals {matched}/{len(self.goals)}", True, self.theme["panel_text"])
        right_text = self.hud_font.render(f"Boxes Left {remaining}   Moves {self.steps_taken}", True, self.theme["panel_text"])
        self.screen.blit(left_text, (14, 12))
        self.screen.blit(right_text, right_text.get_rect(topright=(self.width - 14, 12)))

        if self.win and not self.animating:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 132))
            self.screen.blit(overlay, (0, 0))

            title = self.title_font.render("Warehouse Cleared", True, self.theme["goal_glow"])
            detail = self.body_font.render(
                f"Used {self.steps_taken} moves   Boxes Left {remaining}",
                True,
                (242, 244, 247),
            )
            restart = self.small_font.render(
                "Press A / Left Arrow to restart",
                True,
                (236, 237, 241),
            )
            self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 32)))
            self.screen.blit(detail, detail.get_rect(center=(self.width // 2, self.height // 2 + 6)))
            self.screen.blit(restart, restart.get_rect(center=(self.width // 2, self.height // 2 + 38)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use W/A/S/D or Arrow keys to move the player one tile at a time. "
            "Walls block movement. Push boxes by walking into them, and place every box onto a glowing goal tile to win. After clearing the map, press A or Left Arrow to restart."
        )

    def getAutoAction(self, frame_index: int) -> ActionState:
        action = self.BLANK_ACTION.copy()

        if frame_index % self.moveInterval != 0:
            return action

        if self.win and not self.animating:
            if self.auto_restart_wait_steps < 0:
                self.auto_restart_wait_steps = random.randint(3, 8)
            if self.auto_restart_wait_steps > 0:
                self.auto_restart_wait_steps -= 1
                return action
            self.auto_restart_wait_steps = -1
            action["A"] = True
            return action

        self.auto_restart_wait_steps = -1
        if self.animating or self.auto_wait_frames > 0:
            if self.auto_wait_frames > 0:
                self.auto_wait_frames -= 1
            return action

        if not self.auto_actions:
            return action

        next_key = self.auto_actions.pop(0)
        self.auto_wait_frames = random.randint(0, 2)
        return self._action_from_key(next_key)


if __name__ == "__main__":
    from pygameRunner import run_human_debug, run_autoplay

    run_autoplay(SokobanBase)
