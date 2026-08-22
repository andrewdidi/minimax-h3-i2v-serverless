#!/usr/bin/env bash
# Network Volume → /comfyui/models 链接；可选补齐缺失下载。
set -euo pipefail

COMFY_ROOT="${COMFY_ROOT:-/comfyui}"
VOLUME_ROOT="${VOLUME_ROOT:-${RUNPOD_VOLUME_PATH:-/runpod-volume}}"
MANIFEST="${MANIFEST:-${COMFY_ROOT}/models_manifest.json}"
DOWNLOAD_MODELS_ON_START="${DOWNLOAD_MODELS_ON_START:-0}"
REQUIRE_MODELS="${REQUIRE_MODELS:-1}"
ALLOW_MISSING_MODELS="${ALLOW_MISSING_MODELS:-0}"
MIN_FREE_KB="${MIN_FREE_KB:-65000000}"

log() { echo "[minimax-h3-i2v] $*"; }

detect_models_root() {
  local vr="$1"
  if [[ -d "${vr}/models/checkpoints" || -d "${vr}/models/loras" || -d "${vr}/models/diffusion_models" ]]; then
    echo "${vr}/models"
    return
  fi
  if [[ -d "${vr}/ComfyUI/models/checkpoints" || -d "${vr}/ComfyUI/models/loras" ]]; then
    echo "${vr}/ComfyUI/models"
    return
  fi
  if [[ -d "${vr}/checkpoints" || -d "${vr}/loras" || -d "${vr}/diffusion_models" ]]; then
    echo "${vr}"
    return
  fi
  echo ""
}

ensure_models_layout() {
  local root="$1"
  mkdir -p \
    "${root}/diffusion_models/MiniMax-H3" \
    "${root}/text_encoders/MiniMax-H3" \
    "${root}/vae/MiniMax-H3" \
    "${root}/loras"
}

