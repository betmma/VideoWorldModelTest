# Clone HY-WorldPlay
```bash
git clone https://github.com/betmma/HY-WorldPlay.git
cd HY-WorldPlay
git checkout pr-47
cd ..
```

# System packages

```bash
apt-get install -y xvfb
apt-get install -y parallel
```

# Python environments

Use `VWMT` for local game-data generation:

```bash
conda create -n VWMT python=3.14 -y
conda activate VWMT
pip install pygame-ce ursina opencv-python-headless requests
```

Use `VBMT` for HY-WorldPlay preprocessing and training (could fail on game-data generation):

```bash
conda create -n VBMT python=3.10 -y
conda activate VBMT
pip install -r requirements.txt
```

# Model checkpoints

HY-WorldPlay preprocessing needs HunyuanVideo-1.5 plus the text, vision, and ByT5 encoders. The HY script downloads all required pieces; the vision encoder needs a Hugging Face token with access to `black-forest-labs/FLUX.1-Redux-dev`.

```bash
conda activate VBMT
cd HY-WorldPlay
python download_models.py --hf_token "$HF_TOKEN"
cd ..
```

If you do not have FLUX access yet, this downloads everything except the vision encoder:

```bash
conda activate VBMT
cd HY-WorldPlay
python download_models.py --skip_vision_encoder
```

The script prints the resolved checkpoint paths. Use the printed `MODEL_PATH` as `--model_path` when preprocessing.

Copy models to a more convenient place:

```bash
mkdir model_ckpts
cp -rL /root/.cache/huggingface/hub/models--tencent--HunyuanVideo-1.5/snapshots/9b49404b3f5df2a8f0b31df27a0c7ab872e7b038 model_ckpts/HunyuanVideo-1.5
cp -rL /root/.cache/huggingface/hub/models--tencent--HY-WorldPlay/snapshots/f4c29235647707b571479a69b569e4166f9f5bf8 model_ckpts/HY-WorldPlay    
```

HY training also loads negative prompt tensors from `./model_ckpts`. Generate them after the HunyuanVideo checkpoint is available:

```bash
conda activate VBMT
cd HY-WorldPlay
python datasets/hy_preprocess/generate_neg_prompt_pt.py \
  --model_path ./model_ckpts/HunyuanVideo-1.5 \
  --output_dir ./model_ckpts \
  --device cuda
```

# Create virtual display

```bash
Xvfb :99 -screen 0 854x480x24 &
export DISPLAY=:99
```

# Generate debug data

```bash
python generateAutoplayDataset.py --game-class games.marbleMaze:MarbleMazeUrsina --output-root debug --max-seconds 10
```

# Preprocess debug data for HY-WorldPlay

This writes HY-WorldPlay training artifacts to `./preprocessed`, including `dataset_index.json`, `.pt` tensor bundles, dense identity-pose JSON, and dense discrete-action JSON.
Long source videos are split into random overlapping clips. Clip lengths are aligned to `4n+1` frames, and the last frame of each clip is reused as the first frame of the next clip.

```bash
conda activate VBMT
python preprocess_debug_hyworldplay.py \
  --input_dir ./debug \
  --output_dir ./preprocessed \
  --model_path ./model_ckpts/HunyuanVideo-1.5 \
  --clip_min_frames 125 \
  --clip_max_frames 637 \
  --device cuda
```

To preprocess across multiple GPUs, launch one process per GPU with `torchrun`.
The script shards split clips by rank, maps `--device cuda` to `cuda:<LOCAL_RANK>`, writes rank-local temporary index files, and rank 0 merges them into `dataset_index.json`.
Use `--overwrite` only once in the `torchrun` command; rank 0 removes the old output directory before the other ranks start writing.

```bash
conda activate VBMT
torchrun --standalone --nproc_per_node=8 preprocess_debug_hyworldplay.py \
  --parallel \
  --input_dir ./debug \
  --output_dir ./preprocessed \
  --model_path ./model_ckpts/HunyuanVideo-1.5 \
  --clip_min_frames 125 \
  --clip_max_frames 637 \
  --split_seed 0 \
  --overwrite \
  --device cuda
```

Set `--nproc_per_node` to the number of GPUs to use, or restrict visible GPUs first:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 torchrun --standalone --nproc_per_node=4 preprocess_debug_hyworldplay.py \
  --parallel \
  --input_dir ./debug \
  --output_dir ./preprocessed \
  --model_path ./model_ckpts/HunyuanVideo-1.5 \
  --split_seed 0 \
  --device cuda
```

Quick input validation without loading model checkpoints:

```bash
conda activate VBMT
python preprocess_debug_hyworldplay.py --input_dir ./debug --dry_run
python preprocess_debug_hyworldplay.py --input_dir ./.debugSplit/20260506_123546_841086_sokoban --dry_run
```
