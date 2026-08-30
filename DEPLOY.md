# MiniMax H3 I2V Turbo · 零出错部署清单

**推荐路径**：Network Volume 填盘 → Serverless 只链接+校验。

---

## 绿灯标准

| # | 检查项 | 通过标准 |
|---|--------|----------|
| 1 | Volume | ≥ **120GB**，挂载 **`/runpod-volume`** |
| 2 | 六个权重 | `verify_models.py --strict` → `PASSED` |
| 3 | 镜像 | **`andrewdidi/minimax-h3-i2v-serverless:latest`**（Docker Hub，**不要用 GHCR**） |
| 4 | Endpoint 环境变量 | `VOLUME_ROOT` · `DOWNLOAD_MODELS_ON_START=0` · `REQUIRE_MODELS=1` |
| 5 | Worker 日志 | `Volume 模型已齐全 → 跳过下载` · `prepare_volume_models OK` |

模型清单见 `models_manifest.json`（FL2VA ~20GB + Heretic TE ~25GB + Tail ~7.6GB + VAEs + LoRA）。

---

## 为什么不用 GHCR（彻底解决 toomanyrequests）

RunPod Worker 从 `ghcr.io` 拉大镜像时，常因机房**共享出口 IP** 触发：

```text
failed to pull image: toomanyrequests
```

Package 设为 Public、配置 Registry Auth **都不能根治**。  
**根治**：镜像推到 **Docker Hub**，Endpoint 只填 Docker Hub 地址。

| 用途 | 地址 |
|------|------|
| **RunPod Serverless（必用）** | `andrewdidi/minimax-h3-i2v-serverless:latest` |
| 备用 / CI 产物 | `ghcr.io/andrewdidi/minimax-h3-i2v-serverless:latest` |

Actions 已双推；仓库需配置 Secrets：`DOCKERHUB_USERNAME`、`DOCKERHUB_TOKEN`（Hub Access Token）。

---

## 步骤 1 · Network Volume

RunPod → Storage → Network Volume → 同区域 ≥ **120GB**。

---

## 步骤 2 · 镜像

推送本仓库 `main` → GitHub Actions 构建并推送 **Docker Hub + GHCR**。

```text
andrewdidi/minimax-h3-i2v-serverless:latest
```

Endpoint / Template 的 Container Image **只填上面这一行**（或 `docker.io/andrewdidi/minimax-h3-i2v-serverless:latest`）。

---

## 步骤 3 · 临时 Pod 填盘

1. Pod 镜像：`andrewdidi/minimax-h3-i2v-serverless:latest`
2. 挂载 Volume → `/runpod-volume`
3. 环境变量：`VOLUME_ROOT=/runpod-volume` · `HF_TOKEN=hf_xxx`（可选）
4. **Start Command**：

```bash
bash /comfyui/pod_fill_volume.sh
```

5. 日志结尾出现 **`DOWNLOAD_COMPLETE` / `下载完成`**（以及 `PASSED`）即可 Stop Pod；不要一直等 sleep
6. Stop 临时 Pod（Volume 保留）

---

## 步骤 4 · Serverless Endpoint

1. 同一 Volume → `/runpod-volume`
2. **Container Image**：`andrewdidi/minimax-h3-i2v-serverless:latest`（勿填 ghcr.io）
3. 环境变量：

```text
VOLUME_ROOT=/runpod-volume
DOWNLOAD_MODELS_ON_START=0
REQUIRE_MODELS=1
```

4. Redeploy → 首测用 `build_request.py --duration 5 --steps 4`

GPU 建议 ≥ **48–80GB**；容器盘 ≥ **20GB**。

若 Docker Hub 私有仓库，再在 Template 选 Docker Hub 的 Registry Auth；**Public 仓库无需 Auth**。
---

## 本地验证

```bash
python3 verify_models.py --check-urls
python3 build_request.py --image ./test.jpg --prompt "test" --out request.json
```

双击 **`选中执行_MiniMaxH3New.command`** 或 `Exe_UI/minimax_h3_new/`。
