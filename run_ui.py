#!/usr/bin/env python3
"""MiniMax H3 I2V Turbo Serverless 选中执行。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\n按回车返回…")


def main() -> None:
    while True:
        clear()
        print("=" * 56)
        print("  MiniMax H3 I2V Turbo · Serverless")
        print("=" * 56)
        print("  1) 查看 README")
        print("  2) 校验模型 URL")
        print("  3) 构建「首帧+提示词→视频」请求")
        print("  4) 提交到 Endpoint")
        print("  5) 打开目录")
        print("  0) 退出")
        c = input("\n选择: ").strip()
        if c == "1":
            print((ROOT / "README.md").read_text(encoding="utf-8")[:3000])
            pause()
        elif c == "2":
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "verify_models.py"),
                    "--check-urls",
                    "--manifest",
                    str(ROOT / "models_manifest.json"),
                ],
                cwd=ROOT,
                check=False,
            )
            pause()
        elif c == "3":
            image = input("首帧图片路径: ").strip().strip('"').strip("'")
            prompt = input("prompt: ").strip()
            w = input("width [768]: ").strip() or "768"
            h = input("height [512]: ").strip() or "512"
            dur = input("duration 秒 [5]: ").strip() or "5"
            steps = input("steps [4]: ").strip() or "4"
            last = input("尾帧路径（可空）: ").strip().strip('"').strip("'")
            skip = input("跳过 enhancer? [y/N]: ").strip().lower() in {"y", "yes", "1"}
            out = ROOT / "request.json"
            cmd = [
                sys.executable,
                str(ROOT / "build_request.py"),
                "--image",
                image,
                "--prompt",
                prompt,
                "--width",
                w,
                "--height",
                h,
                "--duration",
                dur,
                "--steps",
                steps,
                "--out",
                str(out),
            ]
            if last:
                cmd.extend(["--last-frame", last])
            if skip:
                cmd.append("--skip-enhancer")
            subprocess.run(cmd, cwd=ROOT, check=False)
            pause()
        elif c == "4":
            req = input("request JSON [request.json]: ").strip() or "request.json"
            ep = os.environ.get("RUNPOD_ENDPOINT_ID") or input("ENDPOINT_ID: ").strip()
            key = os.environ.get("RUNPOD_API_KEY") or input("API_KEY: ").strip()
            env = os.environ.copy()
            env["RUNPOD_ENDPOINT_ID"] = ep
            env["RUNPOD_API_KEY"] = key
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "send_request.py"),
                    "--request",
                    str(Path(req) if Path(req).is_absolute() else ROOT / req),
                    "--mode",
                    "run",
                    "--out-dir",
                    str(ROOT / "output"),
                ],
                cwd=ROOT,
                env=env,
                check=False,
            )
            pause()
        elif c == "5":
            if sys.platform == "darwin":
                subprocess.run(["open", str(ROOT)], check=False)
            else:
                print(ROOT)
            pause()
        elif c == "0":
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消")
