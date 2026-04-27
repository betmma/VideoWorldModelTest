from __future__ import annotations

import heapq, math, os, random, sys, pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pygameBase, pygameRunner


class Box:
    """Rotated rectangle used for slots, curbs, cars, roads, and footprints."""

    def __init__(self, x, y, length, width, angle, color, kind):
        """Store rectangle geometry, color, and semantic kind."""
        self.x = x
        self.y = y
        self.length = length
        self.width = width
        self.angle = angle
        self.color = color
        self.kind = kind


class CircleObstacle:
    """Circle shape used for islands and circular footprints."""

    def __init__(self, x, y, radius, color, kind):
        """Store circle geometry, color, and semantic kind."""
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.kind = kind


class CarState:
    """Mutable state for the player car."""

    def __init__(self, x, y, angle):
        """Store car pose, speed, and current steering angle."""
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = 0.0
        self.steer = 0.0


class TrafficCar:
    """Simple moving car spawned by a road piece."""

    def __init__(self, x, y, angle, speed, color):
        """Store pose, speed, and body size for one traffic car."""
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = speed
        self.color = color
        self.length = 76
        self.width = 38


class Road:
    """Straight traffic road that periodically spawns moving cars."""

    def __init__(self, x, y, length, width, angle, flow, lane_offset, speed, spawn_min, spawn_max, color):
        """Store road geometry, traffic direction, and spawn tuning."""
        self.x = x
        self.y = y
        self.length = length
        self.draw_length = length
        self.width = width
        self.angle = angle
        self.flow = flow
        self.lane_offset = lane_offset
        self.speed = speed
        self.spawn_min = spawn_min
        self.spawn_max = spawn_max
        self.color = color
        self.cars = []
        self.spawn_timer = 0

    def reset(self) -> None:
        """Clear moving cars and restart the spawn timer."""
        self.cars = []
        self.spawn_timer = random.randint(self.spawn_min, self.spawn_max)


