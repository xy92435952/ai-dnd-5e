#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/backend/.env}"
BACKEND_PORT="${AI_TRPG_BACKEND_PORT:-8000}"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

warn() {
  echo "WARN: $1" >&2
}

if [ ! -f "$ENV_FILE" ]; then
  fail "missing backend env file: $ENV_FILE"
fi

get_env_value() {
  key="$1"
  value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

ENV_VALUE="$(get_env_value ENV)"
LLM_MODEL="$(get_env_value LLM_MODEL)"
LLM_BASE_URL="$(get_env_value LLM_BASE_URL)"
CORS_ALLOW_ORIGINS="$(get_env_value CORS_ALLOW_ORIGINS)"
DATABASE_URL="$(get_env_value DATABASE_URL)"
LANGGRAPH_DB_URL="$(get_env_value LANGGRAPH_DB_URL)"
JWT_SECRET="$(get_env_value JWT_SECRET)"

[ -n "$LLM_MODEL" ] || fail "LLM_MODEL is required"
[ -n "$LLM_BASE_URL" ] || fail "LLM_BASE_URL is required"
[ -n "$CORS_ALLOW_ORIGINS" ] || fail "CORS_ALLOW_ORIGINS is required"
[ -n "$DATABASE_URL" ] || fail "DATABASE_URL is required"
[ -n "$JWT_SECRET" ] || fail "JWT_SECRET is required"

case "$CORS_ALLOW_ORIGINS" in
  *localhost*|*127.0.0.1*)
    if [ "$ENV_VALUE" = "production" ]; then
      fail "production CORS_ALLOW_ORIGINS must not include localhost"
    else
      warn "CORS_ALLOW_ORIGINS includes local development origins"
    fi
    ;;
esac

if [ "$ENV_VALUE" = "production" ]; then
  case "$DATABASE_URL" in
    postgresql+asyncpg://*) ;;
    *) fail "production DATABASE_URL must use postgresql+asyncpg://" ;;
  esac
  case "$LANGGRAPH_DB_URL" in
    postgresql://*|postgresql+psycopg://*) ;;
    *) fail "production LANGGRAPH_DB_URL must use PostgreSQL" ;;
  esac
  if [ "$JWT_SECRET" = "dev-secret-change-me-at-least-32-bytes" ]; then
    fail "production JWT_SECRET still uses the development placeholder"
  fi
fi

if [ -f "$ROOT_DIR/deploy.sh" ] && ! grep -q -- "--port $BACKEND_PORT" "$ROOT_DIR/deploy.sh"; then
  warn "deploy.sh does not contain backend port $BACKEND_PORT; verify nginx proxy_pass and systemd ExecStart"
fi

echo "deploy env ok: env=${ENV_VALUE:-unset} model=$LLM_MODEL base_url=$LLM_BASE_URL port=$BACKEND_PORT"
