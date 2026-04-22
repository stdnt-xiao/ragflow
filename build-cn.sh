#!/bin/bash
# 在中国大陆 / 内网环境构建 RAGFlow 镜像的辅助脚本
#
# 用法：
#   ./build-cn.sh                       # 构建 slim 镜像（不含大模型权重）
#   TAG=nightly ./build-cn.sh           # 指定 tag
#   BUILD_DEPS=1 ./build-cn.sh          # 强制在本地重新构建 deps 镜像
#
# 脚本会按以下顺序获取 infiniflow/ragflow_deps:latest：
#   1. 本地已存在 → 直接复用
#   2. 尝试从 Docker Hub（或配置的 registry mirror）拉取
#   3. 拉取失败 → 自动调用 download_deps.py --china-mirrors 下载依赖文件，
#      再用 Dockerfile.deps 在本地构建 deps 镜像
#
# 前置条件：
#   - docker buildx 已安装
#   - Python 3 + uv（用于执行 download_deps.py）
set -euo pipefail

TAG="${TAG:-nightly}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE="${IMAGE:-infiniflow/ragflow:${TAG}}"
DEPS_IMAGE="infiniflow/ragflow_deps:latest"
BUILD_DEPS="${BUILD_DEPS:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 构建 RAGFlow 镜像 (国内网络 / 内网优化) ==="
echo "    IMAGE       = ${IMAGE}"
echo "    PLATFORM    = ${PLATFORM}"
echo "    NEED_MIRROR = 1"
echo "    BUILD_DEPS  = ${BUILD_DEPS}"
echo

# ────────────────────────────────────────────────
# Step 1: 确保 deps 镜像可用
# ────────────────────────────────────────────────
ensure_deps_image() {
    # 如果本地已存在且不强制重建，直接跳过
    if [[ "${BUILD_DEPS}" == "0" ]] && docker image inspect "${DEPS_IMAGE}" &>/dev/null; then
        echo ">>> deps 镜像已存在于本地，跳过拉取"
        return 0
    fi

    if [[ "${BUILD_DEPS}" == "0" ]]; then
        echo ">>> 尝试从远端拉取 ${DEPS_IMAGE}"
        if docker pull --platform "${PLATFORM}" "${DEPS_IMAGE}" 2>/dev/null; then
            echo ">>> 拉取成功"
            return 0
        fi
        echo ">>> 远端拉取失败，将在本地构建 deps 镜像"
    else
        echo ">>> BUILD_DEPS=1，强制本地构建 deps 镜像"
    fi

    build_deps_image_locally
}

build_deps_image_locally() {
    echo
    echo ">>> 下载 deps 文件（使用国内镜像）"
    cd "${SCRIPT_DIR}"

    # 优先使用 uv run，回退到系统 python3
    if command -v uv &>/dev/null; then
        uv run download_deps.py --china-mirrors
    elif command -v python3 &>/dev/null; then
        python3 download_deps.py --china-mirrors
    else
        echo "错误：需要 uv 或 python3 来执行 download_deps.py"
        exit 1
    fi

    echo
    echo ">>> 构建本地 deps 镜像: ${DEPS_IMAGE}"
    DOCKER_BUILDKIT=1 docker build \
        --platform "${PLATFORM}" \
        -f Dockerfile.deps \
        -t "${DEPS_IMAGE}" \
        .
    echo ">>> deps 镜像构建完成"
}

ensure_deps_image

# ────────────────────────────────────────────────
# Step 2: 拉取基础镜像
# ────────────────────────────────────────────────
echo
echo ">>> 预拉取 ubuntu:24.04"
docker pull --platform "${PLATFORM}" ubuntu:24.04 || echo "警告：ubuntu:24.04 拉取失败，如本地已有缓存可忽略"

# ────────────────────────────────────────────────
# Step 3: 构建主镜像
# ────────────────────────────────────────────────
echo
echo ">>> 开始 docker build"
DOCKER_BUILDKIT=1 docker build \
    --platform "${PLATFORM}" \
    --build-arg NEED_MIRROR=1 \
    --build-arg HTTP_PROXY="${HTTP_PROXY:-}" \
    --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
    --build-arg NO_PROXY="${NO_PROXY:-}" \
    -f Dockerfile \
    -t "${IMAGE}" \
    .

echo
echo "=== 构建成功: ${IMAGE} ==="
