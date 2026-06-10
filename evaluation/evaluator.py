from __future__ import annotations

import argparse, importlib, inspect, json, os, sys
from typing import Any, Type

import cv2, numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engineBase import GameBase


def parseGameClass(spec: str) -> Type[GameBase]:
    """Load a GameBase subclass from module.path or module.path:ClassName."""
    module_name, separator, class_name = spec.partition(":")
    if not module_name:
        raise ValueError("game class must include a module path")

    module = importlib.import_module(module_name)

    if separator:
        if not class_name:
            raise ValueError("game class must be in format module.path or module.path:ClassName")
        game_cls = getattr(module, class_name)
        if not inspect.isclass(game_cls) or not issubclass(game_cls, GameBase):
            raise TypeError(f"{spec} is not a GameBase subclass")
        return game_cls

    game_classes = [obj for _, obj in inspect.getmembers(module, inspect.isclass) if obj.__module__ == module.__name__ and obj is not GameBase and issubclass(obj, GameBase)]
    if len(game_classes) == 0:
        raise ValueError(f"No GameBase subclass defined in {module_name}")
    if len(game_classes) > 1:
        class_names = ", ".join(cls.__name__ for cls in game_classes)
        raise ValueError(f"Multiple GameBase subclasses defined in {module_name}: {class_names}. Use module.path:ClassName to choose one.")
    return game_classes[0]


def hasStateEvaluator(game: GameBase) -> bool:
    """Return whether the game overrides frameToState."""
    return game.frameToState.__func__ is not GameBase.frameToState


def readRgbFrame(capture: cv2.VideoCapture) -> np.ndarray | None:
    """Read one RGB frame from an OpenCV capture."""
    ok, frame_bgr = capture.read()
    if not ok:
        return None
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def resizeLike(frame_rgb: np.ndarray, reference_rgb: np.ndarray) -> np.ndarray:
    """Resize a frame to the reference frame size when needed."""
    if frame_rgb.shape[:2] == reference_rgb.shape[:2]:
        return frame_rgb
    return cv2.resize(frame_rgb, (reference_rgb.shape[1], reference_rgb.shape[0]), interpolation=cv2.INTER_AREA)


def pixelSimilarity(gt_rgb: np.ndarray, pred_rgb: np.ndarray) -> float:
    """Return normalized average per-pixel similarity between two RGB frames."""
    difference = np.abs(gt_rgb.astype(np.int16) - pred_rgb.astype(np.int16))
    return 1.0 - float(np.mean(difference)) / 255.0


def evaluateVideos(game_cls: Type[GameBase], gt_video_path: str, pred_video_path: str, max_frames: int | None = None) -> dict[str, Any]:
    """Compare a ground truth video and generated video with pixel and optional state metrics."""
    game = game_cls(headless=True)
    gt_capture = cv2.VideoCapture(gt_video_path)
    pred_capture = cv2.VideoCapture(pred_video_path)
    if not gt_capture.isOpened():
        raise RuntimeError(f"unable to open ground truth video: {gt_video_path}")
    if not pred_capture.isOpened():
        raise RuntimeError(f"unable to open generated video: {pred_video_path}")

    use_state = hasStateEvaluator(game)
    frame_count = 0
    pixel_total = 0.0
    state_compared = 0
    state_matches = 0
    last_gt_state = None
    last_pred_state = None

    try:
        while max_frames is None or frame_count < max_frames:
            gt_frame = readRgbFrame(gt_capture)
            pred_frame = readRgbFrame(pred_capture)
            if gt_frame is None or pred_frame is None:
                break

            pred_frame = resizeLike(pred_frame, gt_frame)
            pixel_total += pixelSimilarity(gt_frame, pred_frame)

            if use_state:
                gt_state = game.frameToState(gt_frame)
                pred_state = game.frameToState(pred_frame)
                if game.statesMatch(gt_state, pred_state, last_gt_state, last_pred_state):
                    state_matches += 1
                state_compared += 1
                last_gt_state = gt_state
                last_pred_state = pred_state

            frame_count += 1
    finally:
        gt_capture.release()
        pred_capture.release()

    if frame_count == 0:
        raise RuntimeError("no frames were compared")

    result = {"framesCompared": frame_count, "pixelSimilarity": pixel_total / frame_count, "stateEvaluator": use_state}
    if use_state:
        result["stateFramesCompared"] = state_compared
        result["stateMatches"] = state_matches
        result["stateAccuracy"] = state_matches / state_compared
    return result


def main() -> None:
    """Run video evaluation from the command line."""
    parser = argparse.ArgumentParser(description="Evaluate generated gameplay video against ground truth video.")
    parser.add_argument("--game-class", required=True, help="Game module path; module.path:ClassName is also accepted")
    parser.add_argument("--ground-truth-video", required=True)
    parser.add_argument("--generated-video", required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    game_cls = parseGameClass(args.game_class)
    result = evaluateVideos(game_cls, args.ground_truth_video, args.generated_video, args.max_frames)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json is not None:
        with open(args.output_json, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
