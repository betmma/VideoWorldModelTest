from __future__ import annotations
from panda3d.core import loadPrcFileData

loadPrcFileData("", """
load-display pandagl
aux-display p3tinydisplay
window-type onscreen
win-size 854 480
sync-video false
""")

import argparse
from datetime import datetime
import importlib
import inspect
import json
import os
import re
from typing import Type

import cv2
import numpy as np

from engineBase import ActionState, BaseRunner, GameBase, choose_random_variant


def _get_autoplay_runner(game_cls: Type[GameBase]) -> Type[BaseRunner]:
    """Pick the concrete autoplay runner by detecting the engine base in the MRO.

    Lazy-imported so pygame-only runs don't pay the ursina/Panda3D import cost
    (and vice versa).
    """
    modules = {cls.__module__ for cls in game_cls.__mro__}
    if "ursinaBase" in modules:
        from ursinaRunner import UrsinaAutoPlayRunner
        return UrsinaAutoPlayRunner
    if "pygameBase" in modules:
        from pygameRunner import AutoPlayRunner
        return AutoPlayRunner
    raise TypeError(
        f"Cannot determine engine for {game_cls.__name__}: it does not inherit "
        "from pygameBase.GameBase or ursinaBase.UrsinaGameBase"
    )


def _parse_game_class(spec: str) -> Type[GameBase]:
    module_name, separator, class_name = spec.partition(":")
    if not module_name:
        raise ValueError("game class must include a module path")

    module = importlib.import_module(module_name)

    if separator:
        if not class_name:
            raise ValueError("game class must be in format module.path or module.path:ClassName")
        try:
            game_cls = getattr(module, class_name)
        except AttributeError as exc:
            raise ValueError(f"{module_name} has no class named {class_name}") from exc
        if not inspect.isclass(game_cls) or not issubclass(game_cls, GameBase):
            raise TypeError(f"{spec} is not a GameBase subclass")
        return game_cls

    game_classes = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__module__ == module.__name__
        and obj is not GameBase
        and issubclass(obj, GameBase)
    ]
    if len(game_classes) == 0:
        raise ValueError(f"No GameBase subclass defined in {module_name}")
    if len(game_classes) > 1:
        class_names = ", ".join(cls.__name__ for cls in game_classes)
        raise ValueError(
            f"Multiple GameBase subclasses defined in {module_name}: {class_names}. "
            "Use module.path:ClassName to choose one."
        )
    return game_classes[0]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-") or "game"


def _ensure_aspect(width: int, height: int) -> None:
    if width == 854 and height == 480:
        return
    ratio = width / height
    if abs(ratio - (16 / 9)) > 0.01:
        raise ValueError("width and height must be 16:9 (or default 854x480)")


def _action_copy(action: ActionState) -> ActionState:
    return {
        "W": bool(action["W"]),
        "A": bool(action["A"]),
        "S": bool(action["S"]),
        "D": bool(action["D"]),
        "LU": bool(action["LU"]),
        "LL": bool(action["LL"]),
        "LD": bool(action["LD"]),
        "LR": bool(action["LR"]),
    }


