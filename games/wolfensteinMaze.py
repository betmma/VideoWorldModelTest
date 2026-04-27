from __future__ import annotations

import math, os, random, sys, pygame, numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pygameBase import ActionState, GameBase


class WolfensteinMazeBase(GameBase):
    """Raycast maze game with a wrong-way entrance loss and a wall-mounted map at the start."""

    name = "Wolfenstein Maze 3D"
    variantsPath = "wolfensteinMazes"
    width = 960
    height = 540

    def __init__(self, headless: bool = False) -> None:
        """Create fonts, renderer settings, and the first random maze."""
        self.fps = 30
        self.maze_width = 23
        self.maze_height = 15
        self.outdoor_width = 2
        self.player_radius = 0.18
        self.turn_speed = 0.05
        self.forward_speed = 0.085
        self.backward_speed = 0.065
        self.field_of_view = math.pi / 2
        self.camera_plane = math.tan(self.field_of_view / 2)
        self.ray_width = 2
        self.wall_height_scale = self.height
        self.floor_render_width = self.width // 2
        self.end_screen_auto_reset = 140
        self.hud_color = (242, 240, 232)
        self.floor_color = (56, 44, 34)
        self.ceiling_color = (26, 31, 48)
        self.wall_palettes = [((144, 118, 92), (112, 96, 78), (88, 76, 62)), ((118, 132, 138), (94, 108, 114), (76, 84, 96)), ((142, 108, 92), (120, 84, 70), (96, 68, 58))]
        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        self.title_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.hud_font = pygame.font.SysFont("consolas", 18, bold=True)
        self.tip_font = pygame.font.SysFont("consolas", 16)
        self.end_font = pygame.font.SysFont("consolas", 44, bold=True)
        self.poster_font = pygame.font.SysFont("consolas", 20, bold=True)
        self.background_surface = self._build_background_surface()
        self.floor_surface = pygame.Surface((self.floor_render_width, self.height - self.height // 2))
        self.floor_lerp = np.linspace(0.0, 1.0, self.floor_render_width)
        self.prev_action = self.BLANK_ACTION.copy()
        self.reset()

    def reset(self) -> None:
        """Build a fresh maze and reset the player, autoplay, and end-screen state."""
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.finish_state = ""
        self.finish_text = ""
        self.auto_pause_frames = 0
        self.auto_bump_frames = 0
        self.auto_bump_angle = 0.0
        self.auto_route: list[tuple[int, int]] = []
        self.auto_index = 1
        self.auto_finish_side = "exit"
        self.wall_palette = random.choice(self.wall_palettes)
        self.grid, self.entrance_row, self.exit_row = self._generate_maze()
        self.grid_height = len(self.grid)
        self.grid_width = len(self.grid[0])
        self.spawn_cell = (self.entrance_row - 1, 1)
        self.outside_goal_cell = (self.entrance_row, self.outdoor_width - 1)
        self.start_cell = (self.entrance_row, self.outdoor_width + 1)
        self.entrance_cell = (self.entrance_row, self.outdoor_width)
        self.exit_cell = (self.exit_row, self.grid_width - 1)
        self.poster_row = self.entrance_row - 1
        self.poster_col = self.outdoor_width
        self.poster_surface = self._build_poster_surface()
        self.player_x = self.spawn_cell[1] + 0.5
        self.player_y = self.spawn_cell[0] + 0.5
        self.player_angle = 0.0
        self.player_has_entered_maze = False
        self.prev_action = self.BLANK_ACTION.copy()
        self.auto_route, self.auto_finish_side = self._build_auto_route()

    def _build_background_surface(self) -> pygame.Surface:
        """Pre-render the sky and floor backdrop behind the raycast walls."""
        surface = pygame.Surface((self.width, self.height))
        half_height = self.height // 2
        for y in range(half_height):
            mix = y / half_height
            color = (int(self.ceiling_color[0] + 30 * mix), int(self.ceiling_color[1] + 32 * mix), int(self.ceiling_color[2] + 34 * mix))
            pygame.draw.line(surface, color, (0, y), (self.width, y))
        pygame.draw.rect(surface, self.floor_color, pygame.Rect(0, half_height, self.width, self.height - half_height))
        return surface

    def _generate_maze(self) -> tuple[list[list[str]], int, int]:
        """Generate one branchy maze with an outside entrance strip and a winding far exit."""
        width = self.maze_width
        height = self.maze_height
        entrance_row = height // 2
        if entrance_row % 2 == 0:
            entrance_row -= 1
        grid = [["#"] * width for _ in range(height)]
        directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        frontier = []
        frontier_set = set()
        grid[entrance_row][1] = " "
        self._add_frontier_cells(grid, entrance_row, 1, frontier, frontier_set, directions)
        while frontier:
            row, col = frontier.pop(random.randrange(len(frontier)))
            frontier_set.remove((row, col))
            open_neighbors = []
            for delta_row, delta_col in directions:
                next_row = row + delta_row
                next_col = col + delta_col
                if 1 <= next_row < height - 1 and 1 <= next_col < width - 1 and grid[next_row][next_col] == " ":
                    open_neighbors.append((next_row, next_col))
            if not open_neighbors:
                continue
            connect_row, connect_col = random.choice(open_neighbors)
            grid[row][col] = " "
            grid[(row + connect_row) // 2][(col + connect_col) // 2] = " "
            self._add_frontier_cells(grid, row, col, frontier, frontier_set, directions)
        self._add_extra_branches(grid)
        grid[entrance_row][0] = "E"
        exit_row = self._choose_exit_row(grid, entrance_row)
        grid[exit_row][width - 1] = "X"
        full_grid = [["#"] * (width + self.outdoor_width) for _ in range(height)]
        for row in range(height):
            for col in range(width):
                full_grid[row][col + self.outdoor_width] = grid[row][col]
        for row in range(entrance_row - 2, entrance_row + 3):
            for col in range(self.outdoor_width):
                full_grid[row][col] = " "
        return full_grid, entrance_row, exit_row

    def _add_frontier_cells(self, grid: list[list[str]], row: int, col: int, frontier: list[tuple[int, int]], frontier_set: set[tuple[int, int]], directions: list[tuple[int, int]]) -> None:
        """Add unopened maze cells two steps away from one carved cell into the frontier list."""
        for delta_row, delta_col in directions:
            next_row = row + delta_row
            next_col = col + delta_col
            if not (1 <= next_row < len(grid) - 1 and 1 <= next_col < len(grid[0]) - 1):
                continue
            if grid[next_row][next_col] != "#" or (next_row, next_col) in frontier_set:
                continue
            frontier.append((next_row, next_col))
            frontier_set.add((next_row, next_col))

    def _add_extra_branches(self, grid: list[list[str]]) -> None:
        """Open a few extra inner walls so the maze has more branches and loops than a pure tree."""
        candidates = []
        for row in range(1, len(grid) - 1):
            for col in range(1, len(grid[0]) - 1):
                if grid[row][col] != "#":
                    continue
                if row % 2 == 1 and col % 2 == 0 and grid[row][col - 1] == " " and grid[row][col + 1] == " ":
                    candidates.append((row, col))
                if row % 2 == 0 and col % 2 == 1 and grid[row - 1][col] == " " and grid[row + 1][col] == " ":
                    candidates.append((row, col))
        random.shuffle(candidates)
        open_count = max(3, len(candidates) // 24)
        for row, col in candidates[:open_count]:
            grid[row][col] = " "

    def _choose_exit_row(self, grid: list[list[str]], entrance_row: int) -> int:
        """Choose one right-edge exit row whose shortest path is long and not dominated by one straight run."""
        candidates = []
        for row in range(1, len(grid) - 1):
            if grid[row][len(grid[0]) - 2] != " ":
                continue
            path = self._find_path_in_grid(grid, (entrance_row, 1), (row, len(grid[0]) - 2))
            if not path:
                continue
            turn_count, longest_run = self._path_shape(path)
            score = len(path) + turn_count * 6 - longest_run * 5
            candidates.append((score, turn_count, len(path), -longest_run, random.random(), row))
        return max(candidates)[5]

    def _find_path_in_grid(self, grid: list[list[str]], start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        """Find one shortest path on a temporary grid before the full shifted map is built."""
        queue = [start]
        head = 0
        previous = {start: None}
        while head < len(queue):
            row, col = queue[head]
            head += 1
            if (row, col) == goal:
                break
            for next_row, next_col in self._cell_neighbors(row, col):
                if not self._walkable_on_grid(grid, next_row, next_col):
                    continue
                if (next_row, next_col) in previous:
                    continue
                previous[(next_row, next_col)] = (row, col)
                queue.append((next_row, next_col))
        if goal not in previous:
            return []
        path = []
        cell = goal
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return path

    def _path_shape(self, path: list[tuple[int, int]]) -> tuple[int, int]:
        """Return how many turns and how long the longest straight run are for one path."""
        turn_count = 0
        longest_run = 0
        current_run = 0
        previous_direction = None
        for index in range(1, len(path)):
            direction = (path[index][0] - path[index - 1][0], path[index][1] - path[index - 1][1])
            if direction == previous_direction:
                current_run += 1
            else:
                if previous_direction is not None:
                    turn_count += 1
                previous_direction = direction
                current_run = 1
            if current_run > longest_run:
                longest_run = current_run
        return turn_count, longest_run

    def _walkable_on_grid(self, grid: list[list[str]], row: int, col: int, allow_boundary: bool = True) -> bool:
        """Return whether one grid cell can be used for logical pathing."""
        if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
            return False
        cell = grid[row][col]
        if cell == "#":
            return False
        if not allow_boundary and cell in "EX":
            return False
        return True

    def _cell_neighbors(self, row: int, col: int) -> list[tuple[int, int]]:
        """Return four-neighbor grid cells around one location."""
        return [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]

    def _distance_map(self, grid: list[list[str]], start: tuple[int, int]) -> dict[tuple[int, int], int]:
        """Run a simple breadth-first search and return shortest distances from start."""
        queue = [start]
        head = 0
        distances = {start: 0}
        while head < len(queue):
            row, col = queue[head]
            head += 1
            for next_row, next_col in self._cell_neighbors(row, col):
                if not self._walkable_on_grid(grid, next_row, next_col):
                    continue
                if (next_row, next_col) in distances:
                    continue
                distances[(next_row, next_col)] = distances[(row, col)] + 1
                queue.append((next_row, next_col))
        return distances

    def _find_path(self, start: tuple[int, int], goal: tuple[int, int], blocked: set[tuple[int, int]] | None = None, allow_boundary: bool = False) -> list[tuple[int, int]]:
        """Find a shortest path on the current maze while optionally forbidding some cells."""
        queue = [start]
        head = 0
        previous = {start: None}
        while head < len(queue):
            row, col = queue[head]
            head += 1
            if (row, col) == goal:
                break
            for next_row, next_col in self._cell_neighbors(row, col):
                if blocked is not None and (next_row, next_col) in blocked and (next_row, next_col) != goal:
                    continue
                if not self._walkable_on_grid(self.grid, next_row, next_col, allow_boundary=allow_boundary or (next_row, next_col) == goal):
                    continue
                if (next_row, next_col) in previous:
                    continue
                previous[(next_row, next_col)] = (row, col)
                queue.append((next_row, next_col))
        if goal not in previous:
            return [start]
        path = []
        cell = goal
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return path

    def _branch_path(self, pivot: tuple[int, int], blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
        """Pick one branch that leaves a main path, goes partway into it, and stops before boundary exits."""
        queue = [pivot]
        head = 0
        previous = {pivot: None}
        distances = {pivot: 0}
        farthest = pivot
        while head < len(queue):
            row, col = queue[head]
            head += 1
            if distances[(row, col)] > distances[farthest]:
                farthest = (row, col)
            for next_row, next_col in self._cell_neighbors(row, col):
                if (next_row, next_col) in blocked and (next_row, next_col) != pivot:
                    continue
                if not self._walkable_on_grid(self.grid, next_row, next_col, allow_boundary=False):
                    continue
                if (next_row, next_col) in previous:
                    continue
                previous[(next_row, next_col)] = (row, col)
                distances[(next_row, next_col)] = distances[(row, col)] + 1
                queue.append((next_row, next_col))
        if farthest == pivot:
            return []
        path = []
        cell = farthest
        while cell is not None:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        cut_index = random.randint(1, len(path) - 1)
        return path[:cut_index + 1]

    def _apply_detours(self, path: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Insert a few branch detours so autoplay does not simply follow the shortest route."""
        if len(path) < 6:
            return path[:]
        path_set = set(path)
        branch_options = []
        for index in range(2, len(path) - 2):
            branch = self._branch_path(path[index], path_set)
            if branch:
                branch_options.append((index, branch))
        if not branch_options:
            return path[:]
        random.shuffle(branch_options)
        detour_count = 1
        if len(branch_options) > 1 and random.random() < 0.25:
            detour_count = 2
        chosen = sorted(branch_options[:detour_count], key=lambda item: item[0])
        chosen_map = {index: branch for index, branch in chosen}
        route = []
        for index, cell in enumerate(path):
            route.append(cell)
            if index not in chosen_map:
                continue
            branch = chosen_map[index]
            route += branch[1:]
            route += branch[-2::-1]
        return route

    def _build_auto_route(self) -> tuple[list[tuple[int, int]], str]:
        """Choose whether autoplay will eventually leave by the exit or lose by returning to the entrance."""
        if random.random() < 0.33:
            return self._build_entrance_route(), "entrance"
        return self._build_exit_route(), "exit"

    def _build_exit_route(self) -> list[tuple[int, int]]:
        """Build a wandering route that still ends at the proper exit."""
        approach_path = self._find_path(self.spawn_cell, self.start_cell, allow_boundary=True)
        main_path = self._find_path(self.start_cell, self.exit_cell, allow_boundary=True)
        return approach_path + self._apply_detours(main_path)[1:]

    def _build_entrance_route(self) -> list[tuple[int, int]]:
        """Build a route that explores part of the maze and then loses by going back out the entrance."""
        approach_path = self._find_path(self.spawn_cell, self.start_cell, allow_boundary=True)
        exit_path = self._find_path(self.start_cell, self.exit_cell, allow_boundary=True)
        if len(exit_path) < 6:
            return approach_path + [self.outside_goal_cell]
        turn_index = random.randint(len(exit_path) // 4, len(exit_path) // 2)
        outgoing = self._apply_detours(exit_path[:turn_index + 1])
        back_path = self._find_path(outgoing[-1], self.outside_goal_cell, allow_boundary=True)
        return approach_path + outgoing[1:] + back_path[1:]

    def _build_poster_surface(self) -> pygame.Surface:
        """Render a flat 2D maze map that will be projected onto the entrance wall."""
        surface = pygame.Surface((192, 192))
        surface.fill((114, 76, 42))
        paper = pygame.Rect(10, 10, 172, 172)
        pygame.draw.rect(surface, (232, 220, 190), paper)
        pygame.draw.rect(surface, (76, 46, 22), paper, 4)
        cell_size = 6
        map_width = self.grid_width * cell_size
        map_height = self.grid_height * cell_size
        offset_x = paper.x + (paper.width - map_width) // 2
        offset_y = paper.y + 18 + (paper.height - 18 - map_height) // 2
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                rect = pygame.Rect(offset_x + col * cell_size, offset_y + row * cell_size, cell_size, cell_size)
                cell = self.grid[row][col]
                color = (236, 232, 214)
                if cell == "#":
                    color = (44, 54, 62)
                if cell == "E":
                    color = (88, 138, 220)
                if cell == "X":
                    color = (224, 126, 68)
                pygame.draw.rect(surface, color, rect)
        start_center = (offset_x + self.spawn_cell[1] * cell_size + cell_size // 2, offset_y + self.spawn_cell[0] * cell_size + cell_size // 2)
        exit_center = (offset_x + self.exit_cell[1] * cell_size + cell_size // 2, offset_y + self.exit_cell[0] * cell_size + cell_size // 2)
        pygame.draw.circle(surface, (210, 40, 40), start_center, cell_size // 3)
        pygame.draw.circle(surface, (34, 168, 88), exit_center, cell_size // 3)
        label = self.poster_font.render("MAP", True, (64, 46, 28))
        surface.blit(label, label.get_rect(center=(surface.get_width() // 2, 38)))
        return surface

    def _pressed_action(self, action: ActionState) -> ActionState:
        """Convert held input into newly pressed buttons for one frame."""
        pressed = self.BLANK_ACTION.copy()
        for key, value in action.items():
            if value and not self.prev_action[key]:
                pressed[key] = True
        self.prev_action = action.copy()
        return pressed

    def _angle_delta(self, target: float, current: float) -> float:
        """Return the signed smallest angle from current to target."""
        return (target - current + math.pi) % (math.pi * 2) - math.pi

    def _position_hits_wall(self, x: float, y: float) -> bool:
        """Test a circular player body against nearby wall cells."""
        if x - self.player_radius < 0 or y - self.player_radius < 0 or y + self.player_radius > self.grid_height:
            return True
        if x + self.player_radius > self.grid_width and not (self.exit_row <= y <= self.exit_row + 1):
            return True
        start_row = max(0, int(y - self.player_radius) - 1)
        end_row = min(self.grid_height - 1, int(y + self.player_radius) + 1)
        start_col = max(0, int(x - self.player_radius) - 1)
        end_col = min(self.grid_width - 1, int(x + self.player_radius) + 1)
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                if self.grid[row][col] != "#":
                    continue
                nearest_x = min(max(x, col), col + 1)
                nearest_y = min(max(y, row), row + 1)
                delta_x = x - nearest_x
                delta_y = y - nearest_y
                if delta_x * delta_x + delta_y * delta_y < self.player_radius * self.player_radius:
                    return True
        return False

    def _move_player(self, move_amount: float) -> None:
        """Move forward or backward while sliding along walls."""
        next_x = self.player_x + math.cos(self.player_angle) * move_amount
        next_y = self.player_y + math.sin(self.player_angle) * move_amount
        if not self._position_hits_wall(next_x, self.player_y):
            self.player_x = next_x
        if not self._position_hits_wall(self.player_x, next_y):
            self.player_y = next_y

    def update(self, action: ActionState) -> bool:
        """Advance input, movement, ending logic, and restart handling by one frame."""
        self.frame_index += 1
        pressed = self._pressed_action(action)
        if self.end_event_pending:
            self.end_event_pending = False
            return True
        if self.finish_state:
            self.end_screen_frames += 1
            if pressed["A"] or pressed["LL"] or self.end_screen_frames >= self.end_screen_auto_reset:
                self.reset()
            return False
        rotate_left = action["A"] or action["LL"]
        rotate_right = action["D"] or action["LR"]
        if rotate_left and not rotate_right:
            self.player_angle -= self.turn_speed
        if rotate_right and not rotate_left:
            self.player_angle += self.turn_speed
        move_amount = 0.0
        if action["W"] or action["LU"]:
            move_amount += self.forward_speed
        if action["S"] or action["LD"]:
            move_amount -= self.backward_speed
        if move_amount:
            self._move_player(move_amount)
        player_row = int(self.player_y)
        player_col = int(self.player_x)
        cell = self.grid[player_row][player_col]
        if player_col >= self.start_cell[1]:
            self.player_has_entered_maze = True
        if cell == "X":
            self.finish_state = "win"
            self.finish_text = "You escaped through the far exit."
            self.end_reported = True
            self.end_event_pending = True
        if self.player_has_entered_maze and player_col < self.outdoor_width:
            self.finish_state = "lose"
            self.finish_text = "You went back out through the entrance."
            self.end_reported = True
            self.end_event_pending = True
        return False

    def _cast_ray(self, camera_x: float) -> tuple[float, int, int, str, float] | None:
        """Cast one ray and return hit distance, cell, wall face, and wall offset."""
        direction_x = math.cos(self.player_angle)
        direction_y = math.sin(self.player_angle)
        ray_x = direction_x - direction_y * self.camera_plane * camera_x
        ray_y = direction_y + direction_x * self.camera_plane * camera_x
        map_x = int(self.player_x)
        map_y = int(self.player_y)
        delta_dist_x = 1e30 if ray_x == 0 else abs(1 / ray_x)
        delta_dist_y = 1e30 if ray_y == 0 else abs(1 / ray_y)
        if ray_x < 0:
            step_x = -1
            side_dist_x = (self.player_x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1 - self.player_x) * delta_dist_x
        if ray_y < 0:
            step_y = -1
            side_dist_y = (self.player_y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1 - self.player_y) * delta_dist_y
        side = 0
        while True:
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            if not (0 <= map_x < self.grid_width and 0 <= map_y < self.grid_height):
                return None
            if self.grid[map_y][map_x] == "#":
                break
        if side == 0:
            distance = (map_x - self.player_x + (1 - step_x) / 2) / ray_x
            offset = self.player_y + distance * ray_y
            face = "W" if step_x > 0 else "E"
        else:
            distance = (map_y - self.player_y + (1 - step_y) / 2) / ray_y
            offset = self.player_x + distance * ray_x
            face = "N" if step_y > 0 else "S"
        return distance, map_y, map_x, face, offset - math.floor(offset)

    def _poster_u(self, row: int, col: int, face: str, offset: float) -> float | None:
        """Return the horizontal poster coordinate when a ray hits the poster wall."""
        if face != "W":
            return None
        if row != self.poster_row or col != self.poster_col:
            return None
        return offset

    def _wall_color(self, row: int, col: int, face: str, offset: float, distance: float) -> tuple[int, int, int]:
        """Shade one wall column with a small stripe pattern and distance darkening."""
        base = self.wall_palette[(row + col) % len(self.wall_palette)]
        shade = 1 / (1 + distance * 0.18)
        if face in "NS":
            shade *= 0.84
        if int(offset * 8) % 2 == 0:
            shade *= 1.07
        return (int(base[0] * shade), int(base[1] * shade), int(base[2] * shade))

    def _draw_floor_tiles(self) -> None:
        """Render a perspective square-tile floor on the lower half of the screen."""
        half_height = self.height // 2
        floor_height = self.height - half_height
        direction_x = math.cos(self.player_angle)
        direction_y = math.sin(self.player_angle)
        plane_x = -direction_y * self.camera_plane
        plane_y = direction_x * self.camera_plane
        ray0_x = direction_x - plane_x
        ray0_y = direction_y - plane_y
        ray1_x = direction_x + plane_x
        ray1_y = direction_y + plane_y
        pixels = pygame.surfarray.pixels3d(self.floor_surface)
        grout = 0.08
        for row_offset in range(1, floor_height + 1):
            row_distance = half_height / row_offset
            floor_x = self.player_x + row_distance * (ray0_x + (ray1_x - ray0_x) * self.floor_lerp)
            floor_y = self.player_y + row_distance * (ray0_y + (ray1_y - ray0_y) * self.floor_lerp)
            cell_x = np.floor(floor_x).astype(np.int32)
            cell_y = np.floor(floor_y).astype(np.int32)
            frac_x = floor_x - cell_x
            frac_y = floor_y - cell_y
            grout_mask = (frac_x < grout) | (frac_x > 1 - grout) | (frac_y < grout) | (frac_y > 1 - grout)
            parity_mask = ((cell_x + cell_y) & 1) == 0
            shade = 0.22 + 0.78 / (1 + row_distance * 0.14)
            red = np.where(grout_mask, 40, np.where(parity_mask, 132, 92))
            green = np.where(grout_mask, 34, np.where(parity_mask, 108, 72))
            blue = np.where(grout_mask, 28, np.where(parity_mask, 84, 54))
            pixels[:, row_offset - 1, 0] = (red * shade).astype(np.uint8)
            pixels[:, row_offset - 1, 1] = (green * shade).astype(np.uint8)
            pixels[:, row_offset - 1, 2] = (blue * shade).astype(np.uint8)
        del pixels
        scaled_floor = pygame.transform.scale(self.floor_surface, (self.width, floor_height))
        self.screen.blit(scaled_floor, (0, half_height))

    def _draw_world(self) -> None:
        """Render the background and all raycast wall columns."""
        self.screen.blit(self.background_surface, (0, 0))
        self._draw_floor_tiles()
        for screen_x in range(0, self.width, self.ray_width):
            camera_x = 2 * ((screen_x + self.ray_width * 0.5) / self.width) - 1
            hit = self._cast_ray(camera_x)
            if hit is None:
                continue
            distance, row, col, face, offset = hit
            line_height = round(self.wall_height_scale / distance)
            unclipped_top = self.height // 2 - line_height // 2
            unclipped_bottom = unclipped_top + line_height
            top = max(0, unclipped_top)
            bottom = min(self.height, unclipped_bottom)
            draw_height = bottom - top
            if draw_height <= 0:
                continue
            poster_u = self._poster_u(row, col, face, offset)
            if poster_u is not None:
                texture_x = int(poster_u * (self.poster_surface.get_width() - 1))
                texture_top = (top - unclipped_top) * self.poster_surface.get_height() // line_height
                texture_bottom = (bottom - unclipped_top) * self.poster_surface.get_height() // line_height
                column = self.poster_surface.subsurface(pygame.Rect(texture_x, texture_top, 1, texture_bottom - texture_top))
                scaled = pygame.transform.scale(column, (self.ray_width, draw_height))
                self.screen.blit(scaled, (screen_x, top))
                continue
            color = self._wall_color(row, col, face, offset, distance)
            pygame.draw.rect(self.screen, color, pygame.Rect(screen_x, top, self.ray_width, draw_height))
            edge_color = (color[0] // 2, color[1] // 2, color[2] // 2)
            pygame.draw.line(self.screen, edge_color, (screen_x, top), (screen_x, bottom))

    def _draw_hud(self) -> None:
        """Draw a compact title and control strip over the 3D view."""
        panel = pygame.Surface((self.width, 44), pygame.SRCALPHA)
        panel.fill((8, 10, 14, 118))
        self.screen.blit(panel, (0, 0))
        title = self.title_font.render(self.name, True, self.hud_color)
        self.screen.blit(title, (14, 8))
        if self.frame_index < 110:
            note = self.hud_font.render("You start outside, facing the maze map beside the entrance.", True, (250, 224, 154))
            self.screen.blit(note, note.get_rect(center=(self.width // 2, self.height - 26)))

    def _draw_end_screen(self) -> None:
        """Overlay a win or lose message after the player leaves the maze."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        title_text = "You Win" if self.finish_state == "win" else "You Lose"
        title_color = (98, 224, 146) if self.finish_state == "win" else (242, 108, 94)
        title = self.end_font.render(title_text, True, title_color)
        detail = self.hud_font.render(self.finish_text, True, (244, 244, 240))
        restart = self.hud_font.render("Press A or Left Arrow to restart", True, (244, 244, 240))
        self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 34)))
        self.screen.blit(detail, detail.get_rect(center=(self.width // 2, self.height // 2 + 6)))
        self.screen.blit(restart, restart.get_rect(center=(self.width // 2, self.height // 2 + 36)))

    def draw(self) -> None:
        """Render the full 3D scene and overlay UI."""
        self._draw_world()
        self._draw_hud()
        if self.finish_state:
            self._draw_end_screen()

    def getPrompt(self) -> str:
        """Describe controls and win or loss conditions for training and debugging."""
        return "This is a Wolfenstein-style first-person maze. Use A and D to rotate the player. Use W and S to move forward or backward. The player starts outside the maze, facing a 2D map mounted on the outer wall beside the entrance. Reach the far exit opening to win. After entering the maze, going back out through the entrance loses."

    def getAutoAction(self) -> ActionState:
        """Drive a noisy first-person autoplayer that often detours, bumps walls, and sometimes exits the wrong way."""
        action = self.BLANK_ACTION.copy()
        if self.finish_state:
            if random.random() < 0.18:
                action["A"] = True
            return action
        if self.auto_pause_frames > 0:
            self.auto_pause_frames -= 1
            return action
        if not self.auto_route:
            self.auto_route, self.auto_finish_side = self._build_auto_route()
            self.auto_index = 1
        if self.auto_bump_frames > 0:
            angle_error = self._angle_delta(self.auto_bump_angle, self.player_angle)
            if angle_error > 0.08:
                action["D"] = True
            if angle_error < -0.08:
                action["A"] = True
            if abs(angle_error) < 0.34:
                action["W"] = True
            self.auto_bump_frames -= 1
            return action
        current_cell = (int(self.player_y), int(self.player_x))
        while self.auto_index < len(self.auto_route) - 1 and self.auto_route[self.auto_index] == current_cell:
            self.auto_index += 1
        if random.random() < 0.002:
            self.auto_pause_frames = random.randint(1, 5)
            return action
        if self.auto_index >= len(self.auto_route):
            self.auto_index = len(self.auto_route) - 1
        target_row, target_col = self.auto_route[self.auto_index]
        target_x = target_col + 0.5
        target_y = target_row + 0.5
        distance = math.hypot(target_x - self.player_x, target_y - self.player_y)
        if distance < 0.19 and self.auto_index < len(self.auto_route) - 1:
            self.auto_index += 1
            target_row, target_col = self.auto_route[self.auto_index]
            target_x = target_col + 0.5
            target_y = target_row + 0.5
            distance = math.hypot(target_x - self.player_x, target_y - self.player_y)
        if distance < 0.3 and random.random() < 0.004:
            player_row = int(self.player_y)
            player_col = int(self.player_x)
            bump_choices = []
            for delta_row, delta_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                next_row = player_row + delta_row
                next_col = player_col + delta_col
                if 0 <= next_row < self.grid_height and 0 <= next_col < self.grid_width and self.grid[next_row][next_col] == "#":
                    bump_choices.append(math.atan2(delta_row, delta_col))
            if bump_choices:
                self.auto_bump_angle = random.choice(bump_choices)
                self.auto_bump_frames = random.randint(3, 6)
                return action
        desired_angle = math.atan2(target_y - self.player_y, target_x - self.player_x)
        angle_error = self._angle_delta(desired_angle, self.player_angle)
        if angle_error > 0.07:
            action["D"] = True
        if angle_error < -0.07:
            action["A"] = True
        if abs(angle_error) < 0.62:
            action["W"] = True
        if abs(angle_error) > 2.45 and distance < 0.7:
            action["S"] = True
        return action


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_human_debug(WolfensteinMazeBase)