class CarParkingBase(pygameBase.GameBase):
    """Top-down parking game with random maps, moving traffic, and limited lives per map."""

    name = "Car Parking"
    variantsPath = "carParkings"
    width = 900
    height = 540
    moveInterval = 1

    def __init__(self, headless: bool = False) -> None:
        """Set constants, colors, fonts, and build the first random map."""
        self.car_length = 82
        self.car_width = 42
        self.wheel_base = 48
        self.wheel_length = 18
        self.wheel_width = 10
        self.max_steer = 0.72
        self.steer_step = 0.055
        self.steer_return = 0.045
        self.acceleration = 0.22
        self.coasting = 0.9
        self.max_forward_speed = 4.5
        self.max_reverse_speed = 3.0
        self.park_confirm_frames = 12
        self.end_screen_auto_reset = 55
        self.slot_margin = 1
        self.map_lives_max = 3
        self.map_frame_limit = 1000

        self.bg_color = (106, 147, 96)
        self.lot_color = (45, 53, 65)
        self.line_color = (234, 238, 244)
        self.curb_color = (183, 191, 198)
        self.curb_top_color = (214, 219, 225)
        self.player_color = (234, 94, 76)
        self.target_fill = (74, 163, 221)
        self.target_line = (144, 219, 255)
        self.shadow_color = (17, 21, 28, 70)
        self.text_color = (245, 247, 250)
        self.dim_text = (173, 179, 186)
        self.win_color = (98, 225, 157)
        self.fail_color = (244, 121, 102)
        self.road_mark_color = (240, 216, 124)
        self.grass_ring = (131, 168, 110)
        self.parked_car_colors = [(225, 184, 88), (109, 170, 222), (149, 109, 212), (208, 113, 134), (96, 190, 151)]
        self.traffic_colors = [(248, 145, 67), (246, 83, 96), (82, 178, 242), (236, 214, 98)]
        self.road_colors = [(79, 86, 101), (72, 81, 95), (84, 88, 108)]
        self.circle_colors = [(162, 176, 124), (149, 170, 139), (174, 157, 118)]

        super().__init__(headless=headless)
        pygame.display.set_caption(self.name)
        self.title_font = pygame.font.SysFont("consolas", 34, bold=True)
        self.ui_font = pygame.font.SysFont("consolas", 22, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 18)

        self.lot_rect = pygame.Rect(54, 54, self.width - 108, self.height - 108)
        self.safe_rect = pygame.Rect(self.lot_rect.left + 54, self.lot_rect.top + 54, self.lot_rect.width - 108, self.lot_rect.height - 108)
        self.road_draw_length = self.lot_rect.width + self.lot_rect.height
        self.outside_lot_mask = self._build_outside_lot_mask()
        self.has_map = False
        self.next_reset_mode = "new_map"
        self.map_index = 0
        self.lives_left = self.map_lives_max
        self.reset()

    def reset(self) -> None:
        """Reset one attempt or roll forward to a new random map."""
        self.frame_index = 0
        self.end_screen_frames = 0
        self.end_reported = False
        self.end_event_pending = False
        self.won = False
        self.crashed = False
        self.timed_out = False
        self.park_frames = 0
        self.message = "Drive into the blue slot and stop."
        self.result_color = self.text_color

        if not self.has_map or self.next_reset_mode == "new_map":
            self._generate_map()
            self.map_index += 1
            self.lives_left = self.map_lives_max
            self.has_map = True

        self._respawn_current_map()
        self.next_reset_mode = "same_map"

    def _respawn_current_map(self) -> None:
        """Reset dynamic state while keeping the current random map."""
        self.car = CarState(self.spawn_x, self.spawn_y, self.spawn_angle)
        self.attempt_frames = 0
        self.park_frames = 0
        self.message = "Drive into the blue slot and stop."
        self.result_color = self.text_color
        for road in self.roads:
            road.reset()
        self._seed_initial_traffic()
        self._reset_autoplay_state()

    def _reset_autoplay_state(self) -> None:
        """Create a noisy generic controller state for the current target slot."""
        self.auto_points = self._make_auto_points()
        self.auto_approach_sign = self._choose_auto_approach_sign()
        self.auto_index = 0
        self.auto_pause = random.randint(0, 6)
        self.auto_noise = random.uniform(-0.08, 0.08)
        self.auto_noise_timer = random.randint(18, 34)
        self.auto_reverse_frames = 0
        self.auto_reverse_turn = random.choice([-1, 1])
        self.auto_watch_x = self.car.x
        self.auto_watch_y = self.car.y
        self.auto_stuck_frames = 0
        self.auto_speed_bias = random.uniform(-0.14, 0.18)
        self.auto_parking_frames = 0
        self.auto_reentry_frames = 0
        self.auto_reentry_turn = 0
        self._reset_auto_parking_progress()

    def _reset_auto_parking_progress(self) -> None:
        """Clear tracked progress for the final parking insertion."""
        self.auto_parking_stall_frames = 0
        self.auto_best_parking_corners = 0
        self.auto_best_parking_center = False
        self.auto_best_parking_forward = 9999
        self.auto_best_parking_lateral = 9999
        self.auto_best_parking_angle = 9999

    def _make_auto_points(self):
        """Build rough approach points from the target slot geometry."""
        approach_sign = self._choose_auto_approach_sign()
        fx, fy = self._forward_vector(self.target_spot.angle)
        rx, ry = self._right_vector(self.target_spot.angle)
        spawn_forward, spawn_right = self._local_point(self.target_spot.x, self.target_spot.y, self.target_spot.angle, self.spawn_x, self.spawn_y)
        entry_right = max(-52, min(52, spawn_right * 0.35))
        path_goal = self._auto_point(self.target_spot.x + fx * approach_sign * random.randint(120, 150) + rx * (entry_right + random.randint(-8, 8)), self.target_spot.y + fy * approach_sign * random.randint(120, 150) + ry * (entry_right + random.randint(-8, 8)))
        path_points = self._find_auto_path(path_goal[0], path_goal[1])
        return path_points + [self._auto_point(self.target_spot.x + fx * approach_sign * random.randint(62, 82) + rx * random.randint(-8, 8), self.target_spot.y + fy * approach_sign * random.randint(62, 82) + ry * random.randint(-8, 8)), self._auto_point(self.target_spot.x + fx * approach_sign * random.randint(18, 28) + rx * random.randint(-4, 4), self.target_spot.y + fy * approach_sign * random.randint(18, 28) + ry * random.randint(-4, 4)), self._auto_point(self.target_spot.x + rx * random.randint(-3, 3), self.target_spot.y + ry * random.randint(-3, 3))]

    def _auto_point(self, x, y):
        """Clamp one autoplay waypoint inside the safe driving area."""
        return max(self.safe_rect.left + 28, min(self.safe_rect.right - 28, x)), max(self.safe_rect.top + 28, min(self.safe_rect.bottom - 28, y))

    def _find_auto_path(self, goal_x, goal_y):
        """Find a coarse path from the spawn area to one goal point."""
        cell_size = 44
        cols = (self.safe_rect.width // cell_size) + 1
        rows = (self.safe_rect.height // cell_size) + 1
        start = self._grid_cell_for_point(self.spawn_x, self.spawn_y, cell_size, cols, rows)
        goal = self._grid_cell_for_point(goal_x, goal_y, cell_size, cols, rows)
        frontier = [(0.0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0.0}

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for neighbor in self._grid_neighbors(current[0], current[1], cols, rows):
                if self._grid_blocked(neighbor[0], neighbor[1], cell_size, goal):
                    continue
                step_cost = 1.4 if neighbor[0] != current[0] and neighbor[1] != current[1] else 1.0
                new_cost = cost_so_far[current] + step_cost
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    heuristic = math.hypot(goal[0] - neighbor[0], goal[1] - neighbor[1])
                    heapq.heappush(frontier, (new_cost + heuristic, neighbor))
                    came_from[neighbor] = current

        if goal not in came_from:
            return [self._auto_point(goal_x, goal_y)]

        path_cells = []
        current = goal
        while current is not None:
            path_cells.append(current)
            current = came_from[current]
        path_cells.reverse()
        return self._compress_auto_path(path_cells, cell_size)

    def _grid_cell_for_point(self, x, y, cell_size, cols, rows):
        """Convert one world point into a bounded grid cell index."""
        col = round((x - self.safe_rect.left) / cell_size)
        row = round((y - self.safe_rect.top) / cell_size)
        return max(0, min(cols - 1, col)), max(0, min(rows - 1, row))

    def _grid_neighbors(self, col, row, cols, rows):
        """Return neighboring cells for coarse autoplay routing."""
        neighbors = []
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                next_col = col + dc
                next_row = row + dr
                if 0 <= next_col < cols and 0 <= next_row < rows:
                    neighbors.append((next_col, next_row))
        return neighbors

    def _grid_blocked(self, col, row, cell_size, goal):
        """Check whether one routing cell is blocked by static geometry."""
        if (col, row) == goal:
            return False
        center_x = self.safe_rect.left + col * cell_size
        center_y = self.safe_rect.top + row * cell_size
        probe = CircleObstacle(center_x, center_y, 28, self.target_fill, "grid_probe")
        return self._shape_hits_any(probe, self.static_boxes) or self._shape_hits_any(probe, self.round_obstacles)

    def _compress_auto_path(self, path_cells, cell_size):
        """Convert grid cells into a shorter list of world path points."""
        points = []
        last_dir = None
        for index, cell in enumerate(path_cells):
            if index == 0:
                continue
            prev_cell = path_cells[index - 1]
            direction = (cell[0] - prev_cell[0], cell[1] - prev_cell[1])
            if direction != last_dir and index > 1:
                turn_cell = prev_cell
                points.append(self._auto_point(self.safe_rect.left + turn_cell[0] * cell_size, self.safe_rect.top + turn_cell[1] * cell_size))
            last_dir = direction
        if path_cells:
            last_cell = path_cells[-1]
            points.append(self._auto_point(self.safe_rect.left + last_cell[0] * cell_size, self.safe_rect.top + last_cell[1] * cell_size))
        return points

    def _choose_auto_approach_sign(self):
        """Use the slot side that supports the autoplay's forward parking insert."""
        return -1

    def _approach_score(self, sign):
        """Score one target approach side by how much straight open room it offers."""
        fx, fy = self._forward_vector(self.target_spot.angle)
        score = 0
        for distance in (45, 90, 140, 200, 250):
            probe = CircleObstacle(self.target_spot.x + fx * sign * distance, self.target_spot.y + fy * sign * distance, 30, self.target_fill, "probe")
            if not self._shape_inside_lot(probe):
                score -= 180
                break
            if self._shape_hits_any(probe, self.static_boxes) or self._shape_hits_any(probe, self.round_obstacles):
                score -= 120
                break
            score += distance
        return score

    def _generate_map(self) -> None:
        """Build a random layout from slot rows, circles, and roads."""
        for _ in range(9000000000000):
            if self._try_generate_map():
                return

    def _try_generate_map(self) -> bool:
        """Try to create one valid random map and return whether it succeeded."""
        footprints = []
        guide_spots = []
        target_candidates = []
        round_obstacles = []
        roads = []
        static_boxes = self._border_curbs()
        piece_kinds = ["slot"] * random.randint(1, 3) + ["road"] * random.randint(1, 5) + ["circle"] * random.randint(1, 5) 
        random.shuffle(piece_kinds)

        for piece_kind in piece_kinds:
            placed_piece = None
            for _ in range(40):
                if piece_kind == "slot":
                    candidate = self._make_slot_row_piece()
                elif piece_kind == "circle":
                    candidate = self._make_circle_piece()
                else:
                    candidate = self._make_road_piece()
                if self._piece_fits(candidate["footprints"], footprints):
                    placed_piece = candidate
                    break
            if placed_piece is None:
                if piece_kind == "slot":
                    return False
                continue
            footprints += placed_piece["footprints"]
            guide_spots += placed_piece["guide_spots"]
            target_candidates += placed_piece["target_candidates"]
            round_obstacles += placed_piece["round_obstacles"]
            roads += placed_piece["roads"]
            static_boxes += placed_piece["static_boxes"]

        if not target_candidates:
            return False

        target_spot = self._choose_target_candidate(target_candidates, static_boxes, round_obstacles)
        if target_spot is None:
            return False
        spawn_pose = self._choose_spawn_pose(static_boxes, round_obstacles, footprints, target_spot)
        if spawn_pose is None:
            return False

        self.guide_spots = guide_spots
        self.target_spot = target_spot
        self.target_park_box = self._make_target_park_box(target_spot)
        self.round_obstacles = round_obstacles
        self.roads = roads
        self.static_boxes = static_boxes
        self.static_polygons = [(box, self._box_points(box.x, box.y, box.length, box.width, box.angle)) for box in self.static_boxes]
        self.spawn_x, self.spawn_y, self.spawn_angle = spawn_pose
        return True

    def _make_target_park_box(self, slot):
        """Create a more lenient invisible parking box for the selected target slot."""
        return Box(slot.x, slot.y, slot.length + 42, slot.width + 24, slot.angle, slot.color, "target_park_box")

    def _choose_target_candidate(self, target_candidates, static_boxes, round_obstacles):
        """Pick a target slot with open room on the forward-insert side."""
        scored_targets = []
        for slot in target_candidates:
            negative_score = self._slot_approach_score(slot, -1, static_boxes, round_obstacles)
            if negative_score >= 220:
                scored_targets.append((negative_score, slot))
        if not scored_targets:
            return None
        scored_targets.sort(key=lambda item: item[0], reverse=True)
        return random.choice(scored_targets[:min(2, len(scored_targets))])[1]

    def _slot_approach_score(self, slot, sign, static_boxes, round_obstacles):
        """Score how open one side of a target slot is for autoplay approach."""
        fx, fy = self._forward_vector(slot.angle)
        score = 0
        for distance in (45, 90, 140, 200, 250):
            probe = CircleObstacle(slot.x + fx * sign * distance, slot.y + fy * sign * distance, 30, self.target_fill, "slot_probe")
            if not self._shape_inside_lot(probe):
                score -= 180
                break
            if self._shape_hits_any(probe, static_boxes) or self._shape_hits_any(probe, round_obstacles):
                score -= 120
                break
            score += distance
        return score

    def _border_curbs(self):
        """Return the fixed curbs that fence the parking lot."""
        return [
            Box(self.width / 2, self.lot_rect.top + 12, self.lot_rect.width - 28, 24, 0.0, self.curb_color, "curb"),
            Box(self.width / 2, self.lot_rect.bottom - 12, self.lot_rect.width - 28, 24, 0.0, self.curb_color, "curb"),
            Box(self.lot_rect.left + 12, self.height / 2, self.lot_rect.height - 28, 24, math.pi / 2, self.curb_color, "curb"),
            Box(self.lot_rect.right - 12, self.height / 2, self.lot_rect.height - 28, 24, math.pi / 2, self.curb_color, "curb"),
        ]

    def _make_slot_row_piece(self):
        """Create one random slot row with parked cars and at least one empty target candidate."""
        slot_angle = random.random() * math.pi *2
        slot_count = random.randint(3, 5)
        slot_spacing = self.car_width + random.randint(30, 40)
        slot_length = self.car_length + random.randint(28, 42)
        slot_width = self.car_width + random.randint(26, 38)
        row_span = (slot_count - 1) * slot_spacing
        footprint = Box(random.randint(self.safe_rect.left + 60, self.safe_rect.right - 60), random.randint(self.safe_rect.top + 60, self.safe_rect.bottom - 60), slot_length + random.randint(12, 66), row_span + slot_width + 28, slot_angle, (0, 0, 0), "footprint")
        rx, ry = self._right_vector(slot_angle)
        guide_spots = []
        easy_targets = []
        target_candidates = []
        static_boxes = []
        empty_count = random.randint(1, min(3, slot_count))
        empty_indexes = random.sample(list(range(slot_count)), empty_count)

        for index in range(slot_count):
            offset = (index - (slot_count - 1) / 2) * slot_spacing
            cx = footprint.x + rx * offset
            cy = footprint.y + ry * offset
            slot = Box(cx, cy, slot_length, slot_width, slot_angle, self.line_color, "slot")
            guide_spots.append(slot)
            if index in empty_indexes:
                target_candidates.append(slot)
                if index == 0 or index == slot_count - 1 or index - 1 in empty_indexes or index + 1 in empty_indexes:
                    easy_targets.append(slot)
            else:
                static_boxes.append(Box(cx, cy, self.car_length, self.car_width, slot_angle, random.choice(self.parked_car_colors), "parked_car"))

        if easy_targets:
            target_candidates = easy_targets

        return {"footprints": [footprint], "guide_spots": guide_spots, "target_candidates": target_candidates, "round_obstacles": [], "roads": [], "static_boxes": static_boxes}

    def _make_circle_piece(self):
        """Create one random round obstacle with a padded placement footprint."""
        radius = random.randint(28, 56)
        circle = CircleObstacle(random.randint(self.safe_rect.left + radius, self.safe_rect.right - radius), random.randint(self.safe_rect.top + radius, self.safe_rect.bottom - radius), radius, random.choice(self.circle_colors), "circle")
        footprint = CircleObstacle(circle.x, circle.y, radius + 22, (0, 0, 0), "footprint_circle")
        return {"footprints": [footprint], "guide_spots": [], "target_candidates": [], "round_obstacles": [circle], "roads": [], "static_boxes": []}

    def _make_road_piece(self):
        """Create one random straight road that will spawn moving cars."""
        angle = random.choice([0.0, math.pi / 2, -0.62, 0.62])
        length = random.randint(250, 380)
        width = random.randint(78, 96)
        road = Road(random.randint(self.safe_rect.left + 90, self.safe_rect.right - 90), random.randint(self.safe_rect.top + 90, self.safe_rect.bottom - 90), length, width, angle, random.choice([-1, 1]), random.choice([-1, 1]) * width * random.uniform(0.14, 0.22), random.uniform(2.3, 3.5), random.randint(92, 142), random.randint(150, 192), random.choice(self.road_colors))
        road.draw_length = self.road_draw_length
        road.footprint_length = self._road_footprint_length(road)
        footprint = Box(road.x, road.y, road.footprint_length, road.width, road.angle, (0, 0, 0), "footprint")
        return {"footprints": [footprint], "guide_spots": [], "target_candidates": [], "round_obstacles": [], "roads": [road], "static_boxes": []}

    def _road_footprint_length(self, road):
        """Return the longest visible road segment that stays inside the safe area."""
        low = 0.0
        high = road.draw_length
        for _ in range(24):
            mid = (low + high) / 2
            if self._shape_inside_lot(Box(road.x, road.y, mid, road.width, road.angle, road.color, "road_footprint")):
                low = mid
            else:
                high = mid
        return low

    def _build_outside_lot_mask(self):
        """Build one reusable background mask that hides drawing outside the lot."""
        mask = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        mask.fill((*self.bg_color, 255))
        pygame.draw.rect(mask, (0, 0, 0, 0), self.lot_rect, border_radius=28)
        return mask

    def _choose_spawn_pose(self, static_boxes, round_obstacles, footprints, target_spot):
        """Pick a free spawn pose that starts outside other structures and roughly faces the target."""
        fx, fy = self._forward_vector(target_spot.angle)
        rx, ry = self._right_vector(target_spot.angle)
        hint_x = target_spot.x - fx * random.randint(190, 270) + rx * random.randint(-65, 65)
        hint_y = target_spot.y - fy * random.randint(190, 270) + ry * random.randint(-65, 65)

        for attempt in range(140):
            if attempt < 70:
                x = hint_x + random.randint(-140, 140)
                y = hint_y + random.randint(-120, 120)
            else:
                x = random.randint(self.safe_rect.left + 44, self.safe_rect.right - 44)
                y = random.randint(self.safe_rect.top + 44, self.safe_rect.bottom - 44)
            if x < self.safe_rect.left + 44 or x > self.safe_rect.right - 44 or y < self.safe_rect.top + 44 or y > self.safe_rect.bottom - 44:
                continue
            angle = math.atan2(target_spot.y - y, target_spot.x - x) + random.uniform(-0.32, 0.32)
            spawn_box = Box(x, y, self.car_length, self.car_width, angle, self.player_color, "spawn")
            if not self._shape_inside_lot(spawn_box):
                continue
            if self._shape_hits_any(spawn_box, static_boxes) or self._shape_hits_any(spawn_box, round_obstacles) or self._shape_hits_any(spawn_box, footprints):
                continue
            return x, y, angle
        return None

    def _piece_fits(self, candidate_shapes, placed_shapes) -> bool:
        """Check whether every footprint stays inside the lot and avoids prior pieces."""
        for shape in candidate_shapes:
            if not self._shape_inside_lot(shape):
                return False
            if self._shape_hits_any(shape, placed_shapes):
                return False
        return True

    def _shape_inside_lot(self, shape) -> bool:
        """Check whether a box or circle shape stays inside the safe placement area."""
        if hasattr(shape, "radius"):
            return shape.x - shape.radius >= self.safe_rect.left and shape.x + shape.radius <= self.safe_rect.right and shape.y - shape.radius >= self.safe_rect.top and shape.y + shape.radius <= self.safe_rect.bottom
        for px, py in self._box_points(shape.x, shape.y, shape.length, shape.width, shape.angle):
            if px < self.safe_rect.left or px > self.safe_rect.right or py < self.safe_rect.top or py > self.safe_rect.bottom:
                return False
        return True

    def _shape_hits_any(self, shape, others) -> bool:
        """Check one shape against a list of other shapes."""
        for other in others:
            if self._shapes_overlap(shape, other):
                return True
        return False

    def _shapes_overlap(self, shape_a, shape_b) -> bool:
        """Check overlap for box-box, circle-circle, or circle-box pairs."""
        if hasattr(shape_a, "radius") and hasattr(shape_b, "radius"):
            return self._circles_overlap(shape_a, shape_b)
        if hasattr(shape_a, "radius"):
            return self._circle_box_overlap(shape_a, shape_b)
        if hasattr(shape_b, "radius"):
            return self._circle_box_overlap(shape_b, shape_a)
        points_a = self._box_points(shape_a.x, shape_a.y, shape_a.length, shape_a.width, shape_a.angle)
        points_b = self._box_points(shape_b.x, shape_b.y, shape_b.length, shape_b.width, shape_b.angle)
        return self._polygons_overlap(points_a, points_b)

    def _circles_overlap(self, circle_a, circle_b) -> bool:
        """Check circle overlap using squared distance."""
        dx = circle_a.x - circle_b.x
        dy = circle_a.y - circle_b.y
        radius_sum = circle_a.radius + circle_b.radius
        return dx * dx + dy * dy <= radius_sum * radius_sum

    def _circle_box_overlap(self, circle, box) -> bool:
        """Check overlap between one circle and one rotated rectangle."""
        local_forward, local_right = self._local_point(box.x, box.y, box.angle, circle.x, circle.y)
        closest_forward = min(max(local_forward, -box.length / 2), box.length / 2)
        closest_right = min(max(local_right, -box.width / 2), box.width / 2)
        diff_forward = local_forward - closest_forward
        diff_right = local_right - closest_right
        return diff_forward * diff_forward + diff_right * diff_right <= circle.radius * circle.radius

    def _forward_vector(self, angle):
        """Return the forward unit vector for one heading angle."""
        return math.cos(angle), math.sin(angle)

    def _right_vector(self, angle):
        """Return the right-side unit vector for one heading angle."""
        return -math.sin(angle), math.cos(angle)

    def _local_point(self, x, y, angle, px, py):
        """Project a world point into one local forward-right frame."""
        dx = px - x
        dy = py - y
        fx, fy = self._forward_vector(angle)
        rx, ry = self._right_vector(angle)
        return dx * fx + dy * fy, dx * rx + dy * ry

    def _box_points(self, x, y, length, width, angle):
        """Return the four corners of a rotated rectangle."""
        fx, fy = self._forward_vector(angle)
        rx, ry = self._right_vector(angle)
        half_length = length / 2
        half_width = width / 2
        return [(x + fx * half_length - rx * half_width, y + fy * half_length - ry * half_width), (x + fx * half_length + rx * half_width, y + fy * half_length + ry * half_width), (x - fx * half_length + rx * half_width, y - fy * half_length + ry * half_width), (x - fx * half_length - rx * half_width, y - fy * half_length - ry * half_width)]

    def _polygon_axes(self, points):
        """Return the separating axes generated from polygon edges."""
        axes = []
        for index in range(len(points)):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % len(points)]
            edge_x = x2 - x1
            edge_y = y2 - y1
            axes.append((-edge_y, edge_x))
        return axes

    def _project_points(self, points, axis):
        """Project polygon points onto one axis and return the scalar range."""
        ax, ay = axis
        first = points[0][0] * ax + points[0][1] * ay
        low = first
        high = first
        for x, y in points[1:]:
            value = x * ax + y * ay
            if value < low:
                low = value
            if value > high:
                high = value
        return low, high

    def _polygons_overlap(self, points_a, points_b) -> bool:
        """Check two rotated rectangles with the separating axis test."""
        for axis in self._polygon_axes(points_a) + self._polygon_axes(points_b):
            low_a, high_a = self._project_points(points_a, axis)
            low_b, high_b = self._project_points(points_b, axis)
            if high_a < low_b or high_b < low_a:
                return False
        return True

    def _angle_delta(self, a, b):
        """Return the shortest signed difference between two angles."""
        delta = a - b
        while delta > math.pi:
            delta -= math.tau
        while delta < -math.pi:
            delta += math.tau
        return delta

    def _update_steering(self, action: pygameBase.ActionState) -> None:
        """Turn the visible front wheels with A and D and recenter when idle."""
        if action["A"] and not action["D"]:
            self.car.steer -= self.steer_step
        elif action["D"] and not action["A"]:
            self.car.steer += self.steer_step
        elif self.car.steer > 0:
            self.car.steer -= self.steer_return
            if self.car.steer < 0:
                self.car.steer = 0.0
        elif self.car.steer < 0:
            self.car.steer += self.steer_return
            if self.car.steer > 0:
                self.car.steer = 0.0

        if self.car.steer > self.max_steer:
            self.car.steer = self.max_steer
        if self.car.steer < -self.max_steer:
            self.car.steer = -self.max_steer

    def _update_speed(self, action: pygameBase.ActionState) -> None:
        """Accelerate with W and S and coast when neither is held."""
        drive = 0
        if action["W"] and not action["S"]:
            drive = 1
        elif action["S"] and not action["W"]:
            drive = -1

        if drive != 0:
            self.car.speed += self.acceleration * drive
        else:
            self.car.speed *= self.coasting
            if abs(self.car.speed) < 0.04:
                self.car.speed = 0.0

        if self.car.speed > self.max_forward_speed:
            self.car.speed = self.max_forward_speed
        if self.car.speed < -self.max_reverse_speed:
            self.car.speed = -self.max_reverse_speed

    def _move_car(self) -> None:
        """Advance the player car with a simple bicycle steering model."""
        distance = self.car.speed
        self.car.angle += math.tan(self.car.steer) * distance / self.wheel_base
        fx, fy = self._forward_vector(self.car.angle)
        self.car.x += fx * distance
        self.car.y += fy * distance

    def _car_points(self):
        """Return the current player car polygon."""
        return self._box_points(self.car.x, self.car.y, self.car_length, self.car_width, self.car.angle)

    def _car_hits_static(self) -> bool:
        """Check the player car against static boxes and round obstacles."""
        car_points = self._car_points()
        for _, obstacle_points in self.static_polygons:
            if self._polygons_overlap(car_points, obstacle_points):
                return True
        player_box = Box(self.car.x, self.car.y, self.car_length, self.car_width, self.car.angle, self.player_color, "player")
        for circle in self.round_obstacles:
            if self._circle_box_overlap(circle, player_box):
                return True
        return False

    def _car_hits_traffic(self) -> bool:
        """Check the player car against all moving traffic cars."""
        car_points = self._car_points()
        for road in self.roads:
            for traffic_car in road.cars:
                traffic_points = self._box_points(traffic_car.x, traffic_car.y, traffic_car.length, traffic_car.width, traffic_car.angle)
                if self._polygons_overlap(car_points, traffic_points):
                    return True
        return False

    def _car_parking_state(self, park_box):
        """Return how much of the car sits inside one parking box."""
        inside_corners = 0
        for px, py in self._car_points():
            local_forward, local_right = self._local_point(park_box.x, park_box.y, park_box.angle, px, py)
            if abs(local_forward) <= park_box.length / 2 - self.slot_margin and abs(local_right) <= park_box.width / 2 - self.slot_margin:
                inside_corners += 1
        center_forward, center_right = self._local_point(park_box.x, park_box.y, park_box.angle, self.car.x, self.car.y)
        center_inside = abs(center_forward) <= park_box.length / 2 - self.slot_margin and abs(center_right) <= park_box.width / 2 - self.slot_margin
        return inside_corners, center_inside, center_forward, center_right

    def _car_is_parked(self) -> bool:
        """Check whether the whole player car is inside the target slot and nearly still."""
        park_box = self.target_park_box
        inside_corners, center_inside, _, _ = self._car_parking_state(park_box)
        if not center_inside:
            return False
        if inside_corners < 4:
            return False
        if abs(self._angle_delta(self.car.angle, park_box.angle)) > 0.45:
            return False
        if abs(self.car.speed) > 0.48:
            return False
        return True

    def _update_roads(self) -> None:
        """Advance traffic on every road and spawn new moving cars."""
        player_box = Box(self.car.x, self.car.y, self.car_length, self.car_width, self.car.angle, self.player_color, "player")

        for road in self.roads:
            road.spawn_timer -= 1
            if road.spawn_timer <= 0:
                self._spawn_traffic_car(road, player_box)
                road.spawn_timer = random.randint(road.spawn_min, road.spawn_max)

            for traffic_car in road.cars:
                fx, fy = self._forward_vector(traffic_car.angle)
                traffic_car.x += fx * traffic_car.speed
                traffic_car.y += fy * traffic_car.speed

            road.cars = [traffic_car for traffic_car in road.cars if abs(self._local_point(road.x, road.y, road.angle, traffic_car.x, traffic_car.y)[0]) < road.draw_length / 2 + 120]

    def _seed_initial_traffic(self) -> None:
        """Place visible traffic cars on each road when one attempt starts."""
        player_box = Box(self.car.x, self.car.y, self.car_length, self.car_width, self.car.angle, self.player_color, "player")
        for road in self.roads:
            self._seed_road_traffic(road, player_box)

    def _seed_road_traffic(self, road, player_box) -> None:
        """Fill the fitted part of one road with a small amount of visible traffic."""
        visible_length = getattr(road, "footprint_length", road.length)
        max_offset = visible_length / 2 - 54
        if max_offset <= 0:
            return
        target_count = 1 if visible_length < 320 else 2
        player_forward, _ = self._local_point(road.x, road.y, road.angle, self.car.x, self.car.y)
        candidate_offsets = [0.0, max_offset * 0.58, -max_offset * 0.58, max_offset * 0.88, -max_offset * 0.88]
        candidate_offsets.sort(key=lambda forward_offset: abs(forward_offset - player_forward), reverse=True)

        for forward_offset in candidate_offsets:
            if len(road.cars) >= target_count:
                break
            traffic_car, traffic_box = self._make_traffic_car_on_road(road, forward_offset)
            if not self._shape_inside_lot(traffic_box):
                continue
            if self._shapes_overlap(traffic_box, player_box):
                continue
            too_close = False
            for other in road.cars:
                other_forward = self._local_point(road.x, road.y, road.angle, other.x, other.y)[0]
                if abs(other_forward - forward_offset) < traffic_car.length + 34:
                    too_close = True
                    break
            if too_close:
                continue
            road.cars.append(traffic_car)

    def _make_traffic_car_on_road(self, road, forward_offset):
        """Create one traffic car and its collision box at a road-relative offset."""
        fx, fy = self._forward_vector(road.angle)
        rx, ry = self._right_vector(road.angle)
        spawn_x = road.x + fx * forward_offset + rx * road.lane_offset
        spawn_y = road.y + fy * forward_offset + ry * road.lane_offset
        traffic_angle = road.angle if road.flow > 0 else road.angle + math.pi
        traffic_car = TrafficCar(spawn_x, spawn_y, traffic_angle, road.speed, random.choice(self.traffic_colors))
        traffic_box = Box(traffic_car.x, traffic_car.y, traffic_car.length, traffic_car.width, traffic_car.angle, traffic_car.color, "traffic")
        return traffic_car, traffic_box

    def _spawn_traffic_car(self, road, player_box) -> None:
        """Spawn one moving car on a road if the entry area is clear."""
        entry_forward = -road.flow * (road.draw_length / 2 - 34)
        traffic_car, traffic_box = self._make_traffic_car_on_road(road, entry_forward)

        for other in road.cars:
            other_box = Box(other.x, other.y, other.length, other.width, other.angle, other.color, "traffic")
            if self._shapes_overlap(traffic_box, other_box):
                return
        if self._shapes_overlap(traffic_box, player_box):
            return
        road.cars.append(traffic_car)

    def _lose_attempt(self, message) -> None:
        """Mark the current life as failed and decide whether to retry or change map."""
        if not self.timed_out:
            self.crashed = True
        self.lives_left -= 1
        self.message = message
        self.result_color = self.fail_color
        if self.lives_left <= 0:
            self.message = message + " Next map."
            self.next_reset_mode = "new_map"
        else:
            self.message = message + f" {self.lives_left} lives left on this map."
            self.next_reset_mode = "same_map"
        if not self.end_reported:
            self.end_reported = True
            self.end_event_pending = True

    def _win_attempt(self) -> None:
        """Mark the current attempt as a successful park and queue a new map."""
        self.won = True
        self.message = "Clean park. Next map."
        self.result_color = self.win_color
        self.next_reset_mode = "new_map"
        if not self.end_reported:
            self.end_reported = True
            self.end_event_pending = True

    def update(self, action: pygameBase.ActionState) -> bool:
        """Advance one frame of driving, traffic, parking, and map-life logic."""
        self.frame_index += 1

        if self.end_event_pending:
            self.end_event_pending = False
            return True

        if self.won or self.crashed or self.timed_out:
            self.end_screen_frames += 1
            if self.end_screen_frames >= self.end_screen_auto_reset or action["A"] or action["LL"]:
                self.reset()
            return False

        self.attempt_frames += 1
        self._update_steering(action)
        self._update_speed(action)
        self._update_roads()

        old_x = self.car.x
        old_y = self.car.y
        old_angle = self.car.angle
        self._move_car()

        if self._car_hits_static():
            self.car.x = old_x
            self.car.y = old_y
            self.car.angle = old_angle
            self.car.speed = 0.0
            self._lose_attempt("Crash.")
            return False

        if self._car_hits_traffic():
            self.car.x = old_x
            self.car.y = old_y
            self.car.angle = old_angle
            self.car.speed = 0.0
            self._lose_attempt("Traffic hit.")
            return False

        if self._car_is_parked():
            self.park_frames += 1
            self.message = "Hold still to lock the parking result."
            self.result_color = self.text_color
            if self.park_frames >= self.park_confirm_frames:
                self._win_attempt()
            return False

        self.park_frames = 0
        self.message = "Drive into the blue slot and stop."
        self.result_color = self.text_color

        if self.attempt_frames >= self.map_frame_limit:
            self.timed_out = True
            self._lose_attempt("Time ran out.")
            return False

        return False

    def _front_hazard(self):
        """Estimate the nearest obstacle or traffic car in front of the player."""
        nearest_distance = 9999
        nearest_side = 0
        candidate_shapes = []

        for box in self.static_boxes:
            if box.kind == "curb" or box.kind == "parked_car":
                candidate_shapes.append(box)
        for circle in self.round_obstacles:
            candidate_shapes.append(circle)
        for road in self.roads:
            for traffic_car in road.cars:
                candidate_shapes.append(Box(traffic_car.x, traffic_car.y, traffic_car.length, traffic_car.width, traffic_car.angle, traffic_car.color, "traffic"))

        for shape in candidate_shapes:
            local_forward, local_right = self._local_point(self.car.x, self.car.y, self.car.angle, shape.x, shape.y)
            if local_forward <= -40 or local_forward >= 170:
                continue
            if abs(local_right) >= 68:
                continue
            if local_forward < nearest_distance:
                nearest_distance = local_forward
                nearest_side = -1 if local_right < 0 else 1

        return nearest_distance, nearest_side

    def getAutoAction(self) -> pygameBase.ActionState:
        """Drive with a weak noisy heuristic that sometimes succeeds and sometimes fails."""
        action = self.BLANK_ACTION.copy()
        if self.won or self.crashed or self.timed_out:
            return action

        inside_corners, center_inside, center_forward, center_right = self._car_parking_state(self.target_park_box)
        angle_error = self._angle_delta(self.target_park_box.angle, self.car.angle)

        if self.auto_reentry_frames > 0:
            self.auto_reentry_frames -= 1
            action["S"] = True
            if self.auto_reentry_turn < 0:
                action["A"] = True
            elif self.auto_reentry_turn > 0:
                action["D"] = True
            return action

        if self.auto_index == len(self.auto_points) - 1 and (inside_corners >= 2 or center_inside):
            self.auto_parking_frames += 1
            parking_forward = center_forward * self.auto_approach_sign
            lateral_error = abs(center_right)
            heading_error = abs(angle_error)
            made_progress = inside_corners > self.auto_best_parking_corners or center_inside and not self.auto_best_parking_center or parking_forward < self.auto_best_parking_forward - 4 or lateral_error < self.auto_best_parking_lateral - 3 or heading_error < self.auto_best_parking_angle - 0.05
            if made_progress:
                self.auto_parking_stall_frames = 0
                self.auto_best_parking_corners = max(self.auto_best_parking_corners, inside_corners)
                self.auto_best_parking_center = self.auto_best_parking_center or center_inside
                self.auto_best_parking_forward = min(self.auto_best_parking_forward, parking_forward)
                self.auto_best_parking_lateral = min(self.auto_best_parking_lateral, lateral_error)
                self.auto_best_parking_angle = min(self.auto_best_parking_angle, heading_error)
            else:
                self.auto_parking_stall_frames += 1
            if inside_corners >= 4 and center_inside:
                if self.car.speed > 0.05:
                    action["S"] = True
                elif self.car.speed < -0.05:
                    action["W"] = True
                return action
            if parking_forward < -10 or self.auto_parking_stall_frames > 42:
                self.auto_parking_frames = 0
                self._reset_auto_parking_progress()
                self.auto_reentry_frames = 24
                self.auto_reentry_turn = -1 if center_right > 0 else 1
                self.auto_index = max(0, len(self.auto_points) - 3)
                action["S"] = True
                if self.auto_reentry_turn < 0:
                    action["A"] = True
                else:
                    action["D"] = True
                return action
            desired_parking_speed = 0.58
            if parking_forward < 30 or inside_corners >= 3:
                desired_parking_speed = 0.4
            if parking_forward < 14 or lateral_error > 12 or heading_error > 0.14:
                desired_parking_speed = 0.24
            if self.car.speed < desired_parking_speed - 0.08:
                action["W"] = True
            elif self.car.speed > desired_parking_speed + 0.12:
                action["S"] = True
            steer_signal = angle_error * 0.3 - center_right * 0.03
            if abs(center_right) > 10 or abs(angle_error) > 0.14:
                if steer_signal > 0.12:
                    action["D"] = True
                elif steer_signal < -0.12:
                    action["A"] = True
            return action

        self.auto_parking_frames = 0
        self._reset_auto_parking_progress()

        if self.auto_pause > 0:
            self.auto_pause -= 1
            return action

        self.auto_noise_timer -= 1
        if self.auto_noise_timer <= 0:
            self.auto_noise = random.uniform(-0.08, 0.08)
            self.auto_noise_timer = random.randint(18, 34)

        if self.frame_index % 18 == 0:
            moved = math.hypot(self.car.x - self.auto_watch_x, self.car.y - self.auto_watch_y)
            if moved < 12:
                self.auto_stuck_frames += 18
            else:
                self.auto_stuck_frames = 0
            self.auto_watch_x = self.car.x
            self.auto_watch_y = self.car.y

        if self.auto_stuck_frames >= 96:
            self.auto_reverse_frames = random.randint(10, 22)
            self.auto_reverse_turn = random.choice([-1, 1])
            self.auto_stuck_frames = 0

        hazard_distance, hazard_side = self._front_hazard()
        if hazard_distance < 26 and random.random() < 0.12:
            self.auto_reverse_frames = random.randint(8, 16)
            self.auto_reverse_turn = -hazard_side if hazard_side != 0 else random.choice([-1, 1])

        if self.auto_reverse_frames > 0:
            self.auto_reverse_frames -= 1
            action["S"] = True
            if self.auto_reverse_turn < 0:
                action["A"] = True
            else:
                action["D"] = True
            return action

        target_x, target_y = self.auto_points[self.auto_index]
        local_forward, local_right = self._local_point(self.car.x, self.car.y, self.car.angle, target_x, target_y)
        distance = math.hypot(local_forward, local_right)

        if distance < 40 and self.auto_index < len(self.auto_points) - 1:
            self.auto_index += 1
            target_x, target_y = self.auto_points[self.auto_index]
            local_forward, local_right = self._local_point(self.car.x, self.car.y, self.car.angle, target_x, target_y)
            distance = math.hypot(local_forward, local_right)
        elif self.auto_index < len(self.auto_points) - 1:
            next_x, next_y = self.auto_points[self.auto_index + 1]
            next_distance = math.hypot(self.car.x - next_x, self.car.y - next_y)
            if next_distance + 18 < math.hypot(self.car.x - target_x, self.car.y - target_y):
                self.auto_index += 1
                target_x, target_y = self.auto_points[self.auto_index]
                local_forward, local_right = self._local_point(self.car.x, self.car.y, self.car.angle, target_x, target_y)
                distance = math.hypot(local_forward, local_right)

        if self.auto_index < len(self.auto_points) - 1 and local_forward < -26 and abs(local_right) > 22:
            reverse_bearing = math.atan2(-local_right, -local_forward) + self.auto_noise * 0.45
            action["S"] = True
            if reverse_bearing > 0.14:
                action["A"] = True
            elif reverse_bearing < -0.14:
                action["D"] = True
            return action

        if random.random() < 0.003:
            self.auto_pause = random.randint(1, 4)

        bearing = math.atan2(local_right, local_forward) + self.auto_noise
        if self.auto_index == len(self.auto_points) - 1:
            slot_forward, slot_right = self._local_point(self.car.x, self.car.y, self.car.angle, self.target_spot.x, self.target_spot.y)
            slot_angle_error = self._angle_delta(self.target_spot.angle, self.car.angle)
            bearing = math.atan2(slot_right, slot_forward + 20) + slot_angle_error * 0.24 + self.auto_noise * 0.35
        if bearing > 0.1:
            action["D"] = True
        elif bearing < -0.1:
            action["A"] = True

        desired_speed = 2.4 + self.auto_speed_bias
        if self.auto_index == 1:
            desired_speed = 1.9 + self.auto_speed_bias
        if self.auto_index == 2:
            desired_speed = 1.2 + self.auto_speed_bias * 0.35
        if self.auto_index == len(self.auto_points) - 1:
            desired_speed = 0.78 + self.auto_speed_bias * 0.1

        if abs(bearing) > 0.35:
            desired_speed = min(desired_speed, 1.1)
        if abs(bearing) > 0.75:
            desired_speed = min(desired_speed, 0.35)
        if hazard_distance < 72:
            desired_speed = min(desired_speed, 0.75)
        if hazard_distance < 42:
            desired_speed = min(desired_speed, 0.1)
        if distance < 34:
            desired_speed = min(desired_speed, 0.4)
        if self.auto_index == len(self.auto_points) - 1 and distance < 24:
            desired_speed = min(desired_speed, 0.28)
        if distance < 14 and self.auto_index == len(self.auto_points) - 1:
            desired_speed = 0.0
        if self.auto_index < len(self.auto_points) - 1 and local_forward < -24 and abs(local_right) < 55:
            self.auto_index += 1

        if desired_speed >= 0:
            if self.car.speed < desired_speed - 0.14:
                action["W"] = True
            elif self.car.speed > desired_speed + 0.18:
                action["S"] = True
        else:
            action["S"] = True

        return action

    def _draw_shadow(self, points, dx, dy) -> None:
        """Draw a soft offset shadow for a polygon."""
        shadow_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.polygon(shadow_surface, self.shadow_color, [(round(x + dx), round(y + dy)) for x, y in points])
        self.screen.blit(shadow_surface, (0, 0))

    def _draw_box(self, box: Box) -> None:
        """Draw one static box such as a curb."""
        points = self._box_points(box.x, box.y, box.length, box.width, box.angle)
        self._draw_shadow(points, 4, 6)
        draw_points = [(round(x), round(y)) for x, y in points]
        pygame.draw.polygon(self.screen, box.color, draw_points)
        if box.kind == "curb":
            highlight = self._box_points(box.x - math.sin(box.angle) * 2, box.y + math.cos(box.angle) * 2, box.length - 10, box.width - 10, box.angle)
            pygame.draw.polygon(self.screen, self.curb_top_color, [(round(x), round(y)) for x, y in highlight])

    def _draw_circle_obstacle(self, circle) -> None:
        """Draw one round island obstacle."""
        shadow_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.circle(shadow_surface, self.shadow_color, (round(circle.x + 4), round(circle.y + 6)), round(circle.radius + 2))
        self.screen.blit(shadow_surface, (0, 0))
        pygame.draw.circle(self.screen, circle.color, (round(circle.x), round(circle.y)), round(circle.radius))
        pygame.draw.circle(self.screen, self.grass_ring, (round(circle.x), round(circle.y)), round(circle.radius * 0.62))

    def _draw_road_base(self, road) -> None:
        """Draw one road surface without markings or cars."""
        road_points = self._box_points(road.x, road.y, road.draw_length, road.width, road.angle)
        pygame.draw.polygon(self.screen, road.color, [(round(x), round(y)) for x, y in road_points])

    def _draw_road_markings(self, road) -> None:
        """Draw dashed center markings for one road."""
        fx, fy = self._forward_vector(road.angle)
        dash_half = 12
        dash_count = int(road.draw_length / 92) + 2
        for dash_index in range(-dash_count, dash_count + 1):
            cx = road.x + fx * dash_index * 46
            cy = road.y + fy * dash_index * 46
            start = (round(cx - fx * dash_half), round(cy - fy * dash_half))
            end = (round(cx + fx * dash_half), round(cy + fy * dash_half))
            pygame.draw.line(self.screen, self.road_mark_color, start, end, 3)

    def _draw_traffic_car(self, traffic_car: TrafficCar) -> None:
        """Draw one moving traffic car."""
        self._draw_vehicle(traffic_car.x, traffic_car.y, traffic_car.angle, traffic_car.color, 0.0, traffic_car.length, traffic_car.width)

    def _draw_vehicle(self, x, y, angle, color, steer, length, width) -> None:
        """Draw one car body with visible front-wheel direction."""
        body_points = self._box_points(x, y, length, width, angle)
        cabin_points = self._box_points(x + math.cos(angle) * 2, y + math.sin(angle) * 2, length * 0.46, width * 0.64, angle)
        self._draw_shadow(body_points, 5, 7)
        pygame.draw.polygon(self.screen, color, [(round(px), round(py)) for px, py in body_points])
        pygame.draw.polygon(self.screen, (247, 248, 251), [(round(px), round(py)) for px, py in cabin_points])
        nose_points = self._box_points(x + math.cos(angle) * length * 0.22, y + math.sin(angle) * length * 0.22, length * 0.14, width * 0.78, angle)
        pygame.draw.polygon(self.screen, (255, 225, 212), [(round(px), round(py)) for px, py in nose_points])
        front_axle = self.wheel_base / 2 * (length / self.car_length)
        rear_axle = -front_axle
        wheel_offset = width * 0.43
        wheel_length = self.wheel_length * (length / self.car_length)
        wheel_width = self.wheel_width * (width / self.car_width)
        wheel_centers = [(x + math.cos(angle) * front_axle - math.sin(angle) * -wheel_offset, y + math.sin(angle) * front_axle + math.cos(angle) * -wheel_offset, angle + steer), (x + math.cos(angle) * front_axle - math.sin(angle) * wheel_offset, y + math.sin(angle) * front_axle + math.cos(angle) * wheel_offset, angle + steer), (x + math.cos(angle) * rear_axle - math.sin(angle) * -wheel_offset, y + math.sin(angle) * rear_axle + math.cos(angle) * -wheel_offset, angle), (x + math.cos(angle) * rear_axle - math.sin(angle) * wheel_offset, y + math.sin(angle) * rear_axle + math.cos(angle) * wheel_offset, angle)]
        for wx, wy, wa in wheel_centers:
            wheel_points = self._box_points(wx, wy, wheel_length, wheel_width, wa)
            pygame.draw.polygon(self.screen, (33, 35, 41), [(round(px), round(py)) for px, py in wheel_points])

    def _draw_slots(self) -> None:
        """Draw all slot outlines and highlight the active target slot."""
        for slot in self.guide_spots:
            points = [(round(x), round(y)) for x, y in self._box_points(slot.x, slot.y, slot.length, slot.width, slot.angle)]
            if slot is self.target_spot:
                fill_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                pygame.draw.polygon(fill_surface, (*self.target_fill, 90), points)
                self.screen.blit(fill_surface, (0, 0))
                pygame.draw.lines(self.screen, self.target_line, True, points, 3)
            else:
                pygame.draw.lines(self.screen, self.line_color, True, points, 2)

    def _draw_hud(self) -> None:
        """Draw instructions, map and life counters, and parking progress."""
        self.screen.blit(self.title_font.render(self.name, True, self.text_color), (24, 14))
        self.screen.blit(self.ui_font.render(self.message, True, self.result_color), (24, 54))
        self.screen.blit(self.small_font.render(f"lives {self.lives_left}", True, self.dim_text), (self.width - 180, 86))
        self.screen.blit(self.small_font.render(f"time {self.map_frame_limit - self.attempt_frames}", True, self.dim_text), (self.width - 180, 108))

        pygame.draw.rect(self.screen, (127, 140, 153), pygame.Rect(20, self.height - 58, 236, 42), border_radius=6)
        pygame.draw.rect(self.screen, (27, 31, 38), pygame.Rect(28, self.height - 38, 220, 12), border_radius=6)
        pygame.draw.rect(self.screen, self.target_line, pygame.Rect(28, self.height - 38, 220 * self.park_frames / self.park_confirm_frames, 12), border_radius=6)
        self.screen.blit(self.small_font.render("Parking hold", True, self.text_color), (28, self.height - 58))
        self.screen.blit(self.small_font.render(f"steer {self.car.steer:+.2f}", True, self.dim_text), (self.width - 170, self.height - 56))
        self.screen.blit(self.small_font.render(f"speed {self.car.speed:+.2f}", True, self.dim_text), (self.width - 170, self.height - 34))

    def draw(self) -> None:
        """Render the random map, dynamic traffic, player car, and HUD."""
        self.screen.fill(self.bg_color)
        pygame.draw.rect(self.screen, self.lot_color, self.lot_rect, border_radius=28)
        for road in self.roads:
            self._draw_road_base(road)
        for road in self.roads:
            self._draw_road_markings(road)
        for road in self.roads:
            for traffic_car in road.cars:
                self._draw_traffic_car(traffic_car)
        self.screen.blit(self.outside_lot_mask, (0, 0))
        self._draw_slots()
        for circle in self.round_obstacles:
            self._draw_circle_obstacle(circle)
        for box in self.static_boxes:
            if box.kind == "parked_car":
                self._draw_vehicle(box.x, box.y, box.angle, box.color, 0.0, self.car_length, self.car_width)
            else:
                self._draw_box(box)
        self._draw_vehicle(self.car.x, self.car.y, self.car.angle, self.player_color, self.car.steer, self.car_length, self.car_width)
        self._draw_hud()

    def getPrompt(self) -> str:
        """Describe the current game family for training and autoplay callers."""
        return "A top-down car parking game with random parking lots, circular islands, and straight traffic roads. Turn the front wheels with A and D. Hold W to drive forward and S to reverse. Avoid curbs, parked cars, round obstacles, and moving traffic. Stop with the whole car inside the blue parking slot."


if __name__ == "__main__":
    pygameRunner.run_autoplay(CarParkingBase)
