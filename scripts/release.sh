#!/usr/bin/env bash
# 生产发布脚本（单机 Docker Compose + PostgreSQL）
#
# 流程：前置检查 → 发布前数据库备份 → 构建带版本镜像 → 滚动更新 → 健康检查 → 失败自动回滚
#
# 用法：
#   ./scripts/release.sh                 # 以时间戳作为版本号发布
#   ./scripts/release.sh v1.0.0          # 指定版本号
#   STAGING=1 ./scripts/release.sh       # 发布到 staging（叠加 docker-compose.staging.yml）
#
# 回滚：
#   ./scripts/rollback.sh                # 回滚到上一个版本
#   ./scripts/rollback.sh v0.9.0         # 回滚到指定版本
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

IMAGE_REPO="fire-ai-agent-backend"
STATE_FILE=".release_state"
PREV_FILE=".release_state.previous"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"

log() { printf '[release] %s\n' "$*"; }
fail() { printf '[release][error] %s\n' "$*" >&2; exit 1; }

COMPOSE_ARGS=(-f docker-compose.yml)
if [[ -n "${STAGING:-}" ]]; then
  COMPOSE_ARGS+=(-f docker-compose.staging.yml)
fi
if [[ -n "${WITH_MONITORING:-}" ]]; then
  COMPOSE_ARGS+=(-f deploy/docker-compose.monitoring.yml)
fi

TAG="${1:-$(date +%Y%m%d_%H%M%S)}"

env_value() {
  # 从 .env 读取变量，避免 source 整个文件带来的副作用
  local key="$1" default="$2"
  [[ -f .env ]] || { echo "$default"; return; }
  local value
  value="$(grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- || true)"
  echo "${value:-$default}"
}

wait_ready() {
  local port="$1" deadline=$((SECONDS + HEALTH_TIMEOUT))
  while (( SECONDS < deadline )); do
    if curl -fsS "http://127.0.0.1:${port}/ready" >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  return 1
}

log "开始发布，版本：$TAG"

# ---------- 1. 前置检查 ----------
[[ -f .env ]] || fail "缺少 .env，请先执行 cp .env.example .env 并填写必填项"
command -v docker >/dev/null 2>&1 || fail "未找到 docker 命令"
docker info >/dev/null 2>&1 || fail "Docker 守护进程不可用"

HTTP_PORT="$(env_value HTTP_PORT 80)"
CONTAINER_PREFIX="$(env_value CONTAINER_PREFIX fire_ai)"

# ---------- 2. 发布前备份 ----------
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_PREFIX}_backend$"; then
  log "执行发布前数据库备份"
  if docker compose "${COMPOSE_ARGS[@]}" exec -T backend python db_backup.py backup; then
    log "备份完成"
  else
    fail "发布前备份失败，已中止发布（如需跳过请设置 SKIP_BACKUP=1）"
  fi
else
  log "未检测到运行中的后端容器，跳过发布前备份"
fi

# ---------- 3. 记录当前版本 ----------
CURRENT_TAG="$(cat "$STATE_FILE" 2>/dev/null || echo "")"
if [[ -n "$CURRENT_TAG" ]]; then
  echo "$CURRENT_TAG" > "$PREV_FILE"
  log "当前版本：$CURRENT_TAG（已记录用于回滚）"
else
  log "未发现历史版本记录（首次发布）"
fi

# ---------- 4. 构建 ----------
log "构建镜像 ${IMAGE_REPO}:${TAG}"
IMAGE_TAG="$TAG" docker compose "${COMPOSE_ARGS[@]}" build backend

# ---------- 5. 数据库结构迁移 ----------
# 表结构由 Alembic 版本化。默认 DB_AUTO_MIGRATE=true，应用启动时自行迁移；
# 若显式设为 false，则在这里用新镜像先迁移，失败即中止（旧版本仍在跑）。
if [[ "$(env_value DB_AUTO_MIGRATE true)" == "true" ]]; then
  log "跳过显式迁移：DB_AUTO_MIGRATE=true，由应用启动时迁移"
else
  log "执行数据库结构迁移（alembic upgrade head）"
  if IMAGE_TAG="$TAG" docker compose "${COMPOSE_ARGS[@]}" run --rm --no-deps -T backend \
       alembic upgrade head; then
    log "迁移完成"
  else
    fail "数据库迁移失败，已中止发布（旧版本仍在运行）"
  fi
fi

# ---------- 6. 滚动更新 ----------
log "启动新版本容器"
IMAGE_TAG="$TAG" docker compose "${COMPOSE_ARGS[@]}" up -d

# ---------- 7. 健康检查 ----------
log "等待服务就绪（最长 ${HEALTH_TIMEOUT}s）：http://127.0.0.1:${HTTP_PORT}/ready"
if wait_ready "$HTTP_PORT"; then
  echo "$TAG" > "$STATE_FILE"
  log "发布成功，当前版本：$TAG"
  log "查看状态：docker compose ${COMPOSE_ARGS[*]} ps"
  exit 0
fi

# ---------- 7. 失败自动回滚 ----------
printf '[release][error] 健康检查未通过，开始自动回滚\n' >&2
docker compose "${COMPOSE_ARGS[@]}" logs --tail 80 backend || true

if [[ -n "$CURRENT_TAG" ]]; then
  log "回滚到 $CURRENT_TAG"
  HTTP_PORT="$HTTP_PORT" IMAGE_TAG="$CURRENT_TAG" \
    docker compose "${COMPOSE_ARGS[@]}" up -d
  if wait_ready "$HTTP_PORT"; then
    printf '[release][error] 已回滚到 %s，请排查本次发布问题\n' "$CURRENT_TAG" >&2
  else
    printf '[release][error] 回滚后仍未就绪，请立即人工介入\n' >&2
  fi
else
  printf '[release][error] 无历史版本可回滚，请人工介入\n' >&2
fi
exit 1
