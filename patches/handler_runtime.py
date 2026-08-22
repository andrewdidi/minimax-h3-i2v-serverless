"""Runtime /handler.py: stock worker-comfyui + video collect + upload cleanup."""

from __future__ import annotations

import base64
import importlib.util
import os
import traceback
from pathlib import Path
from typing import Any

import runpod

STOCK_PATH = Path("/handler.stock.py")
COMFY_INPUT = Path("/comfyui/input")
COMFY_OUTPUT = Path("/comfyui/output")
COMFY_TEMP = Path("/comfyui/temp")
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".gif"}

_PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAGfAP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAQUCf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQMBAT8Bf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQIBAT8Bf//Z"
)


def _load_stock():
    if not STOCK_PATH.is_file():
        raise FileNotFoundError(f"Missing {STOCK_PATH}")
    spec = importlib.util.spec_from_file_location("worker_comfyui_stock", STOCK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_stock = _load_stock()


def _safe_name(name: str) -> str | None:
    if not name or not isinstance(name, str):
        return None
    safe = Path(name).name
    if not safe or safe in {".", ".."}:
        return None
    return safe


def cleanup_uploaded_images(images: list | None) -> list[str]:
    cleaned: list[str] = []
    if not images:
        return cleaned
    for item in images:
        if not isinstance(item, dict):
            continue
        safe = _safe_name(item.get("name") or "")
        if not safe:
            continue
        path = COMFY_INPUT / safe
        try:
            if path.is_file():
                path.unlink()
                cleaned.append(safe)
                print(f"minimax-h3-i2v - cleaned upload: {path}")
        except OSError as e:
            print(f"minimax-h3-i2v - cleanup upload failed {path}: {e}")
    try:
        COMFY_INPUT.mkdir(parents=True, exist_ok=True)
        ph = COMFY_INPUT / "first_frame.jpg"
        if not ph.exists():
            ph.write_bytes(_PLACEHOLDER_JPEG)
    except OSError:
        pass
    return cleaned


def collect_videos(result: dict | None, existing_names: set[str]) -> list[dict]:
    found: list[dict] = []
    if not COMFY_OUTPUT.exists():
        return found
    files = sorted(COMFY_OUTPUT.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTS:
            continue
        name = path.name
        if name in existing_names:
            continue
        try:
            data = path.read_bytes()
            found.append(
                {
                    "filename": str(path.relative_to(COMFY_OUTPUT)),
                    "type": "base64",
                    "data": base64.b64encode(data).decode("ascii"),
                    "media_type": "video",
                }
            )
            existing_names.add(name)
            print(f"minimax-h3-i2v - collected video: {path} ({len(data)} bytes)")
            if len(found) >= 3:
                break
        except Exception as e:
            print(f"minimax-h3-i2v - video collect failed {path}: {e}")
    return found


def cleanup_media_files(items: list) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        rel = item.get("filename") or _safe_name(item.get("filename") or "")
        if not rel:
            continue
        safe = Path(rel).name
        for base in (COMFY_OUTPUT, COMFY_TEMP):
            for p in (base / rel, base / safe):
                try:
                    if p.is_file():
                        p.unlink()
                        print(f"minimax-h3-i2v - cleaned media: {p}")
                except OSError:
                    pass


def handler(job: dict):
    images = None
    result: Any = None
    try:
        job_input = job.get("input") if isinstance(job, dict) else None
        if isinstance(job_input, dict):
            images = job_input.get("images")
        result = _stock.handler(job)
        if not isinstance(result, dict):
            result = {"raw": result}

        out_images = list(result.get("images") or [])
        names = {Path(x.get("filename", "")).name for x in out_images if isinstance(x, dict)}
        videos = collect_videos(result, names)
        if videos:
            out_images.extend(videos)
            result["images"] = out_images
            result.setdefault("videos", videos)
            print(f"minimax-h3-i2v - appended {len(videos)} video(s)")
        return result
    except Exception as e:
        print(f"minimax-h3-i2v - wrapper error: {e}")
        print(traceback.format_exc())
        raise
    finally:
        try:
            cleanup_uploaded_images(images if isinstance(images, list) else None)
            if isinstance(result, dict):
                cleanup_media_files(result.get("images") or [])
        except Exception as e:
            print(f"minimax-h3-i2v - post-job cleanup error: {e}")


print("minimax-h3-i2v - Starting handler (I2V turbo + video collect)...")
runpod.serverless.start({"handler": handler})
