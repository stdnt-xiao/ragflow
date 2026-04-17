#!/bin/bash
# 在中国大陆构建 RAGFlow 镜像的辅助脚本
# 用法：
#   ./build-cn.sh                       # 构建 slim 镜像（不含大模型权重）
#   TAG=nightly ./build-cn.sh           # 指定 tag
#
# 前置条件：
#   1. 配置 Docker daemon 的 registry mirror（见 README-CN-BUILD.md）
#   2. 已安装 docker buildx
set -euo pipefail

TAG="${TAG:-nightly}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE="${IMAGE:-infiniflow/ragflow:${TAG}}"

echo "=== 构建 RAGFlow 镜像 (国内网络优化) ==="
echo "    IMAGE    = ${IMAGE}"
echo "    PLATFORM = ${PLATFORM}"
echo "    NEED_MIRROR = 1"
echo

# 预拉取依赖镜像（需要 Docker daemon 配置了 registry mirror 才能快速拉取）
echo ">>> 预拉取 infiniflow/ragflow_deps:latest"
docker pull --platform "${PLATFORM}" infiniflow/ragflow_deps:latest || {
    echo "拉取失败，请先配置 /etc/docker/daemon.json 的 registry-mirrors"
    exit 1
}

echo ">>> 预拉取 ubuntu:24.04"
docker pull --platform "${PLATFORM}" ubuntu:24.04

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
