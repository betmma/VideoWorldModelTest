#!/usr/bin/env python3
"""Preprocess local debug game rollouts for HY-WorldPlay training.

The input layout is the debug dataset produced by this repo:

    debug/<run_id>/
      data.json
      images/000000.jpg
      videos/000000.mp4

The output layout matches HY-WorldPlay's CameraJsonWMemDataset index format:

    preprocessed/
      dataset_index.json
      latent_dataset_w_action/<segment_id>/
        <segment_id>_latent.pt
        <segment_id>_pose.json
        <segment_id>_action.json
        <segment_id>_first_frame.jpg

Long source videos are split into random overlapping clips. Every clip starts
on a multiple-of-4 source frame, has a 4n+1 frame count, and shares its first
frame with the previous clip's last frame.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
import os
import random
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Sequence, Tuple


LOGGER = logging.getLogger("preprocess_debug_hyworldplay")
ACTION_KEYS = ("W", "A", "S", "D", "LU", "LD", "LL", "LR")
DEFAULT_VIEW_PRIORITY = ("LR", "LL", "LU", "LD")


class ClipSpec(NamedTuple):
    """Frame range for one overlapping training clip."""

    clip_idx: int
    start_frame: int
    frame_count: int
    source_frame_count: int
    usable_frame_count: int


class ParallelContext(NamedTuple):
    """torchrun process information for clip-level sharding."""

    enabled: bool
    rank: int
    local_rank: int
    world_size: int
    initialized: bool

    @property
    def is_main(self) -> bool:
        return self.rank == 0


class PlannedClip(NamedTuple):
    """One clip preprocessing task with a stable global order."""

    task_idx: int
    sample_dir: Path
    item_idx: int
    sample: Dict[str, Any]
    clip_spec: ClipSpec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess ./debug game rollouts into HY-WorldPlay training data."
    )
    parser.add_argument(
        "--input_dir",
        type=Path,
        default=Path("debug"),
        help="Root containing debug run folders with data.json, images/, and videos/.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("preprocessed"),
        help="Directory where dataset_index.json and artifacts are written.",
    )
    parser.add_argument(
        "--output_json",
        default="dataset_index.json",
        help="Index filename written under output_dir.",
    )
    parser.add_argument(
        "--hy_worldplay_dir",
        type=Path,
        default=Path("HY-WorldPlay"),
        help="Path to the cloned HY-WorldPlay repository.",
    )
    parser.add_argument(
        "--model_path",
        type=Path,
        default=Path("model_ckpts/HunyuanVideo-1.5"),
        help="Path to HunyuanVideo-1.5 checkpoint directory.",
    )
    parser.add_argument("--device", default="cuda", help="Device for model encoding.")
    parser.add_argument("--target_height", type=int, default=480)
    parser.add_argument("--target_width", type=int, default=832)
    parser.add_argument(
        "--clip_min_frames",
        type=int,
        default=125,
        help="Minimum output frames per split clip. The effective value is rounded up to 4n+1.",
    )
    parser.add_argument(
        "--clip_max_frames",
        type=int,
        default=637,
        help="Maximum output frames per split clip. The effective value is rounded down to 4n+1.",
    )
    parser.add_argument(
        "--split_seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible clip lengths.",
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=None,
        help="Only process the first N samples after sorting, for quick tests.",
    )
    parser.add_argument(
        "--view_priority",
        default=",".join(DEFAULT_VIEW_PRIORITY),
        help="Priority used when multiple LU/LD/LL/LR booleans are true. HY-WorldPlay's current action loader accepts only one view_action string.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove output_dir before preprocessing.",
    )
    parser.add_argument(
        "--parallel",
        "--distributed",
        dest="distributed",
        action="store_true",
        help="Shard clips across torchrun processes. This is also enabled automatically when WORLD_SIZE > 1.",
    )
    parser.add_argument(
        "--dist_backend",
        default="gloo",
        help="torch.distributed backend used only for process barriers in parallel preprocessing.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Validate inputs and print the samples that would be processed.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    rank = os.environ.get("RANK")
    rank_prefix = f"[rank {rank}] " if rank is not None else ""
    logging.basicConfig(level=logging.INFO, format=f"%(levelname)s: {rank_prefix}%(message)s")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def init_parallel_context(args: argparse.Namespace) -> ParallelContext:
    """Initialize torch.distributed when torchrun is driving multiple processes."""
    world_size = env_int("WORLD_SIZE", 1)
    rank = env_int("RANK", 0)
    local_rank = env_int("LOCAL_RANK", rank)
    enabled = bool(args.distributed or world_size > 1)

    if not enabled:
        return ParallelContext(False, 0, 0, 1, False)
    if world_size < 1:
        raise ValueError(f"WORLD_SIZE must be positive, got {world_size}")
    if not 0 <= rank < world_size:
        raise ValueError(f"RANK must be in [0, {world_size}), got {rank}")

    initialized = False
    if world_size > 1:
        import torch.distributed as dist

        if not dist.is_initialized():
            dist.init_process_group(backend=args.dist_backend)
            initialized = True

    return ParallelContext(True, rank, local_rank, world_size, initialized)


def parallel_barrier(parallel: ParallelContext) -> None:
    if not parallel.enabled or parallel.world_size <= 1:
        return
    import torch.distributed as dist

    if dist.is_available() and dist.is_initialized():
        dist.barrier()


def finalize_parallel_context(parallel: ParallelContext) -> None:
    if not parallel.initialized:
        return
    import torch.distributed as dist

    if dist.is_available() and dist.is_initialized():
        dist.destroy_process_group()


def resolve_process_device(device: str, parallel: ParallelContext) -> str:
    """Map --device cuda to cuda:<LOCAL_RANK> under torchrun."""
    if parallel.enabled and parallel.world_size > 1 and device == "cuda":
        resolved_device = f"cuda:{parallel.local_rank}"
        try:
            import torch

            torch.cuda.set_device(parallel.local_rank)
        except Exception:
            LOGGER.warning(
                "Could not set CUDA device to local rank %s; continuing with %s",
                parallel.local_rank,
                resolved_device,
            )
        return resolved_device

    if parallel.enabled and parallel.world_size > 1 and device.startswith("cuda:"):
        LOGGER.warning(
            "Using explicit --device %s on every rank. Use --device cuda to map ranks to cuda:<LOCAL_RANK>.",
            device,
        )
    return device


def import_hy_preprocess(hy_worldplay_dir: Path):
    hy_worldplay_dir = hy_worldplay_dir.resolve()
    preprocess_path = (
        hy_worldplay_dir / "datasets" / "hy_preprocess" / "preprocess_gamefactory_dataset.py"
    )
    if not preprocess_path.exists():
        raise FileNotFoundError(f"HY preprocessing script not found: {preprocess_path}")

    sys.path.insert(0, str(hy_worldplay_dir))
    spec = importlib.util.spec_from_file_location(
        "hy_preprocess_gamefactory_dataset", preprocess_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import {preprocess_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_debug_samples(input_dir: Path) -> List[Tuple[Path, int, Dict[str, Any]]]:
    """Load samples from a debug root or a single debug run directory."""
    samples: List[Tuple[Path, int, Dict[str, Any]]] = []
    data_paths = [input_dir / "data.json"] if (input_dir / "data.json").exists() else sorted(input_dir.glob("*/data.json"))
    for data_path in data_paths:
        with data_path.open("r", encoding="utf-8") as f:
            rows = json.load(f)
        if not isinstance(rows, list):
            raise ValueError(f"{data_path} must contain a JSON list")
        for item_idx, item in enumerate(rows):
            samples.append((data_path.parent, item_idx, item))
    return samples


def require_sample_files(sample_dir: Path, sample: Dict[str, Any]) -> Tuple[Path, Path]:
    missing_keys = [key for key in ("videoPath", "imagePath", "prompt", "actions") if key not in sample]
    if missing_keys:
        raise ValueError(f"{sample_dir}/data.json sample is missing keys: {missing_keys}")

    video_path = sample_dir / sample["videoPath"]
    image_path = sample_dir / sample["imagePath"]
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not isinstance(sample["actions"], list):
        raise ValueError(f"actions must be a list in {sample_dir}/data.json")
    return video_path, image_path


def sample_id(sample_dir: Path, item_idx: int, sample: Dict[str, Any]) -> str:
    video_stem = Path(str(sample.get("videoPath", f"{item_idx:06d}"))).stem
    return f"{sample_dir.name}_{item_idx:03d}_{video_stem}"


def sample_clip_id(sample_dir: Path, item_idx: int, sample: Dict[str, Any], clip_spec: ClipSpec) -> str:
    """Build a stable segment id for a split clip."""
    base_id = sample_id(sample_dir, item_idx, sample)
    return f"{base_id}_clip{clip_spec.clip_idx:04d}_f{clip_spec.start_frame:06d}"


def make_intrinsic(target_height: int, target_width: int) -> List[List[float]]:
    focal = target_width / (2.0 * math.tan(math.radians(60.0) / 2.0))
    return [
        [focal, 0.0, target_width / 2.0],
        [0.0, focal, target_height / 2.0],
        [0.0, 0.0, 1.0],
    ]


def sanitize_bool_action(action: Dict[str, Any]) -> Dict[str, bool]:
    return {key: bool(action.get(key, False)) for key in ACTION_KEYS}


def action_to_move_string(action: Dict[str, bool]) -> str:
    move = ""
    if action["W"] and not action["S"]:
        move += "W"
    elif action["S"] and not action["W"]:
        move += "S"

    if action["D"] and not action["A"]:
        move += "D"
    elif action["A"] and not action["D"]:
        move += "A"
    return move


def action_to_view_string(action: Dict[str, bool], view_priority: Sequence[str]) -> str:
    candidates = set()
    if action["LR"] and not action["LL"]:
        candidates.add("LR")
    elif action["LL"] and not action["LR"]:
        candidates.add("LL")

    if action["LU"] and not action["LD"]:
        candidates.add("LU")
    elif action["LD"] and not action["LU"]:
        candidates.add("LD")

    for key in view_priority:
        if key in candidates:
            return key
    return ""


def get_action_for_source_frame(actions: Sequence[Dict[str, Any]], source_idx: int) -> Dict[str, bool]:
    if not actions:
        return {key: False for key in ACTION_KEYS}
    clamped_idx = min(max(int(source_idx), 0), len(actions) - 1)
    return sanitize_bool_action(actions[clamped_idx])


def blank_action() -> Dict[str, bool]:
    """Return the required no-op action for frame 0 of each clip."""
    return {key: False for key in ACTION_KEYS}


def align_frame_count_up(frame_count: int) -> int:
    """Return the smallest 4n+1 frame count greater than or equal to frame_count."""
    remainder = (frame_count - 1) % 4
    if remainder == 0:
        return frame_count
    return frame_count + 4 - remainder


def align_frame_count_down(frame_count: int) -> int:
    """Return the largest 4n+1 frame count less than or equal to frame_count."""
    return frame_count - ((frame_count - 1) % 4)


def choose_clip_frame_count(remaining_advance: int, min_frames: int, max_frames: int, rng: random.Random) -> int:
    """Choose a random 4n+1 clip length that leaves a valid suffix when possible."""
    max_advance = max_frames - 1
    min_advance = min_frames - 1
    if remaining_advance <= max_advance and remaining_advance < min_advance * 2:
        return remaining_advance + 1

    candidates = list(range(min_advance, min(max_advance, remaining_advance) + 1, 4))
    good_candidates = [advance for advance in candidates if can_partition_advance(remaining_advance - advance, min_advance, max_advance)]
    if can_partition_advance(remaining_advance, min_advance, max_advance) and remaining_advance >= min_advance * 2:
        good_candidates = [advance for advance in good_candidates if advance < remaining_advance]
    if not good_candidates:
        raise ValueError(f"Cannot split remaining {remaining_advance + 1} frames into clips between {min_frames} and {max_frames} frames")
    return rng.choice(good_candidates) + 1


def can_partition_advance(advance: int, min_advance: int, max_advance: int) -> bool:
    """Return whether an advance length can be composed from valid clip advances."""
    if advance == 0:
        return True
    if advance < min_advance:
        return False
    min_parts = math.ceil(advance / max_advance)
    max_parts = advance // min_advance
    return min_parts <= max_parts


def get_video_frame_count(video_path: Path) -> int:
    """Return the decoded video's frame count from OpenCV metadata."""
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()


