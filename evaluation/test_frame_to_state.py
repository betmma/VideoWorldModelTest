from __future__ import annotations

import argparse, json, os, sys
from typing import Any, Type

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engineBase import ActionState, BaseRunner, GameBase
from evaluation.evaluator import parseGameClass


def hasFrameState(game_cls: Type[GameBase]) -> bool:
    """Return whether the game class overrides frameToState."""
    return game_cls.frameToState is not GameBase.frameToState


def hasExpectedFrameState(game_cls: Type[GameBase]) -> bool:
    """Return whether the game class overrides expectedFrameToState."""
    return game_cls.expectedFrameToState is not GameBase.expectedFrameToState


def getAutoplayRunner(game_cls: Type[GameBase]) -> Type[BaseRunner]:
    """Pick the concrete autoplay runner for a GameBase subclass."""
    modules = {cls.__module__ for cls in game_cls.__mro__}
    if "ursinaBase" in modules:
        from ursinaRunner import UrsinaAutoPlayRunner
        return UrsinaAutoPlayRunner
    if "pygameBase" in modules:
        from pygameRunner import AutoPlayRunner
        return AutoPlayRunner
    raise TypeError(f"Cannot determine engine for {game_cls.__name__}")


def toJsonable(value: Any) -> Any:
    """Convert common state values into JSON-friendly values."""
    if isinstance(value, dict):
        return {str(key): toJsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [toJsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def actionToDict(action: ActionState) -> dict[str, bool]:
    """Copy an action state into a normal dict."""
    return {key: bool(value) for key, value in action.items()}


def jitterFrame(frame_rgb: np.ndarray, jitter: float, rng: np.random.Generator) -> np.ndarray:
    """Apply deterministic per-channel RGB jitter to a frame."""
    if jitter <= 0:
        return frame_rgb
    amount = round(255 * jitter)
    noise = rng.integers(-amount, amount + 1, size=frame_rgb.shape, dtype=np.int16)
    return np.clip(frame_rgb.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def testFrameToState(game_cls: Type[GameBase], max_frames: int, max_failures: int, jitter: float, jitter_seed: int) -> dict[str, Any]:
    """Run autoplay frames and compare frameToState(frame) with expectedFrameToState()."""
    if not hasFrameState(game_cls):
        raise RuntimeError(f"{game_cls.__name__} does not override frameToState")
    if not hasExpectedFrameState(game_cls):
        raise RuntimeError(f"{game_cls.__name__} does not override expectedFrameToState")

    game = game_cls(headless=True)
    rng = np.random.default_rng(jitter_seed)
    frames_tested = 0
    matches = 0
    failures = []
    last_expected_state = None
    last_actual_state = None

    def on_frame(frame_rgb: np.ndarray, action: ActionState, frame_index: int, ended_this_frame: bool) -> bool:
        """Check one rendered frame."""
        nonlocal frames_tested, matches, last_expected_state, last_actual_state
        expected_state = game.expectedFrameToState()
        actual_state = game.frameToState(jitterFrame(frame_rgb, jitter, rng))
        matched = game.statesMatch(expected_state, actual_state, last_expected_state, last_actual_state)
        if matched:
            matches += 1
        elif len(failures) < max_failures:
            failures.append({"frame": frame_index, "action": actionToDict(action), "expected": toJsonable(expected_state), "actual": toJsonable(actual_state)})
        frames_tested += 1
        last_expected_state = expected_state
        last_actual_state = actual_state
        return True

    runner_cls = getAutoplayRunner(game_cls)
    runner = runner_cls(game=game, max_frames=max_frames, on_frame=on_frame)
    runner.run()

    if frames_tested == 0:
        raise RuntimeError("no frames were tested")

    return {"game": game_cls.__name__, "jitter": jitter, "jitterSeed": jitter_seed, "framesTested": frames_tested, "matches": matches, "accuracy": matches / frames_tested, "failures": failures}


def main() -> None:
    """Run frameToState parser testing from the command line."""
    parser = argparse.ArgumentParser(description="Test a game's frameToState implementation against expectedFrameToState during autoplay.")
    parser.add_argument("--game-class", required=True, help="Game module path; module.path:ClassName is also accepted")
    parser.add_argument("--max-frames", type=int, default=120)
    parser.add_argument("--max-failures", type=int, default=20)
    parser.add_argument("--jitter", type=float, default=0.0, help="Per-channel RGB jitter as a fraction of 255; 0.01 means about +-3.")
    parser.add_argument("--jitter-seed", type=int, default=0)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    game_cls = parseGameClass(args.game_class)
    result = testFrameToState(game_cls, args.max_frames, args.max_failures, args.jitter, args.jitter_seed)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json is not None:
        with open(args.output_json, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
