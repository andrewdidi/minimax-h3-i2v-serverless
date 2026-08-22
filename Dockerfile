# MiniMax H3 I2V Turbo · Runpod Serverless（slim，模型走 Network Volume）
# worker-comfyui 5.8.x 默认 ComfyUI 0.29.0，不含原生 MiniMaxH3ImageToVideo（需 ≥0.30.0）
FROM runpod/worker-comfyui:5.8.6-base

SHELL ["/bin/bash", "-lc"]

ARG COMFYUI_VERSION=v0.33.1

RUN apt-get update -qq && apt-get install -y -qq git ca-certificates curl && rm -rf /var/lib/apt/lists/* || true

# 升级核心 ComfyUI，拿到 MiniMaxH3ImageToVideo / VAEDecodeAudio / CreateVideo / SaveVideo
RUN set -euo pipefail; \
    cd /comfyui; \
    test -d .git; \
    git fetch --depth 1 origin tag "${COMFYUI_VERSION}"; \
    git checkout -f FETCH_HEAD; \
    test -f comfy_extras/nodes_minimax_h3.py; \
    (command -v uv >/dev/null && uv pip install -r requirements.txt) || pip install -r requirements.txt; \
    python -c "import torchaudio; print('torchaudio', torchaudio.__version__)"

RUN comfy node install --exit-on-fail comfyui-art-venture@1.1.3 --mode remote || \
    (echo "WARN: art-venture pin unavailable, latest" >&2 && comfy node install --exit-on-fail comfyui-art-venture --mode remote)
RUN git clone --depth 1 https://github.com/ethanfel/ComfyUI-MiniMax-H3-Guide /comfyui/custom_nodes/ComfyUI-MiniMax-H3-Guide

COPY api-workflow-i2v.json /comfyui/workflow_api.json
COPY models_manifest.json /comfyui/models_manifest.json
COPY download_models.py /comfyui/download_models.py
COPY verify_models.py /comfyui/verify_models.py
COPY scripts/prepare_volume_models.sh /comfyui/prepare_volume_models.sh
COPY scripts/download_to_volume.sh /comfyui/download_to_volume.sh
COPY scripts/pod_fill_volume.sh /comfyui/pod_fill_volume.sh
COPY scripts/start_with_volume.sh /start_with_volume.sh

RUN chmod +x /comfyui/download_models.py /comfyui/verify_models.py \
      /comfyui/prepare_volume_models.sh /comfyui/download_to_volume.sh \
      /comfyui/pod_fill_volume.sh /start_with_volume.sh && \
    mkdir -p /comfyui/input /comfyui/output/video && \
    python3 -c "import base64;from pathlib import Path;Path('/comfyui/input/first_frame.jpg').write_bytes(base64.b64decode('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAGfAP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAQUCf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQMBAT8Bf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQIBAT8Bf//Z'))"

RUN cp /handler.py /handler.stock.py
COPY patches/handler_runtime.py /handler.py
COPY test_input.json /test_input.json

ENTRYPOINT ["/start_with_volume.sh"]
