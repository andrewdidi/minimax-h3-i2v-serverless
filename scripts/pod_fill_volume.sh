#!/usr/bin/env bash
# 临时 Pod 填盘：bash /comfyui/pod_fill_volume.sh
set -euo pipefail

export VOLUME_ROOT="${VOLUME_ROOT:-/runpod-volume}"
export DOWNLOAD_MODELS_ON_START=1
export REQUIRE_MODELS=1
export ALLOW_MISSING_MODELS=0
export HF_TOKEN="${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}"
export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"

COMFY="${COMFY_ROOT:-/comfyui}"
[[ -f "${COMFY}/download_models.py" ]] || COMFY=/comfyui

echo "============================================================"
echo "[minimax-h3-i2v] Pod 填盘开始（不启动 Comfy）"
echo "  VOLUME_ROOT=$VOLUME_ROOT"
if [[ -n "${HF_TOKEN}" ]]; then echo "  HF_TOKEN: set"; else echo "  HF_TOKEN: empty"; fi
echo "============================================================"

if [[ ! -d "$VOLUME_ROOT" ]]; then
  echo "[minimax-h3-i2v] ERROR: VOLUME_ROOT 不存在: $VOLUME_ROOT"
  echo "  请在 RunPod 挂载 Network Volume → /runpod-volume（≥120GB）"
  exit 1
fi

df -h "$VOLUME_ROOT" || true

if [[ -x "${COMFY}/download_to_volume.sh" ]]; then
  bash "${COMFY}/download_to_volume.sh"
elif [[ -x "${COMFY}/prepare_volume_models.sh" ]]; then
  bash "${COMFY}/prepare_volume_models.sh"
else
  echo "[minimax-h3-i2v] ERROR: 找不到 download_to_volume.sh / prepare_volume_models.sh"
  exit 1
fi

echo ""
echo "############################################################"
echo "########## DOWNLOAD_COMPLETE ##########"
echo "下载完成"
echo "[minimax-h3-i2v] Volume 模型已齐全并通过校验 — 可以 Stop 临时 Pod"
echo "下一步（Serverless Endpoint）:"
echo "  1. 关掉本临时 Pod"
echo "  2. Endpoint 挂载同一 Volume → /runpod-volume"
echo "  3. 环境变量:"
echo "       VOLUME_ROOT=/runpod-volume"
echo "       DOWNLOAD_MODELS_ON_START=0"
echo "       REQUIRE_MODELS=1"
echo "  4. Redeploy → 日志应出现: Volume 模型已齐全 → 跳过下载"
echo "############################################################"

KEEP_ALIVE="${KEEP_ALIVE:-1}"
if [[ "$KEEP_ALIVE" == "1" ]]; then
  echo "[minimax-h3-i2v] KEEP_ALIVE=1 → sleep infinity（已见 DOWNLOAD_COMPLETE 即可 Stop Pod）"
  exec sleep infinity
fi
