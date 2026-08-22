#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_ROOT="${COMFY_ROOT:-${ROOT}}"
[[ -f /comfyui/download_models.py ]] && COMFY_ROOT=/comfyui

export VOLUME_ROOT="${VOLUME_ROOT:-/runpod-volume}"
export DOWNLOAD_MODELS_ON_START=1
export REQUIRE_MODELS=1
export ALLOW_MISSING_MODELS=0
export HF_TOKEN="${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}"
export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"

echo "[minimax-h3-i2v] download_to_volume VOLUME_ROOT=$VOLUME_ROOT COMFY_ROOT=$COMFY_ROOT"

if [[ -x "${COMFY_ROOT}/prepare_volume_models.sh" ]]; then
  bash "${COMFY_ROOT}/prepare_volume_models.sh"
elif [[ -x "${ROOT}/scripts/prepare_volume_models.sh" ]]; then
  export COMFY_ROOT="${ROOT}"
  export MANIFEST="${ROOT}/models_manifest.json"
  mkdir -p "${VOLUME_ROOT}/models"
  bash "${ROOT}/scripts/prepare_volume_models.sh"
else
  echo "找不到 prepare_volume_models.sh"
  exit 1
fi

MANIFEST="${MANIFEST:-${COMFY_ROOT}/models_manifest.json}"
VERIFY="${COMFY_ROOT}/verify_models.py"
[[ -f "$VERIFY" ]] || VERIFY="${ROOT}/verify_models.py"
echo "[minimax-h3-i2v] 最终校验: python3 verify_models.py --root $VOLUME_ROOT --strict"
python3 "$VERIFY" --root "$VOLUME_ROOT" --manifest "$MANIFEST" --strict

echo ""
echo "[minimax-h3-i2v] ✅ Volume 模型已就绪。"
echo "[minimax-h3-i2v] Serverless Endpoint 必须设:"
echo "    VOLUME_ROOT=/runpod-volume"
echo "    DOWNLOAD_MODELS_ON_START=0"
echo "    REQUIRE_MODELS=1"