def plan_clip_specs(source_frame_count: int, action_count: int, min_frames: int, max_frames: int, rng: random.Random) -> List[ClipSpec]:
    """Split one video into overlapping clips whose lengths are 4n+1."""
    usable_frame_count = min(source_frame_count, action_count)
    usable_frame_count = align_frame_count_down(usable_frame_count)
    if usable_frame_count < min_frames:
        raise ValueError(f"Video has {source_frame_count} frame(s) and {action_count} action(s), but needs at least {min_frames} usable frame(s)")

    specs: List[ClipSpec] = []
    start_frame = 0
    remaining_advance = usable_frame_count - 1
    while remaining_advance > 0:
        frame_count = choose_clip_frame_count(remaining_advance, min_frames, max_frames, rng)
        specs.append(ClipSpec(len(specs), start_frame, frame_count, source_frame_count, usable_frame_count))
        start_frame += frame_count - 1
        remaining_advance -= frame_count - 1
    return specs


def clip_actions(actions: Sequence[Dict[str, Any]], start_frame: int, frame_count: int) -> List[Dict[str, bool]]:
    """Return a per-frame action slice with clip-local action 0 forced blank."""
    clipped = [sanitize_bool_action(action) for action in actions[start_frame : start_frame + frame_count]]
    clipped[0] = blank_action()
    return clipped


