#!/usr/bin/env python3
"""构建 MiniMax H3 I2V Turbo RunPod 请求。

  python3 build_request.py \\
    --image ./photo.jpg \\
    --prompt "A woman walks through neon rain" \\
    --width 768 --height 512 --duration 5 \\
    --steps 4 --out request.json
"""

from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_API = ROOT / "api-workflow-i2v.json"
FIRST_FRAME_NAME = "first_frame.jpg"
LAST_FRAME_NAME = "last_frame.jpg"
MAX_IMAGE_SIDE = 1344
JPEG_QUALITY = 85


def snap_frame_count(duration_s: float) -> int:
    """对齐 i2v.json ComfyMath：17k+5 帧数公式。"""
    base = max(5, round(float(duration_s) * 24))
    return base + (5 - (base % 17)) % 17


def encode_image(path: Path, max_side: int, quality: int, out_name: str = FIRST_FRAME_NAME) -> tuple[str, str, dict]:
    try:
        from PIL import Image
    except ImportError:
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return out_name, f"data:image/jpeg;base64,{b64}", {"resized": False}

    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    data = buf.getvalue()
    b64 = base64.b64encode(data).decode("ascii")
    meta = {
        "original_size": [w, h],
        "encoded_size": list(img.size),
        "jpeg_bytes": len(data),
        "resized": scale < 1.0,
    }
    return out_name, f"data:image/jpeg;base64,{b64}", meta


def build_payload(
    *,
    image_path: Path,
    prompt: str,
    width: int,
    height: int,
    duration: float,
    steps: int,
    seed: int | None,
    last_frame_path: Path | None,
    skip_enhancer: bool,
    **kw,
) -> tuple[dict, dict]:
    api = json.loads(Path(kw["api_workflow"]).read_text(encoding="utf-8"))
    name, image_b64, meta = encode_image(image_path, kw["max_side"], kw["quality"])
    wf = copy.deepcopy(api)

    wf["50"]["inputs"]["image"] = name
    wf["104"]["inputs"]["width"] = int(width)
    wf["104"]["inputs"]["height"] = int(height)
    wf["111"]["inputs"]["value"] = float(duration)
    wf["9"]["inputs"]["steps"] = int(steps)

    frame_count = snap_frame_count(duration)
    meta["duration_s"] = float(duration)
    meta["frame_count"] = frame_count

    if skip_enhancer:
        wf["104"]["inputs"]["prompt"] = prompt
    else:
        wf["122"]["inputs"]["manual_prompt"] = prompt
        wf["104"]["inputs"]["prompt"] = ["122", 0]

    if seed is not None:
        wf["15"]["inputs"]["noise_seed"] = int(seed)
        wf["122"]["inputs"]["seed"] = int(seed)

    images = [{"name": name, "image": image_b64}]

    if last_frame_path is not None:
        _, last_b64, last_meta = encode_image(
            last_frame_path, kw["max_side"], kw["quality"], out_name=LAST_FRAME_NAME
        )
        wf["51"]["inputs"]["image"] = LAST_FRAME_NAME
        wf["104"]["inputs"]["last_frame"] = ["51", 0]
        images.append({"name": LAST_FRAME_NAME, "image": last_b64})
        meta["last_frame"] = last_meta
    else:
        wf["104"]["inputs"].pop("last_frame", None)

    payload = {
        "input": {
            "workflow": wf,
            "images": images,
        },
        "policy": {
            "executionTimeout": int(kw.get("execution_timeout_ms", 3_600_000)),
            "ttl": int(kw.get("ttl_ms", 7_200_000)),
        },
    }
    return payload, meta


def main() -> int:
    p = argparse.ArgumentParser(description="MiniMax H3 I2V Turbo → RunPod request.json")
    p.add_argument("--image", required=True, help="首帧图片")
    p.add_argument("--prompt", required=True, help="提示词（manual_prompt / 直传 I2V）")
    p.add_argument("--width", type=int, default=768)
    p.add_argument("--height", type=int, default=512)
    p.add_argument("--duration", type=float, default=5.0, help="时长（秒），自动换算帧数")
    p.add_argument("--steps", type=int, default=4, help="Turbo 采样步数，默认 4")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--last-frame", default=None, help="可选尾帧图片（首尾帧过渡）")
    p.add_argument("--skip-enhancer", action="store_true", help="跳过 PromptEnhancer，直传 prompt 到 I2V")
    p.add_argument("--api-workflow", default=str(DEFAULT_API))
    p.add_argument("--max-side", type=int, default=MAX_IMAGE_SIDE)
    p.add_argument("--quality", type=int, default=JPEG_QUALITY)
    p.add_argument("--execution-timeout-ms", type=int, default=3_600_000)
    p.add_argument("--ttl-ms", type=int, default=7_200_000)
    p.add_argument("--out", default="request.json")
    args = p.parse_args()

    path = Path(args.image)
    if not path.is_file():
        print(f"图片不存在: {path}", file=sys.stderr)
        return 1

    last_path = Path(args.last_frame) if args.last_frame else None
    if last_path and not last_path.is_file():
        print(f"尾帧不存在: {last_path}", file=sys.stderr)
        return 1

    payload, meta = build_payload(
        image_path=path,
        prompt=args.prompt,
        width=args.width,
        height=args.height,
        duration=args.duration,
        steps=args.steps,
        seed=args.seed,
        last_frame_path=last_path,
        skip_enhancer=args.skip_enhancer,
        api_workflow=args.api_workflow,
        max_side=args.max_side,
        quality=args.quality,
        execution_timeout_ms=args.execution_timeout_ms,
        ttl_ms=args.ttl_ms,
    )
    out = Path(args.out)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    mb = out.stat().st_size / (1024 * 1024)
    print(f"Wrote {out} ({mb:.2f} MB)")
    print(f"Meta: {json.dumps(meta, ensure_ascii=False)}")
    print(
        "对齐: LoadImage(50)=%r | frames≈%s | steps=%s | enhancer=%s"
        % (
            payload["input"]["workflow"]["50"]["inputs"]["image"],
            meta.get("frame_count"),
            args.steps,
            not args.skip_enhancer,
        )
    )
    if mb > 9.5:
        print("WARNING: payload > 9.5MB，建议 /run 并减小 --max-side", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
