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
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


LOGGER = logging.getLogger("preprocess_debug_hyworldplay")
ACTION_KEYS = ("W", "A", "S", "D", "LU", "LD", "LL", "LR")
DEFAULT_VIEW_PRIORITY = ("LR", "LL", "LU", "LD")


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
        "--target_num_frames",
        type=int,
        default=129,
        help="Uniformly resample each video to this many frames. Use 129 for HY defaults.",
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
        help=(
            "Priority used when multiple LU/LD/LL/LR booleans are true. "
            "HY-WorldPlay's current action loader accepts only one view_action string."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove output_dir before preprocessing.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Validate inputs and print the samples that would be processed.",
    )
    return parser.parse_args()


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
    samples: List[Tuple[Path, int, Dict[str, Any]]] = []
    for data_path in sorted(input_dir.glob("*/data.json")):
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


def load_image_tensor(image_path: Path):
    import numpy as np
    import torch
    from PIL import Image

    image = Image.open(image_path).convert("RGB")
    return torch.from_numpy(np.asarray(image, dtype=np.uint8))


def validate_view_priority(raw_priority: str) -> Tuple[str, ...]:
    priority = tuple(part.strip() for part in raw_priority.split(",") if part.strip())
    invalid = sorted(set(priority) - {"LR", "LL", "LU", "LD"})
    if invalid:
        raise ValueError(f"Invalid view_priority entries: {invalid}")
    if not priority:
        raise ValueError("view_priority cannot be empty")
    return priority


def path_for_json(path: Path) -> str:
    return path.as_posix()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def preprocess_sample(
    pre,
    sample_dir: Path,
    item_idx: int,
    sample: Dict[str, Any],
    args: argparse.Namespace,
    view_priority: Sequence[str],
    vae,
    text_encoders,
    vision_encoders,
    byt5_encoders,
) -> Dict[str, Any]:
    video_path, image_path = require_sample_files(sample_dir, sample)
    segment_id = sample_id(sample_dir, item_idx, sample)
    segment_dir = args.output_dir / "latent_dataset_w_action" / segment_id
    segment_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Loading video frames: %s", video_path)
    video_frames = pre.load_video_segment(str(video_path), 0, 10**12)
    source_frame_count = int(video_frames.shape[0])
    video_frames, source_indices = pre.resample_video_frames(
        video_frames, target_num_frames=args.target_num_frames
    )
    output_frame_count = int(video_frames.shape[0])

    LOGGER.info(
        "Encoding %s: %s source frames -> %s output frames",
        segment_id,
        source_frame_count,
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

    first_frame = load_image_tensor(image_path)
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
        sample["actions"],
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
        "image_path": path_for_json(image_path),
        "num_source_frames": source_frame_count,
        "num_output_frames": output_frame_count,
        "num_source_actions": len(sample["actions"]),
        "target_height": args.target_height,
        "target_width": args.target_width,
        "latent_path": path_for_json(latent_path),
        "pose_path": path_for_json(pose_path),
        "action_path": path_for_json(action_path),
        "prompt": prompt,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    view_priority = validate_view_priority(args.view_priority)

    samples = load_debug_samples(args.input_dir)
    if args.num_samples is not None:
        samples = samples[: args.num_samples]
    if not samples:
        raise SystemExit(f"No debug samples found under {args.input_dir}")

    for sample_dir, item_idx, sample in samples:
        require_sample_files(sample_dir, sample)

    if args.dry_run:
        LOGGER.info("Found %s sample(s)", len(samples))
        for sample_dir, item_idx, sample in samples:
            video_path, image_path = require_sample_files(sample_dir, sample)
            LOGGER.info(
                "%s: video=%s image=%s actions=%s",
                sample_id(sample_dir, item_idx, sample),
                video_path,
                image_path,
                len(sample["actions"]),
            )
        return

    if args.overwrite and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pre = import_hy_preprocess(args.hy_worldplay_dir)
    LOGGER.info("Loading HY-WorldPlay encoders from %s", args.model_path)
    vae = pre.load_vae_model(str(args.model_path), device=args.device)
    text_encoders = pre.load_text_encoder(str(args.model_path), device=args.device)
    vision_encoders = pre.load_vision_encoder(str(args.model_path), device=args.device)
    byt5_encoders = pre.load_byt5_encoder(str(args.model_path), device=args.device)

    index: List[Dict[str, Any]] = []
    output_json_path = args.output_dir / args.output_json
    for sample_dir, item_idx, sample in samples:
        try:
            row = preprocess_sample(
                pre,
                sample_dir,
                item_idx,
                sample,
                args,
                view_priority,
                vae,
                text_encoders,
                vision_encoders,
                byt5_encoders,
            )
            index.append(row)
            write_json(output_json_path, index)
        except Exception:
            LOGGER.exception("Failed to preprocess %s item %s", sample_dir, item_idx)
            raise

    write_json(output_json_path, index)
    LOGGER.info("Wrote %s sample(s) to %s", len(index), output_json_path)


if __name__ == "__main__":
    main()
