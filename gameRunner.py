from __future__ import annotations

from abc import ABC, abstractmethod
import importlib.util
import inspect
import os
import random
from typing import Callable, Optional, Type

import pygame

from gameBase import ActionState, GameBase


FrameCallback = Callable[[pygame.Surface, ActionState, int, bool], Optional[bool]]


def choose_random_variant(game_cls: Type[GameBase]) -> Type[GameBase]:
	"""Pick one random subclass from game_cls.variantsPath.

	If no valid variant is found, returns game_cls itself.
	"""
	base_file = inspect.getfile(game_cls)
	base_dir = os.path.dirname(os.path.abspath(base_file))
	variants_dir = os.path.join(base_dir, game_cls.variantsPath)

	if not os.path.isdir(variants_dir):
		return game_cls

	variant_classes: list[Type[GameBase]] = [game_cls]
	for filename in os.listdir(variants_dir):
		if not filename.endswith(".py") or filename.startswith("__"):
			continue

		module_path = os.path.join(variants_dir, filename)
		module_name = f"_variant_{game_cls.__name__}_{filename[:-3]}"
		spec = importlib.util.spec_from_file_location(module_name, module_path)
		if spec is None or spec.loader is None:
			continue

		module = importlib.util.module_from_spec(spec)
		try:
			spec.loader.exec_module(module)
		except Exception:
			continue

		for _, obj in inspect.getmembers(module, inspect.isclass):
			if obj is game_cls:
				continue
			if issubclass(obj, game_cls):
				variant_classes.append(obj)

	if not variant_classes:
		return game_cls

	return random.choice(variant_classes)


class _BaseRunner(ABC):
	"""Shared frame loop for concrete runners."""

	def __init__(
		self,
		game: GameBase,
		max_frames: int | None = None,
		on_frame: FrameCallback | None = None,
	) -> None:
		self.game = game
		self.max_frames = max_frames
		self.on_frame = on_frame
		self.frame_index = 0
		self.rendered_frame_index = 0
		self.ended_once = False
		self.running = False

	@abstractmethod
	def _next_action(self) -> ActionState:
		"""Return action for current frame."""

	def _handle_events(self) -> None:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				self.running = False
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				self.running = False

	def _blank_action(self) -> ActionState:
		return {
			"W": False,
			"A": False,
			"S": False,
			"D": False,
			"LU": False,
			"LL": False,
			"LD": False,
			"LR": False,
		}

	def _emit_frame(self, action: ActionState, ended_this_frame: bool) -> None:
		if self.on_frame is None:
			return
		should_continue = self.on_frame(self.game.screen, action, self.rendered_frame_index, ended_this_frame)
		if should_continue is False:
			self.running = False

	def run(self) -> int:
		"""Run game loop until quit signal or max_frames reached.

		Returns total processed frames.
		"""
		self.running = True
		self.frame_index = 0
		self.rendered_frame_index = 0
		self.ended_once = False
		self.game.reset()
		self.game.draw()
		if not self.game.headless:
			pygame.display.flip()

		while self.running:
			self._handle_events()
			action = self._next_action()
			ended_this_frame = self.game.update(action)
			if ended_this_frame:
				self.ended_once = True

			self.game.draw()
			if not self.game.headless:
				pygame.display.flip()
			self.rendered_frame_index += 1
			self._emit_frame(action, ended_this_frame)
			self.game.clock.tick(self.game.fps)

			self.frame_index += 1
			if self.max_frames is not None and self.frame_index >= self.max_frames:
				self.running = False

		pygame.quit()
		return self.frame_index


class HumanDebugRunner(_BaseRunner):
	"""Runner for local debug play controlled by keyboard input."""

	def _next_action(self) -> ActionState:
		keys = pygame.key.get_pressed()
		return {
			"W": bool(keys[pygame.K_w]),
			"A": bool(keys[pygame.K_a]),
			"S": bool(keys[pygame.K_s]),
			"D": bool(keys[pygame.K_d]),
			"LU": bool(keys[pygame.K_UP]),
			"LL": bool(keys[pygame.K_LEFT]),
			"LD": bool(keys[pygame.K_DOWN]),
			"LR": bool(keys[pygame.K_RIGHT]),
		}


class AutoPlayRunner(_BaseRunner):
	"""Runner for automated play, intended for data/video pipelines."""

	def _next_action(self) -> ActionState:
		return self.game.getAutoAction()


def run_human_debug(
	game_cls: Type[GameBase],
	headless: bool = False,
	max_frames: int | None = None,
	on_frame: FrameCallback | None = None,
) -> int:
	"""Construct and run one game instance in human debug mode."""
	game = game_cls(headless=headless)
	runner = HumanDebugRunner(game=game, max_frames=max_frames, on_frame=on_frame)
	return runner.run()


def run_autoplay(
	game_cls: Type[GameBase],
	headless: bool = False,
	max_frames: int | None = None,
	on_frame: FrameCallback | None = None,
) -> int:
	"""Construct and run one game instance in autoplay mode."""
	game = game_cls(headless=headless)
	runner = AutoPlayRunner(game=game, max_frames=max_frames, on_frame=on_frame)
	return runner.run()
 
if __name__ == "__main__":
    from games.g2048 import Game2048
    variant=choose_random_variant(Game2048)
    print(f"Chosen variant: {variant.name}")
    run_human_debug(variant)