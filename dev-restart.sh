#!/usr/bin/env bash
# =============================================================================
# RAGFlow 源码开发环境 - 一键重启脚本
# 用法:
#   bash dev-restart.sh          # 重启前端 + 后端
#   bash dev-restart.sh backend  # 仅重启后端
#   bash dev-restart.sh frontend # 仅重启前端
#   bash dev-restart.sh infra    # 仅重启基础 Docker 服务
# =============================================================================

set -e

RAGFLOW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$RAGFLOW_ROOT/logs/dev"
BACKEND_LOG="$LOG_DIR/backend.log"
TASK_EXECUTOR_LOG="$RAGFLOW_ROOT/logs/task_executor_0.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
TARGET="${1:-all}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERR]${NC}  $1"; exit 1; }

mkdir -p "$LOG_DIR"

# 确保 uv 在 PATH 中
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# ─── 检查前置条件 ────────────────────────────────────────────────────────────
[ ! -d "$RAGFLOW_ROOT/.venv" ] && error "未找到 .venv，请先运行: bash dev-setup.sh"
! docker info &>/dev/null && error "Docker 未运行，请先启动 Docker Desktop"

# ─── 重启基础服务 ────────────────────────────────────────────────────────────
restart_infra() {
  info "重启 Docker 基础服务..."
  cd "$RAGFLOW_ROOT/docker"
  docker compose -f docker-compose-base.yml --profile elasticsearch \
    restart mysql minio redis es01 2>&1 | tail -5
  info "等待 MySQL 就绪..."
  for i in $(seq 1 20); do
    if docker compose -f docker-compose-base.yml exec -T mysql \
         mysqladmin ping -uroot -pinfini_rag_flow &>/dev/null 2>&1; then
      success "MySQL 就绪"
      break
    fi
    [ $i -eq 20 ] && warn "MySQL 健康检查超时，继续重启后端..."
    sleep 2
  done
  cd "$RAGFLOW_ROOT"
}

# ─── 重启后端 ────────────────────────────────────────────────────────────────
restart_backend() {
  info "停止后端进程..."
  pkill -f "ragflow_server.py" 2>/dev/null || true
  pkill -f "task_executor.py"  2>/dev/null || true
  sleep 2

  info "启动后端 (port 9380)..."
  export http_proxy=""; export https_proxy=""; export HTTP_PROXY=""; export HTTPS_PROXY=""

  cd "$RAGFLOW_ROOT"
  PYTHONPATH="$RAGFLOW_ROOT" \
  NLTK_DATA="$RAGFLOW_ROOT/nltk_data" \
  PYTHONUNBUFFERED=1 \
  "$RAGFLOW_ROOT/.venv/bin/python" -u "$RAGFLOW_ROOT/api/ragflow_server.py" \
  > "$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$LOG_DIR/backend.pid"
  disown $BACKEND_PID 2>/dev/null || true
  success "后端已启动 (PID=$BACKEND_PID)，首次加载约需 3-4 分钟"

  info "启动 task_executor..."
  PYTHONPATH="$RAGFLOW_ROOT" \
  NLTK_DATA="$RAGFLOW_ROOT/nltk_data" \
  PYTHONUNBUFFERED=1 \
  "$RAGFLOW_ROOT/.venv/bin/python" -u "$RAGFLOW_ROOT/rag/svr/task_executor.py" 0 \
  >> "$TASK_EXECUTOR_LOG" 2>&1 &
  TASK_PID=$!
  echo $TASK_PID > "$LOG_DIR/task_executor.pid"
  disown $TASK_PID 2>/dev/null || true
  success "task_executor 已启动 (PID=$TASK_PID)"

  # 等待后端健康（最长等 5 分钟）
  info "等待后端就绪（首次启动需下载模型文件，请耐心等待）..."
  for i in $(seq 1 60); do
    if curl --noproxy localhost,127.0.0.1 -sf http://localhost:9380/v1/system/status &>/dev/null 2>&1; then
      success "后端 API 响应正常"
      return 0
    fi
    # 检查进程是否崩溃
    if ! kill -0 $BACKEND_PID &>/dev/null 2>&1; then
      warn "后端进程已退出，查看日志: tail -f $BACKEND_LOG"
      return 1
    fi
    [ $((i % 10)) -eq 0 ] && info "仍在加载... (${i}/60，已等 $((i*5))s)"
    sleep 5
  done
  warn "5 分钟内后端未响应，请查看日志: tail -f $BACKEND_LOG"
}

# ─── 重启前端 ────────────────────────────────────────────────────────────────
restart_frontend() {
  info "停止前端进程..."
  pkill -f "vite" 2>/dev/null || true
  sleep 1

  info "启动前端开发服务器 (port 5173)..."
  cd "$RAGFLOW_ROOT/web"
  nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!
  echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
  success "前端已启动 (PID=$FRONTEND_PID)"
  cd "$RAGFLOW_ROOT"
}

# ─── 执行 ────────────────────────────────────────────────────────────────────
case "$TARGET" in
  backend)
    restart_backend
    ;;
  frontend)
    restart_frontend
    ;;
  infra)
    restart_infra
    ;;
  all|*)
    restart_backend
    restart_frontend
    ;;
esac

# ─── 状态汇总 ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}  重启完成！${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo ""
echo -e "  后端 API:    ${BLUE}http://localhost:9380${NC}"
echo -e "  前端界面:    ${BLUE}http://localhost:9222${NC}"
echo ""
echo -e "  后端日志:    tail -f $BACKEND_LOG"
echo -e "  解析日志:    tail -f $TASK_EXECUTOR_LOG"
echo -e "  前端日志:    tail -f $FRONTEND_LOG"
echo ""

# 打印 Docker 容器状态
echo -e "${YELLOW}Docker 基础服务状态:${NC}"
docker ps --format "  {{.Names}}\t{{.Status}}" \
  --filter "name=docker-mysql-1" \
  --filter "name=docker-redis-1" \
  --filter "name=docker-minio-1" \
  --filter "name=docker-es01-1" 2>/dev/null || \
docker ps --format "  {{.Names}}\t{{.Status}}" 2>/dev/null | head -6
echo ""
