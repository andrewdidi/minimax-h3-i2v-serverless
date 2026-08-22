#!/usr/bin/env bash
# 官方 worker 入口：先准备 Volume 模型，校验通过后再 exec /start.sh
set -euo pipefail

echo "[minimax-h3-i2v] prepare volume models…"
if ! bash /comfyui/prepare_volume_models.sh; then
  echo "[minimax-h3-i2v] ERROR: prepare_volume_models 失败 — Worker 不会进入 ready"
  echo "[minimax-h3-i2v]   请用临时 Pod 填盘: bash /comfyui/pod_fill_volume.sh"
  echo "[minimax-h3-i2v]   Endpoint 日常: VOLUME_ROOT=/runpod-volume DOWNLOAD_MODELS_ON_START=0 REQUIRE_MODELS=1"
  echo "[minimax-h3-i2v]   详见仓库 DEPLOY.md"
  exit 1
fi

if [[ -x /start.sh ]]; then
  exec /start.sh "$@"
fi
if [[ -x /start_serverless.sh ]]; then
  exec /start_serverless.sh "$@"
fi

echo "[minimax-h3-i2v] WARN: /start.sh missing, running handler directly"
exec python3 -u /handler.py