def extract_first_frame_tensor(video_frames):
    """Return frame 0 from an already decoded clip tensor."""
    import torch

    first_frame = video_frames[0]
    if hasattr(first_frame, "detach"):
        return first_frame.detach().cpu()
    return torch.as_tensor(first_frame)


def build_pose_and_action_dicts(
    actions: Sequence[Dict[str, Any]],
    source_frame_indices: Sequence[int],
    target_height: int,
    target_width: int,
    view_priority: Sequence[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    intrinsic = make_intrinsic(target_height, target_width)
    identity_w2c = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]

    pose_dict: Dict[str, Any] = {}
    action_dict: Dict[str, Any] = {}
    for out_idx, source_idx in enumerate(source_frame_indices):
        action = get_action_for_source_frame(actions, source_idx)
        pose_dict[str(out_idx)] = {
            "w2c": identity_w2c,
            "intrinsic": intrinsic,
        }
        action_dict[str(out_idx)] = {
            "move_action": action_to_move_string(action),
            "view_action": action_to_view_string(action, view_priority),
        }
    return pose_dict, action_dict


def save_image_tensor(image_path: Path, image_tensor) -> None:
    """Save an RGB HWC uint8 tensor or array as a JPEG image."""
    import numpy as np
    from PIL import Image

    if hasattr(image_tensor, "detach"):
        image_tensor = image_tensor.detach().cpu().numpy()
    image_array = np.asarray(image_tensor, dtype=np.uint8)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image_array).save(image_path, quality=95)


