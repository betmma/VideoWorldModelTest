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
pip install pygame-ce ursina opencv-python-headless
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
cd ..
```

The script prints the resolved checkpoint paths. Use the printed `MODEL_PATH` as `--model_path` when preprocessing, or place/symlink the printed paths at the defaults used by the commands below. `WORLDPLAY_PATH` is the directory that contains `ar_model`, `bidirectional_model`, and `ar_distilled_action_model`.

```bash
mkdir -p model_ckpts
ln -s "$MODEL_PATH" model_ckpts/HunyuanVideo-1.5
ln -s "$WORLDPLAY_PATH" model_ckpts/HY-WorldPlay
```

HY training also loads negative prompt tensors from `./model_ckpts`. Generate them after the HunyuanVideo checkpoint is available:

```bash
conda activate VBMT
python HY-WorldPlay/datasets/hy_preprocess/generate_neg_prompt_pt.py \
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

```bash
conda activate VBMT
python preprocess_debug_hyworldplay.py \
  --input_dir ./debug \
  --output_dir ./preprocessed \
  --model_path ./model_ckpts/HunyuanVideo-1.5 \
  --target_num_frames 129 \
  --device cuda
```

Quick input validation without loading model checkpoints:

```bash
conda activate VBMT
python preprocess_debug_hyworldplay.py --dry_run
```
