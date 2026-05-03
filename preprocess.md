# HY-WorldPlay Training Data Preprocessing Notes

## Background

```
i cloned HY-WorldPlay/ in the workspace. i'm working on how to preprocess data for HY-WorldPlay training. 
i'm designing a game data synth pipeline and its output is:
one instance of data includes:
videoPath
imagePath
prompt
actions: list of per-frame dict with boolean keys W, A, S, D, LU, LD, LL, LR.
there is no camera pose data. must use discrete actions.

there are some data examples under /debug. each folder under it contains /images, /videos and data.json. data.json looks like:
[
  {
    "videoPath": "videos/000000.mp4",
    "imagePath": "images/000000.jpg",
    "prompt": "Rubik's Cube simulation. Use W/A/S/D to move the cursor across the visible faces. Moving the cursor over the edge will rotate the entire cube to reveal hidden faces. Use the Up/Left/Down/Right arrows to rotate the currently selected slice/layer.",
    "actions": [
      {
        "W": false,
        "A": false,
        "S": false,
        "D": false,
        "LU": false,
        "LL": false,
        "LD": false,
        "LR": false
      },
      ...
    ]
  },
  ...
]
```

Scope: this note only summarizes `HY-WorldPlay/` and `FastVideo/` findings relevant to preparing custom game data for HY-WorldPlay autoregressive training with discrete actions.

## High-level conclusion

HY-WorldPlay's training README describes a tensor dictionary, but the current training path does not consume one standalone JSON file containing tensors. It consumes an index JSON whose entries point to:

- one `.pt` tensor bundle
- one dense pose JSON
- one dense action JSON

The GameFactory preprocessing PR under `HY-WorldPlay/datasets/hy_preprocess/` is useful as a source of helper functions for encoding video, image, text, SigLIP, and ByT5 features. It is not directly usable for a custom game dataset with boolean per-frame controls and no real camera pose metadata.

## Actual training data shape

The launch script passes `--json_path ./preprocessed_gamefactory_f129/dataset_index.json`, not a tensor JSON object. Citation: `HY-WorldPlay/scripts/training/hyvideo15/run_ar_hunyuan_action_mem.sh:17-18`.

Each `dataset_index.json` row is written with `latent_path`, `pose_path`, `action_path`, and prompt metadata. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:981-991`.

The training loader reads:

- `json_data["latent_path"]`
- `json_data["pose_path"]`
- later `json_data["action_path"]`, but only inside a fragile path-name condition

Citations:

- `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:461-462`
- `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:516-519`

The `.pt` file must contain:

- `latent`
- `prompt_embeds`
- `prompt_mask`
- `byt5_text_states`
- `byt5_text_mask`
- `image_cond`
- `vision_states`

The preprocessing PR writes those keys before `torch.save`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:810-820`.

The loader later reads those same keys from `latent_pt`. Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:469-488`.

## Reusable preprocessing helpers

The GameFactory script contains useful reusable functions:

- `load_vae_model`: loads HunyuanVideo 1.5 VAE. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:32`.
- `load_text_encoder`: loads the LLM text encoder. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:58`.
- `load_vision_encoder`: loads SigLIP vision encoder. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:92`.
- `load_byt5_encoder`: loads ByT5/Glyph encoder. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:121`.
- `load_video_segment`: decodes a video frame range. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:176`.
- `resample_video_frames`: uniformly samples frames and returns source indices. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:202`.
- `encode_video_to_latent`: encodes video to VAE latents. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:242`.
- `encode_first_frame_to_latent`: encodes first frame to `image_cond`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:317`.
- `encode_prompt`: creates `prompt_embeds` and `prompt_mask`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:380`.
- `encode_first_frame`: creates SigLIP `vision_states`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:418`.
- `encode_byt5_prompt`: creates `byt5_text_states` and `byt5_text_mask`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:471`.

The video VAE encoder normalizes frames to `[-1, 1]`, uses `[B, C, T, H, W]`, samples the latent distribution, and multiplies by `vae.config.scaling_factor`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:295-314`.

The first-frame image latent uses VAE `latent_dist.mode()` and multiplies by the same scaling factor. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:372-377`.

