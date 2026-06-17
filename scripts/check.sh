#!/usr/bin/env sh
set -eu

SCRIPT_DIR=${0%/*}
if [ "$SCRIPT_DIR" = "$0" ]; then
  SCRIPT_DIR=.
fi
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
BACKEND_PYTEST="$ROOT_DIR/backend/.venv-codex/bin/pytest"
BACKEND_UNIX_PYTHON="$ROOT_DIR/backend/.venv-codex/bin/python"
BACKEND_PYTHON="$ROOT_DIR/.codex-test-artifacts/backend-venv/Scripts/python.exe"
BACKEND_VENV_PYTHON="$ROOT_DIR/backend/.venv-codex/Scripts/python.exe"

run_backend_pytest() {
  if [ -x "$BACKEND_PYTEST" ]; then
    "$BACKEND_PYTEST" "$@"
  elif [ -x "$BACKEND_PYTHON" ]; then
    "$BACKEND_PYTHON" -m pytest "$@"
  elif [ -x "$BACKEND_VENV_PYTHON" ]; then
    "$BACKEND_VENV_PYTHON" -m pytest "$@"
  else
    pytest "$@"
  fi
}

run_backend_python() {
  if [ -x "$BACKEND_UNIX_PYTHON" ]; then
    "$BACKEND_UNIX_PYTHON" "$@"
  elif [ -x "$BACKEND_PYTHON" ]; then
    "$BACKEND_PYTHON" "$@"
  elif [ -x "$BACKEND_VENV_PYTHON" ]; then
    "$BACKEND_VENV_PYTHON" "$@"
  else
    python "$@"
  fi
}

run_npm() {
  if command -v npm.cmd >/dev/null 2>&1; then
    npm.cmd "$@"
  else
    npm "$@"
  fi
}

echo "== Backend tests =="
BACKEND_TEST_TARGETS=${CHECK_BACKEND_TARGETS:-backend/tests}
(cd "$ROOT_DIR" && {
  # shellcheck disable=SC2086
  run_backend_pytest $BACKEND_TEST_TARGETS -q
})

echo "== Frontend tests =="
(cd "$ROOT_DIR/frontend" && run_npm test)

if [ "${RUN_STAGE7_REACTION_GATE:-0}" = "1" ]; then
  echo "== Stage 7 ReactionPrompt backend focused gate =="
  sh "$ROOT_DIR/scripts/stage7_reaction_backend_gate.sh"

  echo "== Stage 7 ReactionPrompt frontend focused gate =="
  (cd "$ROOT_DIR/frontend" && run_npm run test:stage7:reaction)
else
  echo "== Stage 7 ReactionPrompt focused gates skipped =="
  echo "Set RUN_STAGE7_REACTION_GATE=1 to rerun the focused backend/frontend ReactionPrompt recovery/privacy gates."
fi

if [ "${RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE:-0}" = "1" ]; then
  echo "== Stage 7 Feather Fall browser smoke: accept =="
  (cd "$ROOT_DIR" && node scripts/feather_fall_adventure_browser_smoke.mjs)

  if [ "${RUN_STAGE7_FEATHER_FALL_DECLINE_SMOKE:-0}" = "1" ]; then
    echo "== Stage 7 Feather Fall browser smoke: decline =="
    (cd "$ROOT_DIR" && node scripts/feather_fall_adventure_browser_smoke.mjs --decision decline)
  else
    echo "== Stage 7 Feather Fall decline browser smoke skipped =="
    echo "Set RUN_STAGE7_FEATHER_FALL_DECLINE_SMOKE=1 with RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE=1 to run both accept and decline."
  fi
else
  echo "== Stage 7 Feather Fall browser smoke skipped =="
  echo "Set RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE=1 to run the Adventure Feather Fall browser smoke."
fi

echo "== Frontend build =="
(cd "$ROOT_DIR/frontend" && run_npm run build)

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

  (cd "$ROOT_DIR" && run_backend_python scripts/multiplayer_ws_loadtest.py "$@")
else
  echo "== Multiplayer load smoke skipped =="
  echo "Set RUN_MULTIPLAYER_LOADTEST=1 with LOADTEST_MODULE_ID or LOADTEST_SQLITE_DB to run it."
fi

echo "== All checks passed =="
