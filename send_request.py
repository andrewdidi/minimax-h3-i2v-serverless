#!/usr/bin/env python3
"""提交 MiniMax H3 I2V Turbo 任务（推荐 /run 异步）。"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict, api_key: str, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def validate_upload(payload: dict) -> None:
    inp = payload.get("input") or {}
    if "workflow" not in inp:
        raise SystemExit("缺少 input.workflow")
    images = inp.get("images")
    if not images:
        raise SystemExit("缺少 input.images（上传模式必填）")
    for i, img in enumerate(images):
        if "name" not in img or "image" not in img:
            raise SystemExit(f"images[{i}] 需要 name + image")
    expected = (((inp["workflow"].get("50") or {}).get("inputs") or {}).get("image"))
    names = {x["name"] for x in images}
    if expected and expected not in names:
        raise SystemExit(f"LoadImage(50)={expected!r} 与 images[].name={names} 不一致")
    print(f"上传校验通过: LoadImage(50)={expected!r}")


def save_media(result: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    output = result.get("output") or {}
    items = list(output.get("images") or []) + list(output.get("videos") or [])
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        name = item.get("filename") or f"out_{i}.bin"
        typ = item.get("type") or "base64"
        safe = Path(name).name
        if typ == "s3_url" and isinstance(data, str):
            p = out_dir / (safe + ".url.txt")
            p.write_text(data + "\n", encoding="utf-8")
            saved.append(p)
            continue
        if not data or not isinstance(data, str):
            continue
        raw = data.split(",", 1)[1] if data.startswith("data:") else data
        try:
            blob = base64.b64decode(raw)
        except Exception:
            continue
        path = out_dir / safe
        if path.suffix.lower() not in {".mp4", ".webm", ".mov", ".png", ".jpg", ".gif", ".mkv"}:
            path = path.with_suffix(".mp4" if len(blob) > 500_000 else ".bin")
        path.write_bytes(blob)
        saved.append(path)
        latest = out_dir / "latest_video.mp4"
        if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
            latest.write_bytes(blob)
    return saved


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--endpoint-id", default=os.environ.get("RUNPOD_ENDPOINT_ID"))
    p.add_argument("--api-key", default=os.environ.get("RUNPOD_API_KEY"))
    p.add_argument("--mode", choices=["run", "runsync"], default="run")
    p.add_argument("--poll-s", type=float, default=8.0)
    p.add_argument("--out-dir", default="output")
    p.add_argument("--out-result", default="result.json")
    args = p.parse_args()
    if not args.endpoint_id or not args.api_key:
        print("需要 RUNPOD_ENDPOINT_ID 与 RUNPOD_API_KEY", file=sys.stderr)
        return 1

    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    validate_upload(payload)
    base = f"https://api.runpod.ai/v2/{args.endpoint_id}"
    url = f"{base}/{args.mode}"
    print(f"POST {url}")
    try:
        resp = post_json(url, payload, args.api_key, timeout=600 if args.mode == "runsync" else 120)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1

    if args.mode == "runsync":
        Path(args.out_result).write_text(json.dumps(_slim(resp), ensure_ascii=False, indent=2))
        saved = save_media(resp, Path(args.out_dir))
        print(f"status={resp.get('status')} saved={len(saved)}")
        return 0 if resp.get("status") in {None, "COMPLETED", "completed"} else 1

    job_id = resp.get("id")
    if not job_id:
        print(resp)
        return 1
    print(f"job id={job_id}")
    while True:
        st = get_json(f"{base}/status/{job_id}", args.api_key)
        status = st.get("status")
        print(f"  status={status}")
        if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            Path(args.out_result).write_text(json.dumps(_slim(st), ensure_ascii=False, indent=2))
            saved = save_media(st, Path(args.out_dir))
            print(f"Wrote {args.out_result}, media={len(saved)}")
            for s in saved:
                print(f"  - {s} ({s.stat().st_size} bytes)")
            return 0 if status == "COMPLETED" else 1
        time.sleep(args.poll_s)


def _slim(obj: dict) -> dict:
    data = json.loads(json.dumps(obj))
    out = data.get("output") or {}
    for key in ("images", "videos"):
        for item in out.get(key) or []:
            if isinstance(item, dict) and isinstance(item.get("data"), str) and len(item["data"]) > 200:
                item["data"] = f"<base64 len={len(item['data'])}>"
    return data


if __name__ == "__main__":
    raise SystemExit(main())
