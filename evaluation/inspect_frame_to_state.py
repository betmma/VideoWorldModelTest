from __future__ import annotations

import argparse, json, os, sys
from typing import Any, Type

import cv2

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engineBase import GameBase
from evaluation.evaluator import pixelSimilarity, parseGameClass, readRgbFrame, resizeLike


def formatTime(frame_index: int, fps: float) -> str:
    """Format a frame index as mm:ss.cs."""
    centiseconds = round(frame_index * 100 / fps)
    minutes = centiseconds // 6000
    seconds = (centiseconds % 6000) // 100
    cs = centiseconds % 100
    return f"{minutes:02d}:{seconds:02d}.{cs:02d}"


def stateToJsonValue(state: Any) -> Any:
    """Return a JSON-writable version of a recovered state."""
    try:
        json.dumps(state, ensure_ascii=False)
        return state
    except TypeError:
        return repr(state)


def stateToText(state: Any) -> str:
    """Return compact text for a recovered state."""
    if state is None:
        return "None"
    if isinstance(state, str):
        return state
    return json.dumps(stateToJsonValue(state), ensure_ascii=False, default=str)


def clipText(text: str, width: int) -> str:
    """Clip long table cells without changing short text."""
    if len(text) <= width:
        return text
    return text[:width - 3] + "..."


def loadResultItem(results_json_path: str, item_index: int) -> tuple[str, str, str]:
    """Load game class and video paths from one item in a results.json file."""
    with open(results_json_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    item = results["items"][item_index]
    return results["gameClass"], item["groundTruthVideoPath"], item["generatedVideoPath"]


def inspectVideoStates(game_cls: Type[GameBase], gt_video_path: str, pred_video_path: str, start_frame: int = 0, max_frames: int | None = None) -> dict[str, Any]:
    """Run frameToState on paired video frames and return per-frame rows plus summary metrics."""
    game = game_cls(headless=True)
    gt_capture = cv2.VideoCapture(gt_video_path)
    pred_capture = cv2.VideoCapture(pred_video_path)
    gt_capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    pred_capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    fps = gt_capture.get(cv2.CAP_PROP_FPS)
    rows = []
    last_gt_state = None
    last_pred_state = None

    try:
        while max_frames is None or len(rows) < max_frames:
            gt_frame = readRgbFrame(gt_capture)
            pred_frame = readRgbFrame(pred_capture)
            if gt_frame is None or pred_frame is None:
                break

            pred_pixel_frame = resizeLike(pred_frame, gt_frame)
            gt_state = game.frameToState(gt_frame)
            pred_state = game.frameToState(pred_frame)
            match = game.statesMatch(gt_state, pred_state, last_gt_state, last_pred_state)
            rows.append({"frame": start_frame + len(rows), "time": formatTime(start_frame + len(rows), fps), "gtState": stateToJsonValue(gt_state), "predState": stateToJsonValue(pred_state), "match": match, "pixelSimilarity": pixelSimilarity(gt_frame, pred_pixel_frame)})
            last_gt_state = gt_state
            last_pred_state = pred_state
    finally:
        gt_capture.release()
        pred_capture.release()

    if not rows:
        raise RuntimeError("no frames were inspected")
    matches = sum(1 for row in rows if row["match"])
    pixel_average = sum(row["pixelSimilarity"] for row in rows) / len(rows)
    return {"summary": {"framesCompared": len(rows), "stateMatches": matches, "stateAccuracy": matches / len(rows), "pixelSimilarity": pixel_average}, "rows": rows}


def rowVisible(row: dict[str, Any], previous_visible: dict[str, Any] | None, only_mismatches: bool, only_changes: bool) -> bool:
    """Return whether a table row should be printed."""
    if only_mismatches and row["match"]:
        return False
    if only_changes and previous_visible is not None and row["gtState"] == previous_visible["gtState"] and row["predState"] == previous_visible["predState"] and row["match"] == previous_visible["match"]:
        return False
    return True


def printInspection(inspection: dict[str, Any], only_mismatches: bool = False, only_changes: bool = False) -> None:
    """Print an inspection summary and a compact table of frame states."""
    summary = inspection["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print()
    print(f"{'frame':>5} {'time':>8} {'gtState':<18} {'predState':<18} {'match':<5} {'pixel':>7}")
    previous_visible = None
    for row in inspection["rows"]:
        if not rowVisible(row, previous_visible, only_mismatches, only_changes):
            continue
        gt_text = clipText(stateToText(row["gtState"]), 18)
        pred_text = clipText(stateToText(row["predState"]), 18)
        match_text = "yes" if row["match"] else "no"
        print(f"{row['frame']:>5} {row['time']:>8} {gt_text:<18} {pred_text:<18} {match_text:<5} {row['pixelSimilarity']:>7.4f}")
        previous_visible = row


def writeInspection(output_json: str, inspection: dict[str, Any]) -> None:
    """Write inspection rows to a JSON file."""
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(inspection, f, ensure_ascii=False, indent=2)


def main() -> None:
    """Inspect frameToState results for one generated video."""
    parser = argparse.ArgumentParser(description="Show frameToState results for a generated video evaluation item.")
    parser.add_argument("--results-json", default=None, help="Pipeline results.json file. Use with --item-index.")
    parser.add_argument("--item-index", type=int, default=0, help="0-based item index inside results.json.")
    parser.add_argument("--game-class", default=None, help="Game module path; module.path:ClassName is also accepted.")
    parser.add_argument("--ground-truth-video", default=None)
    parser.add_argument("--generated-video", default=None)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--only-mismatches", action="store_true")
    parser.add_argument("--only-changes", action="store_true")
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    if args.results_json is not None:
        game_class, gt_video_path, pred_video_path = loadResultItem(args.results_json, args.item_index)
    else:
        if args.game_class is None or args.ground_truth_video is None or args.generated_video is None:
            parser.error("use --results-json, or provide --game-class, --ground-truth-video, and --generated-video")
        game_class = args.game_class
        gt_video_path = args.ground_truth_video
        pred_video_path = args.generated_video

    inspection = inspectVideoStates(parseGameClass(game_class), gt_video_path, pred_video_path, args.start_frame, args.max_frames)
    printInspection(inspection, args.only_mismatches, args.only_changes)
    if args.output_json is not None:
        writeInspection(args.output_json, inspection)


if __name__ == "__main__":
    main()