## Pose JSON requirements

The loader expects dense pose keys and indexes pose at frame `0`, then `4 * (latent_index - 1) + 4` for later latent frames. Citations:

- requirement comment: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:7-11`
- loader indexing: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:496-503`

The GameFactory converter writes one pose entry per output video frame with:

```json
{
  "0": {
    "w2c": [[...], [...], [...], [...]],
    "intrinsic": [[...], [...], [...]]
  }
}
```

Citations:

- dense key requirement: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:610-612`
- fields written: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:663-666`

For games without camera pose, write identity `w2c` matrices and a stable fake intrinsic matrix. The PR script uses 60 degree FOV and image-center principal point to build intrinsics. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:631-637`.

Important caveat: memory frame selection uses pose/FOV overlap. Identity poses satisfy the file contract but make pose-based memory selection degenerate. Citation for memory selection call: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:611-619`.

## Action JSON requirements

The preprocessing script documents that each frame action JSON entry contains `move_action` and `view_action`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:7-11`.

The GameFactory converter writes:

```json
{
  "0": {
    "move_action": "WD",
    "view_action": "LR"
  }
}
```

Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:667-670`.

The loader reads action labels at the same temporal locations as pose: for latent action index `i`, it uses action key `4 * (i - 1) + 4`. Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:521-524`.

For per-frame boolean controls, you should either:

- populate every dense frame key and ensure terminal keys `4, 8, 12, ...` contain the representative action for that 4-frame latent interval, or
- patch the loader to aggregate actions across each 4-frame interval.

## `move_action` behavior

`move_action` is parsed by membership checks:

- contains `W` and not `S` means forward
- contains `S` and not `W` means backward
- contains `D` and not `A` means right
- contains `A` and not `D` means left

Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:523-532`.

The 4-bit mapping supports 9 translation labels:

- none
- W
- S
- D
- A
- W+D
- W+A
- S+D
- S+A

Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:391-400`.

Do not emit contradictory pairs such as `W+S` or `A+D`. The parser explicitly suppresses each contradictory axis.

## `view_action` behavior

Current action JSON parsing treats `view_action` as a single enum string. It does equality checks only:

- `"LR"` sets rotation bit 0
- `"LL"` sets rotation bit 1
- `"LU"` sets rotation bit 2
- `"LD"` sets rotation bit 3

Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:534-541`.

The GameFactory converter also emits only one of those strings or empty string. Yaw has priority; pitch is only checked in an `elif` branch when yaw is below threshold. Possible emitted values are therefore `""`, `"LL"`, `"LR"`, `"LD"`, `"LU"`. Citation: `HY-WorldPlay/datasets/hy_preprocess/preprocess_gamefactory_dataset.py:581-596`.

Therefore, with the current `action.json` loader, `view_action` does not support combination strings such as:

- `"LU+LL"`
- `"LULL"`
- `"LU LL"`
- `["LU", "LL"]`

Those values will not equal `"LR"`, `"LL"`, `"LU"`, or `"LD"`, so they will be parsed as no rotation.

Nuance: the internal 4-bit mapping can represent combined yaw+pitch labels, because the same 9-label mapping is used for rotation bits too. Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:391-400`.

The pose-derived fallback path can set a yaw bit and a pitch bit independently from relative camera pose, then maps that combined one-hot vector. Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:578-598`.

But that combined behavior is not exposed through `view_action` strings in the current action JSON branch. For your no-pose, discrete-action dataset, combined view actions require patching the loader.

Recommended patch direction if you want diagonal look:

- parse `view_action` as either a string or list
- set `LR`/`LL` bits by membership
- set `LU`/`LD` bits by membership
- reject contradictory `LR+LL` or `LU+LD`
- keep `action_for_pe = trans_one_label * 9 + rotate_one_label`

The transformer receives a flattened discrete `action` tensor and adds it through `self.action_in(action)`. Citations:

