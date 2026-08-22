#!/usr/bin/env python3
"""构建期稳健下载 ComfyUI 模型（断点续传 / 重试 / 镜像回退 / 体积校验）。

  python3 download_models.py --root /comfyui --manifest models_manifest.json --strict
  python3 download_models.py --only ae.safetensors
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_manifest(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def fmt_bytes(n: int | None) -> str:
    if n is None:
        return "?"
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{int(x)}{unit}" if unit == "B" else f"{x:.2f}{unit}"
        x /= 1024
    return f"{x:.2f}PB"


def size_ok(path: Path, expected: int | None, tolerance: float) -> bool:
    if not path.is_file():
        return False
    if expected is None:
        return path.stat().st_size > 0
    actual = path.stat().st_size
    lo = int(expected * (1 - tolerance))
    hi = int(expected * (1 + tolerance))
    return lo <= actual <= hi


def mirror_urls(url: str) -> list[str]:
    """官方 HF → 可选镜像。环境变量 HF_MIRROR 可覆盖（如 https://hf-mirror.com）。"""
    urls = [url]
    mirror = (os.environ.get("HF_MIRROR") or "").rstrip("/")
    if "huggingface.co" in url:
        if mirror:
            urls.append(url.replace("https://huggingface.co", mirror).replace(
                "http://huggingface.co", mirror
            ))
        # 常用公共镜像（构建机在国内/偶发 HF 限流时）
        alt = url.replace("https://huggingface.co", "https://hf-mirror.com")
        if alt not in urls:
            urls.append(alt)
    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def auth_headers() -> dict[str, str]:
    token = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    headers = {"User-Agent": "z-image-img2img-download/1.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def download_with_curl(url: str, dest: Path, partial: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = auth_headers()
    cmd = [
        "curl",
        "-fL",
        "--retry",
        "2",
        "--retry-delay",
        "3",
        "--retry-all-errors",
        "--connect-timeout",
        "30",
        "--max-time",
        "0",
        "-C",
        "-",
        "-o",
        str(partial),
    ]
    for k, v in headers.items():
        cmd.extend(["-H", f"{k}: {v}"])
    cmd.append(url)
    print(f"  curl: {url}", flush=True)
    subprocess.run(cmd, check=True)


def download_with_urllib(url: str, dest: Path, partial: Path) -> None:
    """Fallback when curl missing; supports resume via Range."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = auth_headers()
    existing = partial.stat().st_size if partial.is_file() else 0
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
    req = urllib.request.Request(url, headers=headers)
    print(f"  urllib: {url} (resume={existing})", flush=True)
    with urllib.request.urlopen(req, timeout=600) as resp, open(partial, "ab" if existing else "wb") as out:
        # 若服务器忽略 Range 返回 200，重写文件
        if existing and getattr(resp, "status", 200) == 200 and "Content-Range" not in resp.headers:
            out.close()
            partial.write_bytes(b"")
            with open(partial, "wb") as out2:
                shutil.copyfileobj(resp, out2, length=1024 * 1024)
            return
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def try_comfy_cli(url: str, root: Path, relative_path: str, filename: str) -> bool:
    comfy = shutil.which("comfy")
    if not comfy:
        return False
    env = os.environ.copy()
    print(f"  comfy model download: {filename}", flush=True)
    r = subprocess.run(
        [
            comfy,
            "model",
            "download",
            "--url",
            url,
            "--relative-path",
            relative_path,
            "--filename",
            filename,
        ],
        cwd=str(root),
        env=env,
        check=False,
    )
    return r.returncode == 0


def download_one(
    root: Path,
    model: dict,
    *,
    attempts: int,
    tolerance: float,
    prefer_comfy: bool,
) -> None:
    filename = model["filename"]
    rel_dir = model["relative_path"]
    url = model["url"]
    expected = model.get("bytes")
    dest = root / rel_dir / filename
    partial = dest.with_suffix(dest.suffix + ".partial")

    if size_ok(dest, expected, tolerance):
        print(f"SKIP {filename} already OK ({fmt_bytes(dest.stat().st_size)})", flush=True)
        return

    if dest.exists():
        print(
            f"REMOVE incomplete {filename} size={fmt_bytes(dest.stat().st_size)} expected≈{fmt_bytes(expected)}",
            flush=True,
        )
        dest.unlink()

    urls = mirror_urls(url)
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        for u in urls:
            try:
                print(
                    f"GET [{attempt}/{attempts}] {filename} ← {u} expected≈{fmt_bytes(expected)}",
                    flush=True,
                )
                ok = False
                if prefer_comfy and attempt == 1 and u == url:
                    ok = try_comfy_cli(u, root, rel_dir, filename)
                    if ok and size_ok(dest, expected, tolerance):
                        print(f"OK {filename} via comfy ({fmt_bytes(dest.stat().st_size)})", flush=True)
                        return
                    if dest.exists() and not size_ok(dest, expected, tolerance):
                        dest.unlink(missing_ok=True)

                if shutil.which("curl"):
                    download_with_curl(u, dest, partial)
                else:
                    download_with_urllib(u, dest, partial)

                if not partial.is_file():
                    raise RuntimeError("partial missing after download")
                if not size_ok(partial, expected, tolerance):
                    sz = partial.stat().st_size
                    raise RuntimeError(
                        f"size mismatch after download: got {fmt_bytes(sz)} expected≈{fmt_bytes(expected)}"
                    )
                partial.replace(dest)
                print(f"OK {filename} ({fmt_bytes(dest.stat().st_size)})", flush=True)
                return
            except Exception as e:
                last_err = e
                print(f"  FAIL: {e}", flush=True)
                # 体积不对则删 partial，避免坏续传死循环；网络中断保留 partial 以便续传
                if partial.is_file() and expected and partial.stat().st_size > expected * (1 + tolerance):
                    partial.unlink(missing_ok=True)
                if dest.exists() and not size_ok(dest, expected, tolerance):
                    dest.unlink(missing_ok=True)
        sleep_s = min(120, 8 * attempt)
        print(f"  backoff {sleep_s}s…", flush=True)
        time.sleep(sleep_s)

    raise RuntimeError(f"download failed for {filename}: {last_err}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/comfyui")
    ap.add_argument("--manifest", default="models_manifest.json")
    ap.add_argument("--only", action="append", default=[], help="只下指定 filename，可重复")
    ap.add_argument("--attempts", type=int, default=8)
    ap.add_argument("--tolerance", type=float, default=0.02)
    ap.add_argument("--prefer-comfy", action="store_true", help="首次尝试 comfy model download")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    manifest = load_manifest(Path(args.manifest))
    models = manifest.get("models") or []
    if args.only:
        want = set(args.only)
        models = [m for m in models if m["filename"] in want]
        missing = want - {m["filename"] for m in models}
        if missing:
            print(f"unknown --only: {missing}", file=sys.stderr)
            return 1

    print(f"Root={root} models={len(models)} HF_TOKEN={'set' if auth_headers().get('Authorization') else 'no'}")
    errors = 0
    for m in models:
        if not m.get("required", True) and args.only == []:
            continue
        try:
            download_one(
                root,
                m,
                attempts=args.attempts,
                tolerance=args.tolerance,
                prefer_comfy=args.prefer_comfy,
            )
        except Exception as e:
            errors += 1
            print(f"ERROR {m.get('filename')}: {e}", file=sys.stderr)
            if args.strict:
                return 1
    if errors:
        print(f"FAILED: {errors} model(s)", file=sys.stderr)
        return 1 if args.strict else 0
    print("ALL DOWNLOADS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
