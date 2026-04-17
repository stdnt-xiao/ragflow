# 国内构建 RAGFlow Docker 镜像说明

## 1. 配置 Docker daemon registry mirror（必做）

Base 镜像 `ubuntu:24.04` 与 `infiniflow/ragflow_deps:latest` 都托管在 Docker Hub，国内直连很慢。编辑 `/etc/docker/daemon.json`（macOS 在 Docker Desktop → Settings → Docker Engine）：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.net",
    "https://docker.1panel.live",
    "https://hub-mirror.c.163.com"
  ]
}
```

保存后重启 Docker。

> 注：`infiniflow/ragflow_deps` 是官方提供的资源镜像（约 10GB，包含 NLTK/Tika/Chromium/HuggingFace 模型等），必须能从 Docker Hub 拉到。上述 mirror 任一可用即可。

## 2. 开启 BuildKit

```bash
export DOCKER_BUILDKIT=1
```

Docker Desktop 默认已启用。

## 3. 构建命令

直接用封装好的脚本：

```bash
./build-cn.sh
# 或指定 tag
TAG=v0.22.0 ./build-cn.sh
```

等价于：

```bash
docker build --build-arg NEED_MIRROR=1 -f Dockerfile -t infiniflow/ragflow:nightly .
```

`NEED_MIRROR=1` 会启用：
- apt 源 → `mirrors.aliyun.com`
- pypi → `mirrors.aliyun.com/pypi`
- Python 解释器 (uv) → `registry.npmmirror.com`
- NodeSource (node 20) → `mirrors.tuna.tsinghua.edu.cn`
- npm 全部二进制依赖 → `registry.npmmirror.com`
- `infiniflow/resource` → `gitee.com/infiniflow/resource`

## 4. 有代理时

如果你有能直连 Docker Hub / GitHub 的代理，可以不改 daemon，而是：

```bash
HTTP_PROXY=http://host.docker.internal:7890 \
HTTPS_PROXY=http://host.docker.internal:7890 \
NO_PROXY=localhost,127.0.0.1 \
./build-cn.sh
```

## 5. 可能遇到的问题

- **拉取 `infiniflow/ragflow_deps:latest` 超时**：换一个 registry mirror，或使用代理。
- **`packages.microsoft.com` / `nginx.org` 偶发慢**：已加入重试，重跑一次即可。
- **`git clone gitee.com/infiniflow/resource` 失败**：gitee 偶发限速，重试或改回 github（去掉 `NEED_MIRROR=1`，用代理）。
- **ARM64 / Apple Silicon**：脚本默认 `PLATFORM=linux/amd64`。如果要构建 ARM64，设 `PLATFORM=linux/arm64` 并确保 buildx 支持跨平台。
