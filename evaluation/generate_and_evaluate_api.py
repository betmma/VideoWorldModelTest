from __future__ import annotations

import argparse, json, os, platform, subprocess, sys
from datetime import datetime
from typing import Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.api import MODEL_NAME, generate_video_output_multiple_tries
from evaluation.evaluator import evaluateVideos, parseGameClass


ACTION_KEYS = ("W", "A", "S", "D", "LU", "LL", "LD", "LR")
ACTION_LABELS = {
    "W": "W key",
    "A": "A key",
    "S": "S key",
    "D": "D key",
    "LU": "Up arrow key",
    "LL": "Left arrow key",
    "LD": "Down arrow key",
    "LR": "Right arrow key",
}


def formatTime(frame_index: int, fps: int) -> str:
    """Format a frame index as mm:ss.cs."""
    centiseconds = round(frame_index * 100 / fps)
    minutes = centiseconds // 6000
    seconds = (centiseconds % 6000) // 100
    cs = centiseconds % 100
    return f"{minutes:02d}:{seconds:02d}.{cs:02d}"


def actionsToText(actions: list[dict[str, bool]], fps: int = 30) -> str:
    """Convert per-frame action dicts into compact prompt text."""
    runs = []
    for key in ACTION_KEYS:
        frame_index = 0
        while frame_index < len(actions):
            if not actions[frame_index].get(key, False):
                frame_index += 1
                continue
            start = frame_index
            while frame_index + 1 < len(actions) and actions[frame_index + 1].get(key, False):
                frame_index += 1
            end = frame_index
            runs.append((start, end, key))
            frame_index += 1
    if not runs:
        return "No key is pressed down during this clip."
    lines = []
    for start, end, key in sorted(runs, key=lambda run: (run[0], ACTION_KEYS.index(run[2]))):
        label = ACTION_LABELS[key]
        if end == start:
            lines.append(f"At {formatTime(start, fps)}, {label} is pressed down")
        else:
            lines.append(f"From {formatTime(start, fps)} to {formatTime(end + 1, fps)}, {label} is pressed down and held")
    return "\n".join(lines)


def makePrompt(base_prompt: str, actions: list[dict[str, bool]], fps: int = 30) -> str:
    """Combine the game's rule prompt with the action timeline."""
    return f"{base_prompt}\n\nAction data:\n{actionsToText(actions, fps)}"


def runCommand(command: list[str]) -> None:
    """Run a subprocess command and fail if it fails."""
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)


def newestDataDir(output_root: str) -> str:
    """Return the newest child directory containing data.json."""
    candidates = []
    for name in os.listdir(output_root):
        path = os.path.join(output_root, name)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "data.json")):
            candidates.append(path)
    if not candidates:
        raise RuntimeError(f"No generated data folder with data.json found in {output_root}")
    return max(candidates, key=os.path.getmtime)


def generateDataset(args: argparse.Namespace) -> str:
    """Generate an autoplay dataset and return its run directory."""
    before = set(os.listdir(args.generated_data_root)) if os.path.isdir(args.generated_data_root) else set()
    command = [
        sys.executable,
        "generateAutoplayDataset.py",
        "--game-class",
        args.game_class,
        "--output-root",
        args.generated_data_root,
        "--max-seconds",
        str(args.max_seconds),
        "--count",
        str(args.count),
        "--mode",
        args.mode,
    ]
    if args.random_variant:
        command.append("--random-variant")
    if platform.system().lower() == "linux" and not args.no_xvfb:
        command = ["xvfb-run", "-a", "-s", "-screen 0 854x480x24", *command]
    runCommand(command)
    after = set(os.listdir(args.generated_data_root))
    new_dirs = [os.path.join(args.generated_data_root, name) for name in after - before if os.path.isdir(os.path.join(args.generated_data_root, name)) and os.path.exists(os.path.join(args.generated_data_root, name, "data.json"))]
    if new_dirs:
        return max(new_dirs, key=os.path.getmtime)
    return newestDataDir(args.generated_data_root)


def resolveDataDir(data_dir: str) -> str:
    """Return a directory that contains data.json, accepting a parent folder too."""
    if os.path.exists(os.path.join(data_dir, "data.json")):
        return data_dir
    return newestDataDir(data_dir)


def loadDataItems(data_dir: str, limit: int | None) -> list[dict[str, Any]]:
    """Load dataset items from data.json."""
    with open(os.path.join(data_dir, "data.json"), "r", encoding="utf-8") as f:
        items = json.load(f)
    if limit is not None:
        items = items[:limit]
    return items


