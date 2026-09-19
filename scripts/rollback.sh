#!/usr/bin/env bash
# 版本回滚脚本（单机 Docker Compose）
#
# 用法：
#   ./scripts/rollback.sh              # 回滚到上一个版本（.release_state.previous）
#   ./scripts/rollback.sh v1.0.0       # 回滚到指定版本
#   STAGING=1 ./scripts/rollback.sh    # 回滚 staging 环境
#
# 注意：回滚只切换应用镜像。若本次发布包含不可逆的数据结构变更，
#       还需用 db_backup.py 恢复数据库（见 README「生产部署与回滚」）。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

STATE_FILE=".release_state"
PREV_FILE=".release_state.previous"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"

log() { printf '[rollback] %s\n' "$*"; }
fail() { printf '[rollback][error] %s\n' "$*" >&2; exit 1; }

COMPOSE_ARGS=(-f docker-compose.yml)
if [[ -n "${STAGING:-}" ]]; then
  COMPOSE_ARGS+=(-f docker-compose.staging.yml)
fi

TARGET_TAG="${1:-$(cat "$PREV_FILE" 2>/dev/null || echo "")}"
[[ -n "$TARGET_TAG" ]] || fail "未找到可回滚的版本，请显式指定版本号：./scripts/rollback.sh <tag>"

env_value() {
  local key="$1" default="$2"
  [[ -f .env ]] || { echo "$default"; return; }
  local value
  value="$(grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- || true)"
  echo "${value:-$default}"
}

HTTP_PORT="$(env_value HTTP_PORT 80)"
CURRENT_TAG="$(cat "$STATE_FILE" 2>/dev/null || echo "unknown")"

log "准备回滚：$CURRENT_TAG → $TARGET_TAG"

IMAGE_TAG="$TARGET_TAG" docker compose "${COMPOSE_ARGS[@]}" pull backend 2>/dev/null || true
IMAGE_TAG="$TARGET_TAG" docker compose "${COMPOSE_ARGS[@]}" up -d

deadline=$((SECONDS + HEALTH_TIMEOUT))
while (( SECONDS < deadline )); do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}/ready" >/dev/null 2>&1; then
    echo "$TARGET_TAG" > "$STATE_FILE"
    [[ "$CURRENT_TAG" != "unknown" ]] && echo "$CURRENT_TAG" > "$PREV_FILE"
    log "回滚完成，当前版本：$TARGET_TAG"
    exit 0
  fi
  sleep 3
done

docker compose "${COMPOSE_ARGS[@]}" logs --tail 80 backend || true
fail "回滚后服务仍未就绪，请立即人工介入"
