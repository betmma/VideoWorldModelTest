from __future__ import annotations

import os
import sys

import pygame

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from games.wolfensteinMaze import WolfensteinMazeBase


class TrailMapWolfensteinMaze(WolfensteinMazeBase):
    name = "Wolfenstein Maze Trail Maps"

    def __init__(self, headless: bool = False) -> None:
        self.internal_map_count = 3
        super().__init__(headless=headless)
        self.maze_width = 27
        self.maze_height = 17
        self.reset()

    def reset(self) -> None:
        super().reset()
        self.poster_sites = self._build_poster_sites()
        self.poster_surface = self._build_poster_surface()

    def _build_poster_sites(self) -> list[tuple[int, int, str]]:
        sites = [(self.entrance_row - 1, self.outdoor_width, "W")]
        exit_path = self._find_path(self.start_cell, self.exit_cell, allow_boundary=True)
        if len(exit_path) < 5:
            return sites

        candidates: list[tuple[int, int, int, str]] = []
        for path_index, (row, col) in enumerate(exit_path[1:-1], start=1):
            if row <= 1 or row >= self.grid_height - 2:
                continue
            if col <= self.outdoor_width + 1 or col >= self.grid_width - 2:
                continue
            for delta_row, delta_col, face in ((0, 1, "W"), (0, -1, "E"), (1, 0, "N"), (-1, 0, "S")):
                wall_row = row + delta_row
                wall_col = col + delta_col
                if self.grid[wall_row][wall_col] != "#":
                    continue
                if wall_row in (0, self.grid_height - 1) or wall_col in (0, self.grid_width - 1):
                    continue
                candidates.append((path_index, wall_row, wall_col, face))

        if not candidates:
            return sites

        min_spacing = max(5, len(exit_path) // 7)
        chosen_path_indices: list[int] = []
        used_sites = set(sites)
        target_count = min(self.internal_map_count, len(candidates))
        target_indices = [round((len(exit_path) - 1) * (index + 1) / (target_count + 1)) for index in range(target_count)]

        for target_index in target_indices:
            best_site = None
            for spacing_limit in (min_spacing, 3, 0):
                for path_index, wall_row, wall_col, face in candidates:
                    site = (wall_row, wall_col, face)
                    if site in used_sites:
                        continue
                    if spacing_limit and any(abs(path_index - previous) < spacing_limit for previous in chosen_path_indices):
                        continue
                    score = (abs(path_index - target_index), abs(wall_col - self.grid_width // 2), abs(wall_row - self.entrance_row))
                    if best_site is None or score < best_site[0]:
                        best_site = (score, path_index, wall_row, wall_col, face)
                if best_site is not None:
                    break
            if best_site is None:
                continue
            _, path_index, wall_row, wall_col, face = best_site
            chosen_path_indices.append(path_index)
            used_sites.add((wall_row, wall_col, face))
            sites.append((wall_row, wall_col, face))

        return sites

    def _build_poster_surface(self) -> pygame.Surface:
        surface = pygame.Surface((192, 192))
        surface.fill((110, 74, 44))
        paper = pygame.Rect(10, 10, 172, 172)
        pygame.draw.rect(surface, (232, 220, 190), paper)
        pygame.draw.rect(surface, (76, 46, 22), paper, 4)

        usable_width = paper.width - 16
        usable_height = paper.height - 48
        cell_size = max(4, min(6, usable_width // self.grid_width, usable_height // self.grid_height))
        map_width = self.grid_width * cell_size
        map_height = self.grid_height * cell_size
        offset_x = paper.x + (paper.width - map_width) // 2
        offset_y = paper.y + 24 + (paper.height - 24 - map_height) // 2

        for row in range(self.grid_height):
            for col in range(self.grid_width):
                rect = pygame.Rect(offset_x + col * cell_size, offset_y + row * cell_size, cell_size, cell_size)
                cell = self.grid[row][col]
                color = (236, 232, 214)
                if cell == "#":
                    color = (44, 54, 62)
                elif cell == "E":
                    color = (88, 138, 220)
                elif cell == "X":
                    color = (224, 126, 68)
                pygame.draw.rect(surface, color, rect)

        entrance_center = (
            offset_x + self.entrance_cell[1] * cell_size + cell_size // 2,
            offset_y + self.entrance_cell[0] * cell_size + cell_size // 2,
        )
        exit_center = (
            offset_x + self.exit_cell[1] * cell_size + cell_size // 2,
            offset_y + self.exit_cell[0] * cell_size + cell_size // 2,
        )
        player_x = getattr(self, "player_x", self.spawn_cell[1] + 0.5)
        player_y = getattr(self, "player_y", self.spawn_cell[0] + 0.5)
        player_center = (round(offset_x + player_x * cell_size), round(offset_y + player_y * cell_size))

        pygame.draw.circle(surface, (42, 90, 186), entrance_center, max(2, cell_size // 3))
        pygame.draw.circle(surface, (34, 168, 88), exit_center, max(2, cell_size // 3))
        pygame.draw.circle(surface, (255, 255, 255), player_center, max(3, cell_size // 2))
        pygame.draw.circle(surface, (210, 40, 40), player_center, max(2, cell_size // 3))

        label = self.poster_font.render("LIVE MAP", True, (64, 46, 28))
        legend = self.tip_font.render("Red dot = you", True, (92, 64, 38))
        surface.blit(label, label.get_rect(center=(surface.get_width() // 2, 28)))
        surface.blit(legend, legend.get_rect(center=(surface.get_width() // 2, 48)))
        return surface

    def _poster_texture_u(self, face: str, offset: float) -> float:
        # North- and east-facing walls need a horizontal flip to keep the map readable.
        if face in {"E", "N"}:
            return 1.0 - offset
        return offset

    def _poster_u(self, row: int, col: int, face: str, offset: float) -> float | None:
        for poster_row, poster_col, poster_face in getattr(self, "poster_sites", []):
            if (row, col, face) == (poster_row, poster_col, poster_face):
                return self._poster_texture_u(face, offset)
        return None

    def _draw_world(self) -> None:
        self.poster_surface = self._build_poster_surface()
        super()._draw_world()

    def _draw_hud(self) -> None:
        super()._draw_hud()
        if self.frame_index < 160:
            tip = self.tip_font.render("Wall maps deeper inside the maze track your live red-dot position.", True, (250, 224, 154))
            self.screen.blit(tip, tip.get_rect(center=(self.width // 2, self.height - 48)))

    def getPrompt(self) -> str:
        return (
            f"This is {self.name}. Use A and D to rotate and W and S to move. "
            "Besides the map at the entrance, there are several wall maps placed deeper inside the maze. Each map shows the whole layout, and the red dot updates in real time to show your current position. Reach the far exit opening to win. After entering the maze, going back out through the entrance loses."
        )


if __name__ == "__main__":
    from pygameRunner import run_autoplay, run_human_debug

    run_human_debug(TrailMapWolfensteinMaze)
