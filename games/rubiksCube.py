from __future__ import annotations

import random
from ursina import *
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Assuming the runner interfaces are available in these modules based on standard naming
from engineBase import ActionState
from ursinaBase import UrsinaGameBase


class RubiksCube(UrsinaGameBase):
    name = "RubiksCube"
    variantsPath = "RubiksCubes"

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
                    self.cubes.append(cubie)
                    destroy(cubie_builder)

        # Reset Cursor and State
        self.cur_pos = Vec3(0, 0, -1)
        self.cur_normal = Vec3(0, 0, -1)
        self.cursor = Entity(model='cube', color=color.rgba32(255, 255, 0, 200), scale=(0.9, 0.9, 0.05))
        self.update_cursor_visuals()

        # Animation states (frame-based for determinism)
        self.animating = False
        self.anim_type = None
        self.anim_axis = 'x'
        self.anim_dir = 1
        self.anim_frames = 0
        self.anim_max_frames = 6  # Higher number = slower animation
        
        # Auto action state
        self.auto_timer = 0
        self.moves_made = 0
        
        self.prev_action = self.BLANK_ACTION.copy()

    def getPrompt(self) -> str:
        return "Rubik's Cube simulation. Use W/A/S/D to move the cursor across the visible faces. Moving the cursor over the edge will rotate the entire cube to reveal hidden faces. Use the Up/Left/Down/Right arrows to rotate the currently selected slice/layer."

    def getAutoAction(self) -> ActionState:
        action = self.BLANK_ACTION.copy()
        
        if self.animating:
            return action
        
        self.frames += 1
        if self.frames % self.moveInterval != 0:
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
        
        for e in self.cubes:
            if axis == 'x' and round(e.x) == round(slice_val): e.world_parent = self.rotation_helper
            elif axis == 'y' and round(e.y) == round(slice_val): e.world_parent = self.rotation_helper
            elif axis == 'z' and round(e.z) == round(slice_val): e.world_parent = self.rotation_helper

    def reset_layer_rotation(self):
        for e in self.cubes:
            e.world_parent = scene
            e.position = Vec3(round(e.x), round(e.y), round(e.z))
            e.rotation = Vec3(round(e.rotation_x/90)*90, round(e.rotation_y/90)*90, round(e.rotation_z/90)*90)
            
        self.rotation_helper.rotation = (0, 0, 0)
        self.animating = False
        self.moves_made += 1

    def rotate_whole_cube(self, axis, direction):
        self.animating = True
        self.anim_type = 'cube'
        self.anim_axis = axis
        self.anim_dir = direction
        self.anim_frames = 0

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

        self.cur_pos = self.rotate_point3d(self.cur_pos, axis, direction * 90)
        self.cur_normal = self.rotate_point3d(self.cur_normal, axis, direction * 90)
        self.update_cursor_visuals()

        self.animating = False
        self.moves_made += 1

if __name__ == "__main__":
    from ursinaRunner import run_human_debug, run_autoplay
    run_autoplay(RubiksCube)