class _ClipRecorder:
    def __init__(
        self,
        width: int,
        height: int,
        fps: int,
        mode: str,
        video_abs: str,
        image_abs: str,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.mode = mode
        self.video_abs = video_abs
        self.image_abs = image_abs
        self.actions: list[ActionState] = []
        self.first_image_saved = False
        self.writer = self._create_writer(video_abs)

    def _create_writer(self, video_abs: str) -> cv2.VideoWriter:
        preferred_codecs = ["avc1", "mp4v"]
        for codec in preferred_codecs:
            writer = cv2.VideoWriter(
                video_abs,
                cv2.VideoWriter_fourcc(*codec),
                float(self.fps),
                (self.width, self.height),
            )
            if writer.isOpened():
                return writer
        raise RuntimeError("unable to open video writer with codecs avc1 or mp4v")

    def on_frame(self, frame_rgb: np.ndarray, action: ActionState, frame_index: int, ended_this_frame: bool) -> bool | None:
        """
        Receives the current frame as an HxWx3 uint8 RGB numpy array.
        grab_frame_rgb() on the runner is called internally before this
        callback, so no engine surface types appear here.
        """
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        if frame_bgr.shape[1] != self.width or frame_bgr.shape[0] != self.height:
            frame_bgr = cv2.resize(frame_bgr, (self.width, self.height), interpolation=cv2.INTER_AREA)

        if not self.first_image_saved:
            cv2.imwrite(self.image_abs, frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            self.first_image_saved = True

        self.writer.write(frame_bgr)
        self.actions.append(_action_copy(action))

        if self.mode == "session" and ended_this_frame:
            return False
        return True

    def close(self) -> None:
        self.writer.release()



def _record_one_clip(
    game_cls: Type[GameBase],
    run_dir: str,
    clip_id: int,
    mode: str,
    max_seconds: int,
    width: int,
    height: int,
    random_variant: bool,
) -> dict:
    selected_cls = choose_random_variant(game_cls) if random_variant else game_cls

    old_width = selected_cls.width
    old_height = selected_cls.height
    selected_cls.width = width
    selected_cls.height = height

    video_rel = f"videos/{clip_id:06d}.mp4"
    image_rel = f"images/{clip_id:06d}.jpg"
    video_abs = os.path.join(run_dir, video_rel)
    image_abs = os.path.join(run_dir, image_rel)

    game = selected_cls(headless=True)
    prompt = game.getPrompt()
    fps = int(game.fps)

    # Keep individual clips practical for preview and consistent with requirement.
    hard_cap_seconds = min(max_seconds, 600)
    max_frames = hard_cap_seconds * fps

    recorder = _ClipRecorder(
        width=width,
        height=height,
        fps=fps,
        mode=mode,
        video_abs=video_abs,
        image_abs=image_abs,
    )

    try:
        runner_cls = _get_autoplay_runner(selected_cls)
        runner = runner_cls(game=game, max_frames=max_frames, on_frame=recorder.on_frame)
        runner.run()
    finally:
        recorder.close()
        selected_cls.width = old_width
        selected_cls.height = old_height

    if not recorder.actions:
        raise RuntimeError("recorded clip has no frames")

    first = recorder.actions[0]
    if first["W"] or first["A"] or first["S"] or first["D"] or first["LU"] or first["LL"] or first["LD"] or first["LR"]:
        raise RuntimeError("actions[0] must be all false")

    return {
        "videoPath": video_rel.replace("\\", "/"),
        "imagePath": image_rel.replace("\\", "/"),
        "prompt": prompt,
        "actions": recorder.actions,
    }



def _build_run_dir(out_root: str, game_name: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = f"{stamp}_{_slugify(game_name)}"
    run_dir = os.path.join(out_root, folder)
    os.makedirs(os.path.join(run_dir, "videos"), exist_ok=False)
    os.makedirs(os.path.join(run_dir, "images"), exist_ok=False)
    return run_dir



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate autoplay dataset clips for a game.")
    parser.add_argument("--game-class", required=True, help="Game module path; module.path:ClassName is also accepted")
    parser.add_argument("--output-root", default="generated_data", help="Directory where run folder is created")
    parser.add_argument("--mode", choices=["timelimit", "session"], default="timelimit")
    parser.add_argument("--count", type=int, default=1, help="How many clips to generate")
    parser.add_argument("--max-seconds", type=int, default=120, help="Per-video max duration in seconds")
    parser.add_argument("--width", type=int, default=854)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--random-variant", action="store_true", help="Pick random subclass variant for each clip")
    args = parser.parse_args()

    _ensure_aspect(args.width, args.height)
    if args.max_seconds <= 0:
        raise ValueError("max-seconds must be > 0")
    if args.count <= 0:
        raise ValueError("count must be > 0")

    game_cls = _parse_game_class(args.game_class)
    os.makedirs(args.output_root, exist_ok=True)
    run_dir = _build_run_dir(args.output_root, game_cls.name)

    items = []
    for clip_id in range(args.count):
        item = _record_one_clip(
            game_cls=game_cls,
            run_dir=run_dir,
            clip_id=clip_id,
            mode=args.mode,
            max_seconds=args.max_seconds,
            width=args.width,
            height=args.height,
            random_variant=args.random_variant,
        )
        items.append(item)
        print(f"Generated clip {clip_id + 1}/{args.count}: {item['videoPath']}")

    data_json = os.path.join(run_dir, "data.json")
    with open(data_json, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Saved run folder: {run_dir}")


if __name__ == "__main__":
    main()
