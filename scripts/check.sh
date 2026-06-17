#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BACKEND_PYTEST="$ROOT_DIR/backend/.venv-codex/bin/pytest"

if [ ! -x "$BACKEND_PYTEST" ]; then
  BACKEND_PYTEST="pytest"
fi

echo "== Backend tests =="
(cd "$ROOT_DIR" && "$BACKEND_PYTEST" backend/tests -q)

echo "== Frontend tests =="
(cd "$ROOT_DIR/frontend" && npm test)

if [ "${RUN_STAGE7_REACTION_GATE:-0}" = "1" ]; then
  echo "== Stage 7 ReactionPrompt focused gate =="
  (cd "$ROOT_DIR/frontend" && npm run test:stage7:reaction)
else
  echo "== Stage 7 ReactionPrompt focused gate skipped =="
  echo "Set RUN_STAGE7_REACTION_GATE=1 to rerun the focused ReactionPrompt recovery/privacy gate."
fi

echo "== Frontend build =="
(cd "$ROOT_DIR/frontend" && npm run build)

if [ "${RUN_MULTIPLAYER_LOADTEST:-0}" = "1" ]; then
  echo "== Multiplayer load smoke =="
  LOADTEST_BASE_URL="${LOADTEST_BASE_URL:-http://127.0.0.1:8002}"
  LOADTEST_PREFIX="${LOADTEST_PREFIX:-check_load_$(date +%Y%m%d_%H%M%S)}"

  set -- --base-url "$LOADTEST_BASE_URL" --prefix "$LOADTEST_PREFIX"
  if [ -n "${LOADTEST_MODULE_ID:-}" ]; then
    set -- "$@" --module-id "$LOADTEST_MODULE_ID"
  elif [ -n "${LOADTEST_SQLITE_DB:-}" ]; then
    set -- "$@" --seed-sqlite-module "$LOADTEST_SQLITE_DB"
  else
    echo "RUN_MULTIPLAYER_LOADTEST=1 requires LOADTEST_MODULE_ID or LOADTEST_SQLITE_DB" >&2
    exit 1
  fi

  (cd "$ROOT_DIR" && python scripts/multiplayer_ws_loadtest.py "$@")
else
  echo "== Multiplayer load smoke skipped =="
  echo "Set RUN_MULTIPLAYER_LOADTEST=1 with LOADTEST_MODULE_ID or LOADTEST_SQLITE_DB to run it."
fi

echo "== All checks passed =="