- training input passes `action`: `HY-WorldPlay/trainer/training/ar_hunyuan_mem_training_pipeline.py:454-457`
- transformer accepts `action`: `HY-WorldPlay/trainer/models/hyvideo/models/transformers/ar_action_hunyuanvideo_1_5_transformer.py:769`
- transformer applies action embedding: `HY-WorldPlay/trainer/models/hyvideo/models/transformers/ar_action_hunyuanvideo_1_5_transformer.py:830`

## Fragile action-path condition

The loader only reads `action_path` if the latent path string contains `latent_dataset_w_action`. Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:516-519`.

If that substring is absent, it ignores `action_path` and derives action labels from camera pose instead. Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:547-598`.

For a no-pose game dataset, this must be fixed. Better patch:

```python
if "action_path" in json_data and json_data["action_path"]:
    ...
else:
    ...
```

Temporary workaround: place latent files under a directory whose path contains `latent_dataset_w_action`.

## Negative prompt files

The dataset loader always loads:

- `./model_ckpts/hunyuan_neg_prompt.pt`
- `./model_ckpts/hunyuan_neg_byt5_prompt.pt`

Citation: `HY-WorldPlay/trainer/dataset/ar_camera_hunyuan_w_mem_dataset.py:405-413`.

The PR includes a helper that saves those files. Citations:

- `HY-WorldPlay/datasets/hy_preprocess/generate_neg_prompt_pt.py:56-57`
- `HY-WorldPlay/datasets/hy_preprocess/generate_neg_prompt_pt.py:79-84`

Potential bug: the helper dynamically imports `os.path.dirname(__file__) / "hy_preprocess" / "preprocess_gamefactory_dataset.py"`, but the file is already inside `datasets/hy_preprocess/`. That resolves to a nested non-existent `datasets/hy_preprocess/hy_preprocess/preprocess_gamefactory_dataset.py`. Citation: `HY-WorldPlay/datasets/hy_preprocess/generate_neg_prompt_pt.py:12-19`.

## FastVideo relevance

FastVideo documentation says its preprocessing precomputes text embeddings and VAE latents. Citation: `FastVideo/docs/training/data_preprocess.md:1-4`.

FastVideo outputs Parquet fields such as `vae_latent_bytes`, `text_embedding_bytes`, `clip_feature_bytes`, and `first_frame_latent_bytes`. Citation: `FastVideo/docs/training/data_preprocess.md:113-121`.

That is not the format consumed by HY-WorldPlay's current `CameraJsonWMemDataset`, which expects the `dataset_index.json` plus `.pt`, pose JSON, and action JSON layout above. Use FastVideo as conceptual reference, not as a direct output format for this training path.

## Recommended adapter for your dataset

Input instance:

```json
{
  "videoPath": "...mp4",
  "imagePath": "...png",
  "prompt": "...",
  "actions": [
    {"W": false, "A": false, "S": false, "D": false, "LU": false, "LD": false, "LL": false, "LR": false}
  ]
}
```

Output per segment:

1. Load video frames and optionally resample to a training frame count such as 129.
2. Encode video with `encode_video_to_latent`.
3. Encode prompt with `encode_prompt`.
4. Encode ByT5 with `encode_byt5_prompt`.
5. Encode `imagePath` or frame 0 with `encode_first_frame_to_latent` and `encode_first_frame`.
6. Write `.pt` containing all required tensor keys.
7. Write dense pose JSON with identity `w2c` and fake intrinsics.
8. Write dense action JSON with one entry per output video frame.
9. Write `dataset_index.json` pointing to the three artifacts.
10. Patch the loader so `action_path` is used without relying on the `latent_dataset_w_action` substring.

For `view_action`, choose one of two policies:

- Conservative, no loader patch: collapse view input to exactly one of `""`, `"LR"`, `"LL"`, `"LU"`, `"LD"`.
- Better for discrete game controls: patch the loader to parse combined yaw+pitch view controls, then allow combinations like `["LU", "LL"]`.