link_dir() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    rm -f "$dest"
  elif [[ -d "$dest" ]]; then
    mkdir -p "$dest"
    if [[ -d "$src" ]]; then
      shopt -s nullglob
      for f in "$src"/*; do
        local base
        base="$(basename "$f")"
        [[ "$base" == *.partial ]] && continue
        if [[ ! -e "${dest}/${base}" ]]; then
          ln -sfn "$f" "${dest}/${base}"
        fi
      done
      shopt -u nullglob
    fi
    return
  fi
  if [[ -d "$src" ]]; then
    ln -sfn "$src" "$dest"
    log "link $dest -> $src"
  fi
}

link_all_model_dirs() {
  local src_root="$1"
  for sub in diffusion_models text_encoders vae loras checkpoints; do
    if [[ -d "${src_root}/${sub}" ]]; then
      link_dir "${src_root}/${sub}" "${COMFY_ROOT}/models/${sub}"
    fi
  done
}

list_model_files() {
  local root="$1"
  log "model files under ${root}:"
  for sub in diffusion_models text_encoders vae loras; do
    if [[ -d "${root}/${sub}" ]]; then
      local n
      n="$(find "${root}/${sub}" -type f ! -name '*.partial' 2>/dev/null | wc -l | tr -d ' ')"
      log "  ${sub}/ (${n} files)"
      find "${root}/${sub}" -type f ! -name '*.partial' -printf '    %P (%s bytes)\n' 2>/dev/null | head -20 \
        || find "${root}/${sub}" -type f ! -name '*.partial' 2>/dev/null | head -20
    else
      log "  ${sub}/ (missing dir)"
    fi
  done
}

volume_parent_root() {
  dirname "$MODELS_SRC"
}

volume_models_complete() {
  [[ -f "${COMFY_ROOT}/verify_models.py" && -f "$MANIFEST" ]] || return 1
  python3 "${COMFY_ROOT}/verify_models.py" \
    --root "$(volume_parent_root)" \
    --manifest "$MANIFEST" \
    --strict
}

check_disk_for_download() {
  local path="$1"
  local avail
  avail="$(df -Pk "$path" 2>/dev/null | awk 'NR==2{print $4}')"
  if [[ -z "$avail" ]]; then
    log "WARN: 无法读取磁盘空间: $path"
    return 0
  fi
  log "disk free at $path: $((avail / 1024 / 1024))GB (need ≥$((MIN_FREE_KB / 1024 / 1024))GB to finish missing downloads)"
  if [[ "$avail" -lt "$MIN_FREE_KB" ]]; then
    log "ERROR: Volume 空间不足（约 $((avail / 1024 / 1024))GB 可用），无法补齐约 60GB 模型"
    return 1
  fi
  return 0
}

fail_or_warn() {
  local msg="$1"
  if [[ "$ALLOW_MISSING_MODELS" == "1" ]]; then
    log "WARN: $msg (ALLOW_MISSING_MODELS=1，继续启动)"
    return 0
  fi
  if [[ "$REQUIRE_MODELS" == "1" ]]; then
    log "ERROR: $msg"
    return 1
  fi
  log "WARN: $msg"
  return 0
}

log "VOLUME_ROOT=$VOLUME_ROOT DOWNLOAD_MODELS_ON_START=$DOWNLOAD_MODELS_ON_START REQUIRE_MODELS=$REQUIRE_MODELS"

if [[ ! -d "$VOLUME_ROOT" ]]; then
  fail_or_warn "VOLUME_ROOT 不存在: $VOLUME_ROOT（slim 镜像不含 ~60GB 权重）" || exit 1
  exit 0
fi

MODELS_SRC="$(detect_models_root "$VOLUME_ROOT")"
if [[ -z "$MODELS_SRC" ]]; then
  MODELS_SRC="${VOLUME_ROOT}/models"
  log "未找到现成 models 布局 → 创建 $MODELS_SRC"
  ensure_models_layout "$MODELS_SRC"
fi

ensure_models_layout "$MODELS_SRC"
log "models volume: $MODELS_SRC"
df -h "$VOLUME_ROOT" || true
link_all_model_dirs "$MODELS_SRC"
list_model_files "$MODELS_SRC"

if volume_models_complete; then
  log "Volume 模型已齐全 → 跳过下载（使用外部盘已有权重，不重复拉取）"
else
  log "Volume 尚缺模型（或存在未下完的 .partial）"
  if [[ "$DOWNLOAD_MODELS_ON_START" == "1" ]]; then
    check_disk_for_download "$VOLUME_ROOT" || exit 1
    export HF_TOKEN="${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}"
    export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"
    if [[ -z "${HF_TOKEN}" ]]; then
      log "WARN: HF_TOKEN 为空（公开仓通常仍可下载；失败时请设置 HF_TOKEN）"
    fi
    log "仅补齐缺失文件到 ${MODELS_SRC}（已存在的会 SKIP，不会整包重下）"
    if ! python3 "${COMFY_ROOT}/download_models.py" \
        --root "$(volume_parent_root)" \
        --manifest "$MANIFEST" \
        --attempts 8 \
        --strict; then
      fail_or_warn "download_models 未全部成功（可保留 .partial 下次续传）" || exit 1
    fi
    link_all_model_dirs "$MODELS_SRC"
    list_model_files "$MODELS_SRC"
  else
    fail_or_warn "DOWNLOAD_MODELS_ON_START=0 且 Volume 缺模型；请先补齐或临时设 DOWNLOAD_MODELS_ON_START=1" || exit 1
  fi
fi

if [[ -f "${COMFY_ROOT}/verify_models.py" && -f "$MANIFEST" ]]; then
  if [[ "$ALLOW_MISSING_MODELS" == "1" ]]; then
    python3 "${COMFY_ROOT}/verify_models.py" --root "$COMFY_ROOT" --manifest "$MANIFEST" || \
      log "WARN: 模型校验未通过（ALLOW_MISSING_MODELS=1）"
  else
    if ! python3 "${COMFY_ROOT}/verify_models.py" --root "$COMFY_ROOT" --manifest "$MANIFEST" --strict; then
      fail_or_warn "模型校验未通过（Comfy 会报 ckpt not in []）" || exit 1
    fi
  fi
fi

log "prepare_volume_models OK"
exit 0