def validate_view_priority(raw_priority: str) -> Tuple[str, ...]:
    priority = tuple(part.strip() for part in raw_priority.split(",") if part.strip())
    invalid = sorted(set(priority) - {"LR", "LL", "LU", "LD"})
    if invalid:
        raise ValueError(f"Invalid view_priority entries: {invalid}")
    if not priority:
        raise ValueError("view_priority cannot be empty")
    return priority


def validate_clip_frame_range(min_frames: int, max_frames: int) -> Tuple[int, int]:
    """Validate and align the requested random clip frame range."""
    if min_frames <= 0 or max_frames <= 0:
        raise ValueError("clip_min_frames and clip_max_frames must be positive")
    min_frames = align_frame_count_up(min_frames)
    max_frames = align_frame_count_down(max_frames)
    if min_frames < 5:
        raise ValueError("clip_min_frames must allow at least 5 frames after 4n+1 alignment")
    if max_frames < min_frames:
        raise ValueError("clip_max_frames must be greater than or equal to clip_min_frames after 4n+1 alignment")
    return min_frames, max_frames


def path_for_json(path: Path) -> str:
    return path.as_posix()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def flatten_planned_clips(
    planned_samples: Sequence[Tuple[Path, int, Dict[str, Any], Path, Path, List[ClipSpec]]]
) -> List[PlannedClip]:
    tasks: List[PlannedClip] = []
    for sample_dir, item_idx, sample, _, _, clip_specs in planned_samples:
        for clip_spec in clip_specs:
            tasks.append(
                PlannedClip(
                    task_idx=len(tasks),
                    sample_dir=sample_dir,
                    item_idx=item_idx,
                    sample=sample,
                    clip_spec=clip_spec,
                )
            )
    return tasks


