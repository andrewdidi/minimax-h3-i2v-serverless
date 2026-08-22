#!/usr/bin/env python3
"""Verify required ComfyUI models exist at the correct relative paths.

Usage:
  python3 verify_models.py --root /comfyui --manifest models_manifest.json --strict
  python3 verify_models.py --check-urls   # HEAD-check remote URLs (no download)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_bytes(n: int | None) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}PB"


def verify_files(root: Path, manifest: dict, strict: bool, tolerance: float) -> int:
    errors = 0
    print(f"Root: {root}")
    print(f"Models: {len(manifest.get('models', []))}")
    for note in manifest.get("notes", []):
        print(f"  note: {note}")
    print()

    for m in manifest.get("models", []):
        rel = Path(m["relative_path"]) / m["filename"]
        path = root / rel
        expected = m.get("bytes")
        required = m.get("required", True)
        status = "OK"
        detail = ""

        if not path.is_file():
            status = "MISSING"
            errors += 1 if required else 0
        else:
            actual = path.stat().st_size
            detail = f"size={fmt_bytes(actual)}"
            if expected:
                lo = int(expected * (1 - tolerance))
                hi = int(expected * (1 + tolerance))
                if actual < lo or actual > hi:
                    status = "SIZE_MISMATCH"
                    detail += f" expected≈{fmt_bytes(expected)} (±{int(tolerance*100)}%)"
                    errors += 1 if required else 0
                else:
                    detail += f" (expected≈{fmt_bytes(expected)})"

        mark = "✓" if status == "OK" else "✗"
        print(f"{mark} [{status:14}] {rel}  {detail}")
        if status != "OK":
            print(f"    url: {m.get('url')}")

    print()
    if errors:
        print(f"FAILED: {errors} problem(s)")
        if strict:
            return 1
    else:
        print("PASSED: all required models present")
    return 0


def check_urls(manifest: dict) -> int:
    errors = 0
    for m in manifest.get("models", []):
        url = m["url"]
        name = m["filename"]
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=60) as r:
                cl = r.headers.get("Content-Length")
                if not cl:
                    req2 = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
                    with urllib.request.urlopen(req2, timeout=60) as r2:
                        cr = r2.headers.get("Content-Range", "")
                        cl = cr.split("/")[-1] if "/" in cr else None
                remote = int(cl) if cl and str(cl).isdigit() else None
                expected = m.get("bytes")
                ok = remote is not None and (expected is None or abs(remote - expected) < max(1024, expected * 0.01))
                mark = "✓" if ok else "!"
                print(f"{mark} {name}: HTTP OK remote={fmt_bytes(remote)} expected={fmt_bytes(expected)}")
                if not ok:
                    errors += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            print(f"    url: {url}")
            errors += 1
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="ComfyUI root containing models/")
    ap.add_argument("--manifest", default="models_manifest.json")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any missing/mismatch")
    ap.add_argument("--tolerance", type=float, default=0.02, help="allowed size drift ratio")
    ap.add_argument("--check-urls", action="store_true", help="only HEAD-check remote URLs")
    args = ap.parse_args()

    manifest = load_manifest(Path(args.manifest))
    if args.check_urls:
        return check_urls(manifest)
    return verify_files(Path(args.root), manifest, args.strict, args.tolerance)


if __name__ == "__main__":
    sys.exit(main())
