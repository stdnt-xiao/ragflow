#!/usr/bin/env bash
# =============================================================================
# RAGFlow 源码开发环境 - 首次安装 & 启动脚本
# 适用平台: macOS (Intel/Apple Silicon)
# 用法: bash dev-setup.sh
# =============================================================================

set -e

RAGFLOW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$RAGFLOW_ROOT/logs/dev"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERR]${NC}  $1"; exit 1; }

mkdir -p "$LOG_DIR"

# ─── 0. 检查 Docker ─────────────────────────────────────────────────────────
info "检查 Docker..."
if ! docker info &>/dev/null; then
  error "Docker 未运行，请先启动 Docker Desktop 后重试。"
fi
success "Docker 运行正常"

# ─── 1. 安装 uv（Python 包管理器）──────────────────────────────────────────
if ! command -v uv &>/dev/null; then
  info "安装 uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
if ! command -v uv &>/dev/null; then
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv &>/dev/null || error "uv 安装失败，请手动安装: https://docs.astral.sh/uv/getting-started/installation/"
success "uv: $(uv --version)"

# ─── 2. 安装 macOS 系统依赖（Homebrew）────────────────────────────────────
BREW=/usr/local/bin/brew
if command -v brew &>/dev/null; then BREW=brew; fi

if [ -x "$BREW" ]; then
  # llvmlite(ranx->numba) 需要 LLVM 20 源码编译（macOS x86_64 无预编译 wheel）
  if [ ! -d "/usr/local/opt/llvm@20" ]; then
    info "安装 LLVM 20（用于编译 llvmlite）..."
    $BREW install llvm@20
  fi
  # xgboost 需要 libomp (OpenMP 运行时)
  if [ ! -d "/usr/local/opt/libomp" ]; then
    info "安装 libomp（xgboost 依赖）..."
    $BREW install libomp
  fi
  # pyodbc 需要 unixodbc
  if [ ! -d "/usr/local/opt/unixodbc" ]; then
    info "安装 unixodbc（pyodbc 依赖）..."
    $BREW install unixodbc
  fi
  # cmake 用于编译 llvmlite
  if ! command -v cmake &>/dev/null; then
    info "安装 cmake..."
    $BREW install cmake
  fi
fi

# ─── 3. 创建 Python 虚拟环境 & 安装依赖 ────────────────────────────────────
cd "$RAGFLOW_ROOT"

if [ ! -d ".venv" ]; then
  info "创建 Python 3.12 虚拟环境（首次耗时较长）..."
  uv sync --python 3.12 --all-extras --exclude-package llvmlite 2>&1 | tail -5 || \
  uv sync --python 3.12 --all-extras 2>&1 | tail -5

  # macOS x86_64 无预编译 llvmlite wheel，需从源码编译
  if [ -d "/usr/local/opt/llvm@20" ] && ! "$RAGFLOW_ROOT/.venv/bin/python" -c "import llvmlite" &>/dev/null 2>&1; then
    info "编译安装 llvmlite（需要 LLVM 20，约需 5 分钟）..."
    "$RAGFLOW_ROOT/.venv/bin/python" -m pip install pip setuptools wheel --quiet || true
    LLVM_CONFIG=/usr/local/opt/llvm@20/bin/llvm-config \
    CMAKE_ARGS="-DLLVM_DIR=/usr/local/opt/llvm@20/lib/cmake/llvm" \
    PATH="/usr/local/opt/llvm@20/bin:$PATH" \
    "$RAGFLOW_ROOT/.venv/bin/python" -m pip install llvmlite==0.46.0 \
      --no-build-isolation --no-cache-dir -q && success "llvmlite 编译完成"
    # 重新同步确保依赖完整
    uv sync --python 3.12 --all-extras 2>&1 | tail -3
  fi
  success "Python 依赖安装完成"
else
  info "虚拟环境已存在，跳过安装（如需重装请删除 .venv 目录）"
fi

# ─── 4. 下载 NLP 模型数据 ───────────────────────────────────────────────────
if [ ! -d "$RAGFLOW_ROOT/nltk_data" ]; then
  info "下载 NLP 模型数据..."
  uv run download_deps.py 2>&1 | tail -5 || warn "download_deps.py 执行失败（可选步骤，可忽略）"
  success "NLP 数据下载完成"
fi

# ─── 5. 启动基础服务 (MySQL/ES/MinIO/Redis) ─────────────────────────────────
info "启动基础 Docker 服务..."
cd "$RAGFLOW_ROOT/docker"
docker compose -f docker-compose-base.yml --profile elasticsearch up -d \
  mysql minio redis es01 2>&1 | tail -5

info "等待 MySQL 健康检查..."
for i in $(seq 1 30); do
  if docker compose -f docker-compose-base.yml exec -T mysql \
       mysqladmin ping -uroot -pinfini_rag_flow &>/dev/null 2>&1; then
    success "MySQL 就绪"
    break
  fi
  [ $i -eq 30 ] && error "MySQL 启动超时（30次健康检查失败）"
  sleep 3
done
cd "$RAGFLOW_ROOT"

# ─── 6. 启动后端 ────────────────────────────────────────────────────────────
info "启动后端服务 (port 9380)..."
# 停止已有后端进程
pkill -f "ragflow_server.py" 2>/dev/null || true
pkill -f "task_executor.py"  2>/dev/null || true
sleep 1

export PYTHONPATH="$RAGFLOW_ROOT"
export NLTK_DATA="$RAGFLOW_ROOT/nltk_data"
export http_proxy=""; export https_proxy=""; export HTTP_PROXY=""; export HTTPS_PROXY=""

PYTHONPATH="$RAGFLOW_ROOT" \
NLTK_DATA="$RAGFLOW_ROOT/nltk_data" \
PYTHONUNBUFFERED=1 \
"$RAGFLOW_ROOT/.venv/bin/python" -u api/ragflow_server.py \
> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$LOG_DIR/backend.pid"
disown $BACKEND_PID 2>/dev/null || true
success "后端已启动 (PID=$BACKEND_PID)，首次加载约需 3-4 分钟，日志: $BACKEND_LOG"

# ─── 7. 安装前端依赖（首次）────────────────────────────────────────────────
cd "$RAGFLOW_ROOT/web"
if [ ! -d "node_modules" ]; then
  info "安装前端依赖（首次耗时较长）..."
  npm install 2>&1 | tail -5
  success "前端依赖安装完成"
fi

# ─── 8. 启动前端开发服务器 ──────────────────────────────────────────────────
info "启动前端开发服务器 (port 5173)..."
pkill -f "vite" 2>/dev/null || true
sleep 1

nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
success "前端已启动 (PID=$FRONTEND_PID)，日志: $FRONTEND_LOG"

# ─── 完成 ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}  RAGFlow 开发环境启动完成！${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo ""
echo -e "  后端 API:    ${BLUE}http://localhost:9380${NC}"
echo -e "  前端界面:    ${BLUE}http://localhost:9222${NC}"
echo ""
echo -e "  后端日志:    tail -f $BACKEND_LOG"
echo -e "  前端日志:    tail -f $FRONTEND_LOG"
echo ""
echo -e "  一键重启:    ${YELLOW}bash $RAGFLOW_ROOT/dev-restart.sh${NC}"
echo ""