def findGeneratedVideo(api_output_dir: str) -> str | None:
    """Find the first generated video file in an API output directory."""
    metadata_path = os.path.join(api_output_dir, "metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        videos = metadata.get("artifacts", {}).get("videos", [])
        if videos:
            video_path = videos[0]
            return video_path if os.path.isabs(video_path) else os.path.abspath(video_path)
    for root, _, filenames in os.walk(api_output_dir):
        for filename in filenames:
            if filename.lower().endswith((".mp4", ".webm", ".mov", ".mkv")):
                return os.path.abspath(os.path.join(root, filename))
    return None


def makeRunDir(output_root: str, game_class: str) -> str:
    """Create the evaluation output directory."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    game_name = game_class.replace(":", "_").replace(".", "_")
    run_dir = os.path.join(output_root, f"{stamp}_{game_name}")
    os.makedirs(run_dir, exist_ok=False)
    return run_dir


def evaluateItem(game_cls, data_dir: str, item: dict[str, Any], item_index: int, args: argparse.Namespace) -> dict[str, Any]:
    """Generate one video with the API and evaluate it against the ground truth clip."""
    image_path = os.path.abspath(os.path.join(data_dir, item["imagePath"]))
    gt_video_path = os.path.abspath(os.path.join(data_dir, item["videoPath"]))
    prompt = makePrompt(item["prompt"], item["actions"], args.fps)
    api_output_dir = generate_video_output_multiple_tries(image_path, prompt, attempts=args.api_attempts)
    generated_video_path = findGeneratedVideo(api_output_dir)
    result = {"index": item_index, "imagePath": image_path, "groundTruthVideoPath": gt_video_path, "prompt": prompt, "apiOutputDir": os.path.abspath(api_output_dir), "generatedVideoPath": generated_video_path, "evaluation": None, "error": None}
    if generated_video_path is None:
        result["error"] = "No generated video file found in API output directory"
        return result
    try:
        result["evaluation"] = evaluateVideos(game_cls, gt_video_path, generated_video_path, max_frames=args.eval_max_frames)
    except Exception as error:
        result["error"] = str(error)
    return result


def writeResults(run_dir: str, data: dict[str, Any]) -> None:
    """Write pipeline results to results.json."""
    with open(os.path.join(run_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    """Run data generation, API video generation, and frameToState evaluation."""
    parser = argparse.ArgumentParser(description="Generate or reuse game data, call the video API, and evaluate generated videos with frameToState.")
    parser.add_argument("--game-class", required=True, help="Game module path; module.path:ClassName is also accepted")
    parser.add_argument("--data-dir", default=None, help="Existing dataset run folder containing data.json, or a parent folder whose newest child contains data.json")
    parser.add_argument("--generated-data-root", default=".debugApiEvalData", help="Where fresh data is generated when --data-dir is omitted")
    parser.add_argument("--output-root", default=os.path.join("evaluation", "api_eval"), help="Where results.json is written")
    parser.add_argument("--count", type=int, default=10, help="Number of clips to generate or consume")
    parser.add_argument("--max-seconds", type=int, default=10, help="Fresh generated clip length in seconds")
    parser.add_argument("--mode", choices=["timelimit", "session"], default="timelimit")
    parser.add_argument("--random-variant", action="store_true")
    parser.add_argument("--no-xvfb", action="store_true", help="Do not prefix the data generator with xvfb-run on Linux")
    parser.add_argument("--fps", type=int, default=30, help="FPS used to convert action frame indexes into prompt timestamps")
    parser.add_argument("--api-attempts", type=int, default=1)
    parser.add_argument("--eval-max-frames", type=int, default=300, help="Default 300 because grok-video-3-15s generates 10 second videos at 30 fps")
    args = parser.parse_args()

    data_dir = resolveDataDir(args.data_dir) if args.data_dir is not None else generateDataset(args)
    items = loadDataItems(data_dir, args.count)
    game_cls = parseGameClass(args.game_class)
    run_dir = makeRunDir(args.output_root, args.game_class)
    results = {"gameClass": args.game_class, "modelName": MODEL_NAME, "dataDir": os.path.abspath(data_dir), "outputDir": os.path.abspath(run_dir), "items": []}
    writeResults(run_dir, results)
    for index, item in enumerate(items):
        item_result = evaluateItem(game_cls, data_dir, item, index, args)
        results["items"].append(item_result)
        writeResults(run_dir, results)
        print(f"Finished {index + 1}/{len(items)}")
    print(f"Saved results: {os.path.join(run_dir, 'results.json')}")


if __name__ == "__main__":
    main()
