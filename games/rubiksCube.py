from __future__ import annotations

import random
from typing import Any
from ursina import *
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Assuming the runner interfaces are available in these modules based on standard naming
from engineBase import ActionState
from ursinaBase import UrsinaGameBase


class RubiksCube(UrsinaGameBase):
    name = "RubiksCube"
    variantsPath = "RubiksCubes"
    state_color_names = ("right", "left", "top", "bottom", "back", "front")
    state_color_rgb = {
        "right": (255, 0, 127),
        "left": (255, 127, 0),
        "top": (255, 255, 255),
        "bottom": (255, 255, 0),
        "back": (0, 128, 255),
        "front": (0, 255, 0),
    }
    state_faces = (
        {"name": "right", "normal": (1, 0, 0), "axis": 0, "value": 1, "row_axis": 1, "rows": (1, 0, -1), "col_axis": 2, "cols": (-1, 0, 1), "corners": ((427, 241), (595, 73), (620, 325), (488, 466)), "preview": False},
        {"name": "left", "normal": (-1, 0, 0), "axis": 0, "value": -1, "row_axis": 1, "rows": (1, 0, -1), "col_axis": 2, "cols": (1, 0, -1), "corners": ((754, 69), (796, 99), (798, 144), (754, 122)), "preview": True},
        {"name": "top", "normal": (0, 1, 0), "axis": 1, "value": 1, "row_axis": 2, "rows": (-1, 0, 1), "col_axis": 0, "cols": (-1, 0, 1), "corners": ((198, 180), (427, 241), (595, 73), (376, 49)), "preview": False},
        {"name": "bottom", "normal": (0, -1, 0), "axis": 1, "value": -1, "row_axis": 2, "rows": (1, 0, -1), "col_axis": 0, "cols": (1, 0, -1), "corners": ((710, 144), (754, 122), (798, 144), (754, 163)), "preview": True},
        {"name": "back", "normal": (0, 0, 1), "axis": 2, "value": 1, "row_axis": 1, "rows": (1, 0, -1), "col_axis": 0, "cols": (1, 0, -1), "corners": ((716, 99), (754, 69), (754, 122), (710, 144)), "preview": True},
        {"name": "front", "normal": (0, 0, -1), "axis": 2, "value": -1, "row_axis": 1, "rows": (1, 0, -1), "col_axis": 0, "cols": (-1, 0, 1), "corners": ((198, 180), (427, 241), (488, 466), (289, 383)), "preview": False},
    )

    def __init__(self, headless: bool = False) -> None:
        super().__init__(headless=headless)
        
        # Standard Rubik's Cube colors
        self.cube_colors = [
            color.pink,     # +x (right)
            color.orange,   # -x (left)
            color.white,    # +y (top)
            color.yellow,   # -y (bottom)
            color.azure,    # +z (back)
            color.green,    # -z (front)
        ]
        self.internal_color = color.dark_gray
        
        # UI and helpers
        self.cubes: list[Entity] = []
        self.cursor: Entity | None = None
        self.ui_text: Text | None = None
        
        # Math helpers for 3D rotations
        self.math_dummy_parent = Entity(enabled=False)
        self.math_dummy = Entity(parent=self.math_dummy_parent)
        self.rotation_helper = Entity()
        
        self.prev_action: ActionState = self.BLANK_ACTION.copy()
        
        self.preview_buffer = None
        self.preview_cam = None
        self.preview_panel_bg: Entity | None = None
        self.preview_panel: Entity | None = None
        self.preview_label: Text | None = None

        self.setup_secondary_camera()

    def _vec_tuple(self, value) -> tuple[int, int, int]:
        """Round a Vec3-like value to an integer tuple."""
        return (round(value.x), round(value.y), round(value.z))

    def _rotate_tuple(self, value: tuple[int, int, int], axis: str, direction: int) -> tuple[int, int, int]:
        """Rotate an integer vector by a quarter turn using Ursina's rotation signs."""
        x, y, z = value
        if axis == 'x':
            return (x, -z, y) if direction == 1 else (x, z, -y)
        if axis == 'y':
            return (z, y, -x) if direction == 1 else (-z, y, x)
        return (y, -x, z) if direction == 1 else (-y, x, z)

    def _rotate_sticker_state(self, cubes: list[Entity], axis: str, direction: int) -> None:
        """Rotate logical sticker normals for the cubies in a completed turn."""
        for cubie in cubes:
            cubie.stickers = {self._rotate_tuple(normal, axis, direction): label for normal, label in cubie.stickers.items()}

    def _make_cubie_stickers(self, pos) -> dict[tuple[int, int, int], str]:
        """Return the outward sticker labels for a new cubie position."""
        stickers = {}
        if pos.x == 1:
            stickers[(1, 0, 0)] = "right"
        if pos.x == -1:
            stickers[(-1, 0, 0)] = "left"
        if pos.y == 1:
            stickers[(0, 1, 0)] = "top"
        if pos.y == -1:
            stickers[(0, -1, 0)] = "bottom"
        if pos.z == 1:
            stickers[(0, 0, 1)] = "back"
        if pos.z == -1:
            stickers[(0, 0, -1)] = "front"
        return stickers

    def setup_secondary_camera(self) -> None:
        if self.preview_cam is not None:
            return

        # Panda3D offscreen buffer + camera
        self.preview_buffer = application.base.win.makeTextureBuffer("hidden_faces", 256, 256)
        self.preview_buffer.setSort(-100)   # render before main window
        raw_tex = self.preview_buffer.getTexture()
        preview_tex = Texture(raw_tex)

        self.preview_cam = application.base.makeCamera(self.preview_buffer)
        self.preview_cam.reparent_to(scene) 
        self.preview_cam.node().getLens().setFov(camera.fov)

        # Live texture panel
        self.preview_panel = Entity(
            parent=camera.ui,
            model='quad',
            texture=preview_tex,
            x=.68, y=.25,
            scale=(.30, .30),
            unlit=True,
            z=-0.2,
        )

        self.preview_label = Text(
            parent=camera.ui,
            text='Hidden faces',
            position=(.49, .40),
            scale=.9,
        )

        self.update_secondary_camera()

    def close(self) -> None:
        if self.preview_cam is not None:
            self.preview_cam.removeNode()
            self.preview_cam = None
        if self.preview_buffer is not None:
            base = getattr(application, "base", None)
            if base is not None:
                base.graphicsEngine.removeWindow(self.preview_buffer)
            self.preview_buffer = None
        super().close()

    def update_secondary_camera(self) -> None:
        if self.preview_cam is None:
            return

        # Mirror the main camera through the origin so the inset shows the opposite 3 faces.
        p = camera.position
        self.preview_cam.setPos(-p.x, -p.y, -p.z)
        self.preview_cam.lookAt(0, 0, 0)

    def reset(self) -> None:
        self.frames=0
        # Clean up existing entities for new episodes
        for c in self.cubes:
            destroy(c)
        self.cubes.clear()
        
        if self.cursor:
            destroy(self.cursor)
        if self.ui_text:
            destroy(self.ui_text)
            
        # Reset scene background and camera
        window.color = color._16
        camera.fov = 50
        camera.position = (6, 6, -6)
        camera.look_at(Vec3(0, 0, 0))

        self.ui_text = Text(text='WASD: Move Cursor\nArrows: Rotate Layer', position=(-0.85, 0.45), scale=1.2)

        # Build Cubies
        for x in range(3):
            for y in range(3):
                for z in range(3):
                    pos = Vec3(x-1, y-1, z-1)
                    cubie_builder = Entity(enabled=False)
                    
                    face_configs = [
                        (Vec3.right, pos.x, 0, 1), # X-axis
                        (Vec3.up,    pos.y, 2, 3), # Y-axis
                        (Vec3.forward, pos.z, 4, 5) # Z-axis
                    ]

                    for direction, val, pos_idx, neg_idx in face_configs:
                        c_pos = self.cube_colors[pos_idx] if val == 1 else self.internal_color
                        e_pos = Entity(parent=cubie_builder, model='plane', origin_y=-.5, 
                                       texture='white_cube', color=c_pos)
                        e_pos.look_at(direction, Vec3.up)

                        c_neg = self.cube_colors[neg_idx] if val == -1 else self.internal_color
                        e_neg = Entity(parent=cubie_builder, model='plane', origin_y=-.5, 
                                       texture='white_cube', color=c_neg)
                        e_neg.look_at(-direction, Vec3.up)

                    cubie = Entity(model=cubie_builder.combine(), position=pos, texture='white_cube')
                    cubie.stickers = self._make_cubie_stickers(pos)
                    self.cubes.append(cubie)
                    destroy(cubie_builder)

        # Reset Cursor and State
        self.cur_pos = Vec3(0, 0, -1)
        self.cur_normal = Vec3(0, 0, -1)
        self.cursor = Entity(model='sphere', color=color.rgba32(255, 255, 0, 200), scale=(0.9, 0.9, 0.05))
        self.update_cursor_visuals()

        # Animation states (frame-based for determinism)
        self.animating = False
        self.anim_type = None
        self.anim_axis = 'x'
        self.anim_dir = 1
        self.anim_frames = 0
        self.anim_max_frames = 6  # Higher number = slower animation
        self.rotating_cubes = []
        
        # Auto action state
        self.auto_timer = 0
        self.moves_made = 0
        
        self.prev_action = self.BLANK_ACTION.copy()
        self.update_secondary_camera()

    def getPrompt(self) -> str:
        return "Rubik's Cube simulation. Use W/A/S/D to move the cursor across the visible faces. Moving the cursor over the edge will rotate the entire cube to reveal hidden faces. Use the Up/Left/Down/Right arrows to rotate the currently selected slice/layer."

    def getAutoAction(self, frame_index: int) -> ActionState:
        action = self.BLANK_ACTION.copy()
        
        if self.animating:
            return action
        
        if frame_index % self.moveInterval != 0:
            return action
            
        self.auto_timer -= 1
        if self.auto_timer <= 0:
            self.auto_timer = random.randint(1,3)
            # Pick a random valid input mapping
            key = random.choice(["W", "A", "S", "D", "LU", "LL", "LD", "LR"])
            action[key] = True
            
        return action

    def update(self, action: ActionState) -> bool:
        # 1. Process active animations frame-by-frame
        if self.animating:
            self.anim_frames += 1
            progress = (self.anim_frames / self.anim_max_frames) * 90 * self.anim_dir
            
            if self.anim_axis == 'x': self.rotation_helper.rotation_x = progress
            elif self.anim_axis == 'y': self.rotation_helper.rotation_y = progress
            elif self.anim_axis == 'z': self.rotation_helper.rotation_z = progress
            
            if self.anim_frames >= self.anim_max_frames:
                if self.anim_type == 'layer':
                    self.reset_layer_rotation()
                elif self.anim_type == 'cube':
                    self.reset_whole_cube(self.anim_axis, self.anim_dir)
            
            self.prev_action = action.copy()
            return False

        # 2. Extract edge triggers for inputs
        w_p  = action["W"] and not self.prev_action["W"]
        a_p  = action["A"] and not self.prev_action["A"]
        s_p  = action["S"] and not self.prev_action["S"]
        d_p  = action["D"] and not self.prev_action["D"]
        lu_p = action["LU"] and not self.prev_action["LU"]
        ll_p = action["LL"] and not self.prev_action["LL"]
        ld_p = action["LD"] and not self.prev_action["LD"]
        lr_p = action["LR"] and not self.prev_action["LR"]
        
        # --- WASD Cursor Movement ---
        move_dir = Vec3(0,0,0)
        if w_p or a_p or s_p or d_p:
            if self.cur_normal == Vec3(0, 0, -1): # Front
                if w_p: move_dir = Vec3(0, 1, 0)
                if s_p: move_dir = Vec3(0, -1, 0)
                if a_p: move_dir = Vec3(-1, 0, 0)
                if d_p: move_dir = Vec3(1, 0, 0)
            elif self.cur_normal == Vec3(1, 0, 0): # Right
                if w_p: move_dir = Vec3(0, 1, 0)
                if s_p: move_dir = Vec3(0, -1, 0)
                if a_p: move_dir = Vec3(0, 0, -1)
                if d_p: move_dir = Vec3(0, 0, 1)
            elif self.cur_normal == Vec3(0, 1, 0): # Top
                if w_p: move_dir = Vec3(0, 0, 1)
                if s_p: move_dir = Vec3(0, 0, -1)
                if a_p: move_dir = Vec3(-1, 0, 0)
                if d_p: move_dir = Vec3(1, 0, 0)

            if move_dir != Vec3(0,0,0):
                old_normal = Vec3(self.cur_normal)
                new_pos = self.cur_pos + move_dir
                new_normal = Vec3(self.cur_normal)

                # Boundary wrapping onto adjacent faces
                if new_pos.x > 1: new_pos.x = 1; new_normal = Vec3(1, 0, 0)
                elif new_pos.x < -1: new_pos.x = -1; new_normal = Vec3(-1, 0, 0)
                elif new_pos.y > 1: new_pos.y = 1; new_normal = Vec3(0, 1, 0)
                elif new_pos.y < -1: new_pos.y = -1; new_normal = Vec3(0, -1, 0)
                elif new_pos.z > 1: new_pos.z = 1; new_normal = Vec3(0, 0, 1)
                elif new_pos.z < -1: new_pos.z = -1; new_normal = Vec3(0, 0, -1)

                self.cur_pos = new_pos
                self.cur_normal = new_normal
                self.update_cursor_visuals()

                # Trigger whole cube rotation if moving to an occluded face
                if self.cur_normal == Vec3(-1, 0, 0):
                    if old_normal == Vec3(0, 0, -1): self.rotate_whole_cube('y', -1)
                    elif old_normal == Vec3(0, 1, 0): self.rotate_whole_cube('z', 1)
                elif self.cur_normal == Vec3(0, -1, 0):
                    if old_normal == Vec3(0, 0, -1): self.rotate_whole_cube('x', 1)
                    elif old_normal == Vec3(1, 0, 0): self.rotate_whole_cube('z', -1)
                elif self.cur_normal == Vec3(0, 0, 1):
                    if old_normal == Vec3(1, 0, 0): self.rotate_whole_cube('y', 1)
                    elif old_normal == Vec3(0, 1, 0): self.rotate_whole_cube('x', -1)

        # --- Arrow Keys Layer Rotation ---
        elif lu_p or ld_p or ll_p or lr_p:
            if self.cur_normal == Vec3(0, 0, -1): # Front
                if lu_p: self.rotate_layer('x', self.cur_pos.x, 1)
                elif ld_p: self.rotate_layer('x', self.cur_pos.x, -1)
                elif ll_p: self.rotate_layer('y', self.cur_pos.y, 1)
                elif lr_p: self.rotate_layer('y', self.cur_pos.y, -1)
            elif self.cur_normal == Vec3(1, 0, 0): # Right
                if lu_p: self.rotate_layer('z', self.cur_pos.z, -1)
                elif ld_p: self.rotate_layer('z', self.cur_pos.z, 1)
                elif ll_p: self.rotate_layer('y', self.cur_pos.y, 1)
                elif lr_p: self.rotate_layer('y', self.cur_pos.y, -1)
            elif self.cur_normal == Vec3(0, 1, 0): # Top
                if lu_p: self.rotate_layer('x', self.cur_pos.x, 1)
                elif ld_p: self.rotate_layer('x', self.cur_pos.x, -1)
                elif ll_p: self.rotate_layer('z', self.cur_pos.z, -1)
                elif lr_p: self.rotate_layer('z', self.cur_pos.z, 1)

        self.prev_action = action.copy()
        
        # End episode after a certain amount of moves to cleanly segment clips in dataset
        if self.moves_made >= 50:
            return True

        return False

    # ----------------- HELPER LOGIC -----------------

    def _sample_point(self, face: dict[str, Any], row: int, col: int, width: int, height: int) -> tuple[int, int]:
        """Return the scaled sample point for one sticker."""
        coords = (1 / 6, 1 / 2, 5 / 6)
        u = coords[col]
        v = coords[row]
        p00, p01, p11, p10 = face["corners"]
        x = (1 - u) * (1 - v) * p00[0] + u * (1 - v) * p01[0] + u * v * p11[0] + (1 - u) * v * p10[0]
        y = (1 - u) * (1 - v) * p00[1] + u * (1 - v) * p01[1] + u * v * p11[1] + (1 - u) * v * p10[1]
        return round(x * width / 854), round(y * height / 480)

    def _state_position(self, face: dict[str, Any], row: int, col: int) -> tuple[int, int, int]:
        """Return the cubie position for a face sample."""
        position = [0, 0, 0]
        position[face["axis"]] = face["value"]
        position[face["row_axis"]] = face["rows"][row]
        position[face["col_axis"]] = face["cols"][col]
        return tuple(position)

    def _state_samples(self, width: int, height: int) -> list[dict[str, Any]]:
        """Return all sticker samples in state order."""
        samples = []
        for face in self.state_faces:
            for row in range(3):
                for col in range(3):
                    samples.append({"face": face["name"], "normal": face["normal"], "position": self._state_position(face, row, col), "row": row, "col": col, "point": self._sample_point(face, row, col, width, height), "preview": face["preview"]})
        return samples

    def _pixel_color_name(self, pixel) -> str:
        """Return the closest cube color label for a pixel."""
        r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
        return min(self.state_color_names, key=lambda name: (r - self.state_color_rgb[name][0]) ** 2 + (g - self.state_color_rgb[name][1]) ** 2 + (b - self.state_color_rgb[name][2]) ** 2)

    def _sample_raw_color(self, frame_rgb, sample: dict[str, Any]) -> tuple[int, int, int]:
        """Return the exact RGB color at one sticker sample point."""
        x, y = sample["point"]
        pixel = frame_rgb[y, x]
        return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

    def _raw_color_distance(self, a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
        """Return total RGB channel distance between two sampled colors."""
        return sum(abs(a[index] - b[index]) for index in range(3))

    def _raw_colors_match(self, a: tuple[int, int, int], b: tuple[int, int, int]) -> bool:
        """Return whether two sampled RGB colors should count as the same color."""
        threshold = 10 if self._pixel_color_name(a) == "bottom" and self._pixel_color_name(b) == "bottom" else 30
        return self._raw_color_distance(a, b) <= threshold

    def _raw_color_groups(self, raw_colors: list[tuple[int, int, int]]) -> list[dict[str, Any]]:
        """Group sampled colors while allowing small RGB differences."""
        color_groups = []
        for index, raw_color in enumerate(raw_colors):
            for group in color_groups:
                if self._raw_colors_match(raw_color, group["color"]):
                    group["indices"].append(index)
                    break
            else:
                color_groups.append({"color": raw_color, "indices": [index]})
        return color_groups

    def frameToState(self, frame_rgb) -> dict[str, Any]:
        """Recover sticker colors and cursor position from one rendered RGB frame."""
        height, width = frame_rgb.shape[:2]
        samples = self._state_samples(width, height)
        raw_colors = [self._sample_raw_color(frame_rgb, sample) for sample in samples]
        color_groups = self._raw_color_groups(raw_colors)
        cursor_group = next((group for group in color_groups if len(group["indices"]) == 1), None)
        hidden_sticker_group = next((group for group in color_groups if len(group["indices"]) == 8), None)
        cursor_index = cursor_group["indices"][0] if cursor_group is not None else None
        sticker_colors = list(raw_colors)
        if cursor_index is not None and hidden_sticker_group is not None:
            sticker_colors[cursor_index] = hidden_sticker_group["color"]
        stickers = tuple(self._pixel_color_name(raw_color) for raw_color in sticker_colors)
        cursor = None
        if cursor_index is not None:
            sample = samples[cursor_index]
            cursor = (sample["face"], sample["row"], sample["col"])
        return {"stickers": stickers, "cursor": cursor}

    def expectedFrameToState(self) -> dict[str, Any]:
        """Return the expected frameToState result from the logical cube state."""
        stickers = []
        for face in self.state_faces:
            for row in range(3):
                for col in range(3):
                    position = self._state_position(face, row, col)
                    cubie = next(cubie for cubie in self.cubes if self._vec_tuple(cubie.position) == position)
                    stickers.append(cubie.stickers[face["normal"]])
        return {"stickers": tuple(stickers), "cursor": self._expected_cursor_state(), "animating": self.animating}

    def _expected_cursor_state(self) -> tuple[str, int, int] | None:
        """Return the cursor state in the same face-row-column format as frameToState."""
        normal = self._vec_tuple(self.cur_normal)
        position = self._vec_tuple(self.cur_pos)
        for face in self.state_faces:
            if face["normal"] != normal:
                continue
            row = face["rows"].index(position[face["row_axis"]])
            col = face["cols"].index(position[face["col_axis"]])
            return (face["name"], row, col)
        return None

    def statesMatch(self, gt_state: Any, pred_state: Any, last_gt_state: Any, last_pred_state: Any) -> bool:
        """Compare parsed Rubik's Cube states and skip in-progress rotation frames."""
        if isinstance(gt_state, dict) and gt_state.get("animating"):
            return True
        if not isinstance(gt_state, dict) or not isinstance(pred_state, dict):
            return gt_state == pred_state
        stickers_match = gt_state.get("stickers") == pred_state.get("stickers")
        return stickers_match and gt_state.get("cursor") == pred_state.get("cursor")

    def update_cursor_visuals(self):
        if self.cursor:
            self.cursor.position = self.cur_pos + self.cur_normal * 0.52
            self.cursor.look_at(self.cursor.position + self.cur_normal)

    def rotate_point3d(self, p, axis, angle):
        self.math_dummy_parent.rotation = (0, 0, 0)
        self.math_dummy.position = p
        if axis == 'x': self.math_dummy_parent.rotation_x = angle
        elif axis == 'y': self.math_dummy_parent.rotation_y = angle
        elif axis == 'z': self.math_dummy_parent.rotation_z = angle
        return Vec3(round(self.math_dummy.world_position.x), 
                    round(self.math_dummy.world_position.y), 
                    round(self.math_dummy.world_position.z))

    def rotate_layer(self, axis, slice_val, direction):
        self.animating = True
        self.anim_type = 'layer'
        self.anim_axis = axis
        self.anim_dir = direction
        self.anim_frames = 0
        self.rotating_cubes = []
        
        for e in self.cubes:
            if axis == 'x' and round(e.x) == round(slice_val):
                e.world_parent = self.rotation_helper
                self.rotating_cubes.append(e)
            elif axis == 'y' and round(e.y) == round(slice_val):
                e.world_parent = self.rotation_helper
                self.rotating_cubes.append(e)
            elif axis == 'z' and round(e.z) == round(slice_val):
                e.world_parent = self.rotation_helper
                self.rotating_cubes.append(e)

    def reset_layer_rotation(self):
        for e in self.cubes:
            e.world_parent = scene
            e.position = Vec3(round(e.x), round(e.y), round(e.z))
            e.rotation = Vec3(round(e.rotation_x/90)*90, round(e.rotation_y/90)*90, round(e.rotation_z/90)*90)
            
        self.rotation_helper.rotation = (0, 0, 0)
        self._rotate_sticker_state(self.rotating_cubes, self.anim_axis, self.anim_dir)
        self.rotating_cubes = []
        self.animating = False
        self.moves_made += 1

    def rotate_whole_cube(self, axis, direction):
        self.animating = True
        self.anim_type = 'cube'
        self.anim_axis = axis
        self.anim_dir = direction
        self.anim_frames = 0
        self.rotating_cubes = list(self.cubes)

        for e in self.cubes:
            e.world_parent = self.rotation_helper
            
        # Cursor follows entire cube rotation
        self.cursor.world_parent = self.rotation_helper

    def reset_whole_cube(self, axis, direction):
        for e in self.cubes:
            e.world_parent = scene
            e.position = Vec3(round(e.x), round(e.y), round(e.z))
            e.rotation = Vec3(round(e.rotation_x/90)*90, round(e.rotation_y/90)*90, round(e.rotation_z/90)*90)
            
        self.cursor.world_parent = scene
        self.rotation_helper.rotation = (0, 0, 0)
        self._rotate_sticker_state(self.rotating_cubes, axis, direction)
        self.rotating_cubes = []

        self.cur_pos = self.rotate_point3d(self.cur_pos, axis, direction * 90)
        self.cur_normal = self.rotate_point3d(self.cur_normal, axis, direction * 90)
        self.update_cursor_visuals()

        self.animating = False
        self.moves_made += 1

if __name__ == "__main__":
    from ursinaRunner import run_human_debug, run_autoplay
    run_autoplay(RubiksCube)
