# MiniMax H3 I2V Turbo · RunPod Serverless

上传 **首帧 + 提示词** → MiniMax H3 **FL2VA 图生视频+音频**（4-step Turbo LoRA + PromptEnhancer）。

## 镜像（RunPod 请用 Docker Hub 短名）

```text
<Hub用户名>/minimax-h3:latest
```

> 已换短名 `minimax-h3`。勿用 `ghcr.io/...`。CI / Secrets 见 [DEPLOY.md](./DEPLOY.md)。

部署步骤见 **[DEPLOY.md](./DEPLOY.md)**。

## 工作流要点

- `UNETLoader` FL2VA → `LoraLoaderModelOnly` turbo（节点 7，strength 1.0）
- `CLIPLoader` Heretic INT8 + `MiniMaxH3GenerationTailLoader` + `MiniMaxH3PromptEnhancer`（I2VA 默认）
- `MiniMaxH3ImageToVideo`：122 增强 prompt → 104
- `BasicScheduler` steps=4 · `LoadImage` 50/51 首/尾帧
- 帧数：`max(5,round(d*24))+(5-(…)%17)%17`（与 i2v.json 一致）

## Volume 布局（~60GB）

```text
/runpod-volume/models/
  diffusion_models/MiniMax-H3/minimax_h3_fl2va_pruned_int8_convrot.safetensors
  text_encoders/MiniMax-H3/qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors
  text_encoders/MiniMax-H3/qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors
  vae/MiniMax-H3/minimax_h3_video_vae_fp16.safetensors
  vae/MiniMax-H3/minimax_h3_audio_vae_fp32.safetensors
  loras/minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors
```

> Turbo LoRA 使用 **drbaph pruned 兼容版**（与 FL2VA `pruned_int8` 基座匹配）。勿用 t8star 的非 pruned `T8-convert`（会 AdaLN shape 报错并打崩 ComfyUI）。
## 调用

```bash
python3 build_request.py \
  --image ./first.jpg \
  --prompt "Cinematic scene, camera pans slowly..." \
  --width 768 --height 512 --duration 5 --steps 4 \
  --out request.json

python3 send_request.py --request request.json --mode run --out-dir ./output
```

可选：`--last-frame ./last.jpg` · `--skip-enhancer` · `--seed 42`

本地菜单：双击 **`选中执行_MiniMaxH3New.command`**  
Web UI：`Exe_UI/minimax_h3_new/`（端口 **8769**）

## 环境变量（Serverless 日常）

```text
VOLUME_ROOT=/runpod-volume
DOWNLOAD_MODELS_ON_START=0
REQUIRE_MODELS=1
```

## ComfyUI / 自定义节点

- 镜像内 ComfyUI **≥0.30**（当前 pin `v0.33.1`）：原生 `MiniMaxH3ImageToVideo` / `VAEDecodeAudio` / `CreateVideo` / `SaveVideo`
- `ComfyUI-MiniMax-H3-Guide`：`MiniMaxH3PromptEnhancer` / `MiniMaxH3GenerationTailLoader`
- `comfyui-art-venture`：`ComfyMathExpression`（镜像内含 `opencv-python-headless`）
