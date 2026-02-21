#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/.openclaw/workspace"
PY_SCRIPT="$ROOT_DIR/im-php-pg/scripts/main_agent_room_reply.py"
ENV_FILE="$ROOT_DIR/im-php-pg/.env.chatroom-reply"
LOCK_FILE="$ROOT_DIR/im-php-pg/runtime/chatroom_reply.lock"

if [[ ! -f "$PY_SCRIPT" ]]; then
  echo "[$(date '+%F %T')] [chatroom-reply] script not found: $PY_SCRIPT" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

export IM_BASE_URL="${IM_BASE_URL:-http://127.0.0.1:18080}"
export IM_USERNAME="${IM_USERNAME:-zhouzhou_reply}"
export IM_PASSWORD="${IM_PASSWORD:-12345678}"
export IM_NICKNAME="${IM_NICKNAME:-周周}"
export IM_SKILL_KEY="${IM_SKILL_KEY:-im-skill-2026}"
export IM_STATE_DIR="${IM_STATE_DIR:-/root/.openclaw/workspace/im-php-pg/runtime}"
export IM_AGENT_SESSION_ID="${IM_AGENT_SESSION_ID:-room-main-live}"
export IM_REPLIED_CACHE_LIMIT="${IM_REPLIED_CACHE_LIMIT:-600}"

# Cron 模式：单次执行，拉取新消息并回复后退出
export IM_RUN_ONCE=1

mkdir -p "$IM_STATE_DIR"

# 防重入：上一轮还未结束时，本轮直接跳过
if ! flock -n "$LOCK_FILE" -c "timeout 55 /usr/bin/python3 '$PY_SCRIPT'"; then
  echo "[$(date '+%F %T')] [chatroom-reply] skipped (running or timeout)"
  exit 0
fi

echo "[$(date '+%F %T')] [chatroom-reply] tick ok"