def shard_tasks(tasks: Sequence[PlannedClip], parallel: ParallelContext) -> List[PlannedClip]:
    if not parallel.enabled or parallel.world_size <= 1:
        return list(tasks)
    return [task for task in tasks if task.task_idx % parallel.world_size == parallel.rank]


def rank_index_path(output_json_path: Path, rank: int) -> Path:
    return output_json_path.with_name(f".{output_json_path.name}.rank{rank:05d}.json")


def merge_rank_indexes(output_json_path: Path, world_size: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rank in range(world_size):
        path = rank_index_path(output_json_path, rank)
        if not path.exists():
            raise FileNotFoundError(f"Missing rank index file: {path}")
        with path.open("r", encoding="utf-8") as f:
            rank_rows = json.load(f)
        if not isinstance(rank_rows, list):
            raise ValueError(f"Rank index file must contain a JSON list: {path}")
        rows.extend(rank_rows)

    rows.sort(key=lambda row: int(row["task_index"]))
    for row in rows:
        row.pop("task_index", None)
    write_json(output_json_path, rows)
    return rows


def preprocess_clip(
    pre,
    sample_dir: Path,
    item_idx: int,
    sample: Dict[str, Any],
    clip_spec: ClipSpec,
    args: argparse.Namespace,
    view_priority: Sequence[str],
    vae,
    text_encoders,
    vision_encoders,
    byt5_encoders,
) -> Dict[str, Any]:
    video_path, image_path = require_sample_files(sample_dir, sample)
    segment_id = sample_clip_id(sample_dir, item_idx, sample, clip_spec)
    segment_dir = args.output_dir / "latent_dataset_w_action" / segment_id
    segment_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info(
        "Loading clip frames: %s start=%s frames=%s",
        video_path,
        clip_spec.start_frame,
        clip_spec.frame_count,
    )
    video_frames = pre.load_video_segment(str(video_path), clip_spec.start_frame, clip_spec.start_frame + clip_spec.frame_count - 1)
    output_frame_count = int(video_frames.shape[0])
    if output_frame_count != clip_spec.frame_count:
        raise ValueError(f"{segment_id} decoded {output_frame_count} frame(s), expected {clip_spec.frame_count}")
    source_indices = list(range(output_frame_count))
    clipped_actions = clip_actions(sample["actions"], clip_spec.start_frame, output_frame_count)

    LOGGER.info(
        "Encoding %s: source frames %s-%s -> %s output frames",
        segment_id,
        clip_spec.start_frame,
        clip_spec.start_frame + output_frame_count - 1,
        output_frame_count,
    )
    latent = pre.encode_video_to_latent(
        vae,
        video_frames,
        target_height=args.target_height,
        target_width=args.target_width,
        device=args.device,
    )

    prompt = str(sample["prompt"])
    prompt_embeds = pre.encode_prompt(prompt, text_encoders, device=args.device)
    byt5_embeds = pre.encode_byt5_prompt(prompt, byt5_encoders, device=args.device)

    first_frame = extract_first_frame_tensor(video_frames)
    first_frame_path = segment_dir / f"{segment_id}_first_frame.jpg"
    save_image_tensor(first_frame_path, first_frame)
    image_cond = pre.encode_first_frame_to_latent(
        vae,
        first_frame,
        args.target_height,
        args.target_width,
        device=args.device,
    )
    vision_states = pre.encode_first_frame(
        first_frame,
        vision_encoders,
        args.target_height,
        args.target_width,
        device=args.device,
    )

    pose_dict, action_dict = build_pose_and_action_dicts(
        clipped_actions,
        source_indices,
        target_height=args.target_height,
        target_width=args.target_width,
        view_priority=view_priority,
    )

    pose_path = segment_dir / f"{segment_id}_pose.json"
    action_path = segment_dir / f"{segment_id}_action.json"
    latent_path = segment_dir / f"{segment_id}_latent.pt"
    write_json(pose_path, pose_dict)
    write_json(action_path, action_dict)

    import torch

    torch.save(
        {
            "latent": latent,
            "prompt_embeds": prompt_embeds["prompt_embeds"],
            "prompt_mask": prompt_embeds["prompt_mask"],
            "byt5_text_states": byt5_embeds["byt5_text_states"],
            "byt5_text_mask": byt5_embeds["byt5_text_mask"],
            "image_cond": image_cond,
            "vision_states": vision_states["vision_states"],
        },
        latent_path,
    )

    return {
        "segment_id": segment_id,
        "source_dir": path_for_json(sample_dir),
        "video_path": path_for_json(video_path),
        "source_image_path": path_for_json(image_path),
        "image_path": path_for_json(first_frame_path),
        "clip_index": clip_spec.clip_idx,
        "source_start_frame": clip_spec.start_frame,
        "source_end_frame": clip_spec.start_frame + output_frame_count - 1,
        "num_source_frames": clip_spec.source_frame_count,
        "num_usable_source_frames": clip_spec.usable_frame_count,
        "num_output_frames": output_frame_count,
        "num_source_actions": len(sample["actions"]),
        "num_output_actions": len(clipped_actions),
        "target_height": args.target_height,
        "target_width": args.target_width,
        "latent_path": path_for_json(latent_path),
        "pose_path": path_for_json(pose_path),
        "action_path": path_for_json(action_path),
        "prompt": prompt,
    }


def preprocess_task(
    pre,
    task: PlannedClip,
    args: argparse.Namespace,
    view_priority: Sequence[str],
    vae,
    text_encoders,
    vision_encoders,
    byt5_encoders,
) -> Dict[str, Any]:
    row = preprocess_clip(
        pre,
        task.sample_dir,
        task.item_idx,
        task.sample,
        task.clip_spec,
        args,
        view_priority,
        vae,
        text_encoders,
        vision_encoders,
        byt5_encoders,
    )
    row["task_index"] = task.task_idx
    return row


def main() -> None:
    configure_logging()
    args = parse_args()
    parallel = init_parallel_context(args)
    try:
        args.device = resolve_process_device(args.device, parallel)
        if parallel.enabled and parallel.world_size > 1 and args.split_seed is None:
            LOGGER.warning(
                "Parallel preprocessing needs identical clip planning on every rank; using --split_seed 0."
            )
            args.split_seed = 0

        run_main(args, parallel)
    finally:
        finalize_parallel_context(parallel)


def run_main(args: argparse.Namespace, parallel: ParallelContext) -> None:
    view_priority = validate_view_priority(args.view_priority)
    clip_min_frames, clip_max_frames = validate_clip_frame_range(args.clip_min_frames, args.clip_max_frames)
    rng = random.Random(args.split_seed)

    samples = load_debug_samples(args.input_dir)
    if args.num_samples is not None:
        samples = samples[: args.num_samples]
    if not samples:
        raise SystemExit(f"No debug samples found under {args.input_dir}")

    planned_samples: List[Tuple[Path, int, Dict[str, Any], Path, Path, List[ClipSpec]]] = []
    for sample_dir, item_idx, sample in samples:
        video_path, image_path = require_sample_files(sample_dir, sample)
        source_frame_count = get_video_frame_count(video_path)
        clip_specs = plan_clip_specs(source_frame_count, len(sample["actions"]), clip_min_frames, clip_max_frames, rng)
        planned_samples.append((sample_dir, item_idx, sample, video_path, image_path, clip_specs))

    tasks = flatten_planned_clips(planned_samples)
    rank_tasks = shard_tasks(tasks, parallel)

    if args.dry_run:
        if parallel.is_main:
            LOGGER.info("Found %s sample(s), planned %s split clip(s)", len(samples), len(tasks))
            LOGGER.info("Clip frame range after 4n+1 alignment: %s-%s", clip_min_frames, clip_max_frames)
            if parallel.enabled:
                LOGGER.info("Parallel plan: rank %s/%s would process %s clip(s)", parallel.rank, parallel.world_size, len(rank_tasks))
            for sample_dir, item_idx, sample, video_path, image_path, clip_specs in planned_samples:
                LOGGER.info(
                    "%s: video=%s image=%s frames=%s usable_frames=%s actions=%s clips=%s",
                    sample_id(sample_dir, item_idx, sample),
                    video_path,
                    image_path,
                    clip_specs[0].source_frame_count,
                    clip_specs[0].usable_frame_count,
                    len(sample["actions"]),
                    len(clip_specs),
                )
                for clip_spec in clip_specs[:10]:
                    LOGGER.info(
                        "  clip %s: start=%s end=%s frames=%s",
                        clip_spec.clip_idx,
                        clip_spec.start_frame,
                        clip_spec.start_frame + clip_spec.frame_count - 1,
                        clip_spec.frame_count,
                    )
                if len(clip_specs) > 10:
                    LOGGER.info("  ... %s more clip(s)", len(clip_specs) - 10)
        elif parallel.enabled:
            LOGGER.info("Parallel plan: rank %s/%s would process %s clip(s)", parallel.rank, parallel.world_size, len(rank_tasks))
        return

    if args.overwrite and parallel.is_main and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    parallel_barrier(parallel)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pre = import_hy_preprocess(args.hy_worldplay_dir)
    LOGGER.info("Loading HY-WorldPlay encoders from %s on %s", args.model_path, args.device)
    vae = pre.load_vae_model(str(args.model_path), device=args.device)
    text_encoders = pre.load_text_encoder(str(args.model_path), device=args.device)
    vision_encoders = pre.load_vision_encoder(str(args.model_path), device=args.device)
    byt5_encoders = pre.load_byt5_encoder(str(args.model_path), device=args.device)

    index: List[Dict[str, Any]] = []
    output_json_path = args.output_dir / args.output_json
    rank_output_json_path = rank_index_path(output_json_path, parallel.rank) if parallel.enabled else output_json_path
    LOGGER.info(
        "Processing %s of %s planned clip(s)",
        len(rank_tasks),
        len(tasks),
    )

    for task in rank_tasks:
        try:
            row = preprocess_task(
                pre,
                task,
                args,
                view_priority,
                vae,
                text_encoders,
                vision_encoders,
                byt5_encoders,
            )
            index.append(row)
            write_json(rank_output_json_path, index)
        except Exception:
            LOGGER.exception(
                "Failed to preprocess %s item %s clip %s",
                task.sample_dir,
                task.item_idx,
                task.clip_spec.clip_idx,
            )
            raise

    write_json(rank_output_json_path, index)
    LOGGER.info("Wrote %s rank-local sample(s) to %s", len(index), rank_output_json_path)

    parallel_barrier(parallel)
    if parallel.enabled and parallel.is_main:
        merged_index = merge_rank_indexes(output_json_path, parallel.world_size)
        LOGGER.info("Merged %s sample(s) to %s", len(merged_index), output_json_path)
    elif not parallel.enabled:
        for row in index:
            row.pop("task_index", None)
        write_json(output_json_path, index)
        LOGGER.info("Wrote %s sample(s) to %s", len(index), output_json_path)
    parallel_barrier(parallel)


if __name__ == "__main__":
    main()
