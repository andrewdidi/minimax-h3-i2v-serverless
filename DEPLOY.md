# MiniMax H3 I2V Turbo · 零出错部署清单

**推荐路径**：Network Volume 填盘 → Serverless 只链接+校验。

---

## 绿灯标准

| # | 检查项 | 通过标准 |
|---|--------|----------|
| 1 | Volume | ≥ **120GB**，挂载 **`/runpod-volume`** |
| 2 | 六个权重 | `verify_models.py --strict` → `PASSED` |
| 3 | 镜像 | **Docker Hub** `<Hub用户名>/minimax-h3:latest`（短名，**不要用 GHCR**） |
| 4 | Endpoint 环境变量 | `VOLUME_ROOT` · `DOWNLOAD_MODELS_ON_START=0` · `REQUIRE_MODELS=1` |
| 5 | Worker 日志 | `Volume 模型已齐全 → 跳过下载` · `prepare_volume_models OK` |

---

## 镜像名（已换短名）

| 用途 | 地址 |
|------|------|
| **RunPod（必用）** | `<Hub用户名>/minimax-h3:latest` |
| GHCR 备份 | `ghcr.io/andrewdidi/minimax-h3:latest` |
| 旧长名（仍推，勿给 RunPod） | `…/minimax-h3-i2v-serverless` |

不要用 `ghcr.io` 给 RunPod（易 `toomanyrequests`）。

### GitHub Actions Secrets（只用这两个名字）

| Secret | 值 |
|--------|-----|
| `DOCKERHUB_USERNAME` | Hub 右上角短用户名（不是 Token） |
| `DOCKERHUB_TOKEN` | 新建 Access Token 的完整密钥 |

**不要用** `AGRICARETK` / `DCKR_PAT_*`（容易填反）。Hub 凭证不对时 CI 仍会成功推 GHCR，但 RunPod 要用 Hub 需先配好上述两条。

```bash
gh secret set DOCKERHUB_USERNAME    # 短用户名 → Ctrl+D
gh secret set DOCKERHUB_TOKEN       # Token 整串 → Ctrl+D
gh secret delete AGRICARETK         # 可选清理
gh workflow run "Build and push Docker image"
```

---

## 步骤 1 · Network Volume

RunPod → Storage → Network Volume → 同区域 ≥ **120GB**。

---

## 步骤 2 · 镜像

推送 `main` 或手动 `workflow_dispatch` → 产出 Hub 短名镜像。

```text
<Hub用户名>/minimax-h3:latest
```

---

## 步骤 3 · 临时 Pod 填盘

1. Pod 镜像：`<Hub用户名>/minimax-h3:latest`
2. 挂载 Volume → `/runpod-volume`
3. 环境变量：`VOLUME_ROOT=/runpod-volume` · `HF_TOKEN=hf_xxx`（可选）
4. **Start Command**：

```bash
bash /comfyui/pod_fill_volume.sh
```

5. 日志出现 **`DOWNLOAD_COMPLETE` / `下载完成`** 即可 Stop Pod
6. Stop 临时 Pod（Volume 保留）

---

## 步骤 4 · Serverless Endpoint

1. 同一 Volume → `/runpod-volume`
2. **Container Image**：`<Hub用户名>/minimax-h3:latest`（勿填 ghcr.io）
3. 环境变量：

```text
VOLUME_ROOT=/runpod-volume
DOWNLOAD_MODELS_ON_START=0
REQUIRE_MODELS=1
```

4. Redeploy → `build_request.py --duration 5 --steps 4`

GPU ≥ **48–80GB**；容器盘 ≥ **20GB**。
