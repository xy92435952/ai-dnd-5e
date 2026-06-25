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

stage7_evidence_files=""

add_stage7_evidence_file() {
  if [ -n "$1" ]; then
    if [ -n "$stage7_evidence_files" ]; then
      stage7_evidence_files="$stage7_evidence_files $1"
    else
      stage7_evidence_files="$1"
    fi
  fi
}

feather_fall_artifact_tag() {
  if [ -n "${FEATHER_FALL_SMOKE_ARTIFACT_TAG:-}" ]; then
    printf '%s' "$FEATHER_FALL_SMOKE_ARTIFACT_TAG"
  else
    date +%Y%m%d
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

if [ "${RUN_STAGE8_COMPREHENSIVE_GATE:-0}" = "1" ]; then
  echo "== Stage 8 comprehensive matrix gate =="
  set --
  if [ "${STAGE8_REQUIRE_STAGE7_5_EVIDENCE:-0}" = "1" ]; then
    set -- "$@" --require-stage7-5-evidence
  fi
  if [ -n "${STAGE8_STAGE7_5_EVIDENCE_FILES:-}" ]; then
    for evidence_file in $STAGE8_STAGE7_5_EVIDENCE_FILES; do
      set -- "$@" --stage7-5-evidence "$evidence_file"
    done
  fi
  (cd "$ROOT_DIR" && node scripts/stage8_comprehensive_gate.mjs "$@")
else
  echo "== Stage 8 comprehensive matrix gate skipped =="
  echo "Set RUN_STAGE8_COMPREHENSIVE_GATE=1 to verify the Stage 8 required-suite matrix."
fi

if [ "${RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE:-0}" = "1" ]; then
  FEATHER_FALL_ARTIFACT_TAG="$(feather_fall_artifact_tag)"
  echo "== Stage 7 Feather Fall browser smoke: accept =="
  (cd "$ROOT_DIR" && node scripts/feather_fall_adventure_browser_smoke.mjs)
  add_stage7_evidence_file "artifacts/browser-feather-fall-adventure-manifest-${FEATHER_FALL_ARTIFACT_TAG}.json"

  if [ "${RUN_STAGE7_FEATHER_FALL_DECLINE_SMOKE:-0}" = "1" ]; then
    echo "== Stage 7 Feather Fall browser smoke: decline =="
    (cd "$ROOT_DIR" && node scripts/feather_fall_adventure_browser_smoke.mjs --decision decline)
    add_stage7_evidence_file "artifacts/browser-feather-fall-adventure-decline-manifest-${FEATHER_FALL_ARTIFACT_TAG}.json"
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
  if [ -z "${LOADTEST_RESULT_JSON:-}" ] && [ "${RUN_STAGE7_EVIDENCE_GATE:-0}" = "1" ]; then
    LOADTEST_RESULT_JSON="artifacts/multiplayer-load-smoke-${LOADTEST_PREFIX}.json"
    echo "LOADTEST_RESULT_JSON not set; writing evidence to $LOADTEST_RESULT_JSON"
  fi

  set -- --base-url "$LOADTEST_BASE_URL" --prefix "$LOADTEST_PREFIX"
  if [ -n "${LOADTEST_MODULE_ID:-}" ]; then
    set -- "$@" --module-id "$LOADTEST_MODULE_ID"
  elif [ -n "${LOADTEST_SQLITE_DB:-}" ]; then
    set -- "$@" --seed-sqlite-module "$LOADTEST_SQLITE_DB"
  else
    echo "RUN_MULTIPLAYER_LOADTEST=1 requires LOADTEST_MODULE_ID or LOADTEST_SQLITE_DB" >&2
    exit 1
  fi
  if [ -n "${LOADTEST_HOLD_SECONDS:-}" ]; then
    set -- "$@" --hold-seconds "$LOADTEST_HOLD_SECONDS"
  fi
  if [ -n "${LOADTEST_RESULT_JSON:-}" ]; then
    set -- "$@" --result-json "$LOADTEST_RESULT_JSON"
    add_stage7_evidence_file "$LOADTEST_RESULT_JSON"
  fi

  (cd "$ROOT_DIR" && run_backend_python scripts/multiplayer_ws_loadtest.py "$@")
else
  echo "== Multiplayer load smoke skipped =="
  echo "Set RUN_MULTIPLAYER_LOADTEST=1 with LOADTEST_MODULE_ID or LOADTEST_SQLITE_DB to run it."
  echo "Set LOADTEST_HOLD_SECONDS to keep sockets open for manual browser observation."
  echo "Set LOADTEST_RESULT_JSON to write a machine-readable load smoke result file."
  echo "If RUN_STAGE7_EVIDENCE_GATE=1 is also set, check.sh writes a default load-smoke result JSON."
fi

if [ "${RUN_STAGE7_POSTDEPLOY_HEALTHCHECK:-0}" = "1" ]; then
  echo "== Stage 7 post-deploy healthcheck =="
  if [ -z "${STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT:-}" ] && [ "${RUN_STAGE7_EVIDENCE_GATE:-0}" = "1" ]; then
    STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT="artifacts/stage7-postdeploy-healthcheck-$(date +%Y%m%d_%H%M%S).json"
    echo "STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT not set; writing evidence to $STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT"
  fi

  set --
  if [ -n "${STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT:-}" ]; then
    set -- "$@" --json --output "$STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT"
  fi
  if [ -n "${STAGE7_POSTDEPLOY_TIMEOUT_MS:-}" ]; then
    set -- "$@" --timeout-ms "$STAGE7_POSTDEPLOY_TIMEOUT_MS"
  fi
  if [ -n "${STAGE7_POSTDEPLOY_HEALTH_URLS:-}" ]; then
    for health_url in $STAGE7_POSTDEPLOY_HEALTH_URLS; do
      set -- "$@" --url "$health_url"
    done
  fi
  if [ -n "${STAGE7_POSTDEPLOY_LOG_FILES:-}" ]; then
    for log_file in $STAGE7_POSTDEPLOY_LOG_FILES; do
      set -- "$@" --log-file "$log_file"
    done
  fi

  (cd "$ROOT_DIR" && node scripts/stage7_postdeploy_healthcheck.mjs "$@")
  if [ -n "${STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT:-}" ]; then
    add_stage7_evidence_file "$STAGE7_POSTDEPLOY_HEALTHCHECK_OUTPUT"
  fi
else
  echo "== Stage 7 post-deploy healthcheck skipped =="
  echo "Set RUN_STAGE7_POSTDEPLOY_HEALTHCHECK=1 after server pull/restart to verify /health and captured logs."
fi

if [ "${RUN_STAGE7_PUBLIC_BROWSER_SMOKE:-0}" = "1" ]; then
  echo "== Stage 7 public browser smoke =="
  if [ -z "${STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT:-}" ] && [ "${RUN_STAGE7_EVIDENCE_GATE:-0}" = "1" ]; then
    STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT="artifacts/stage7-public-browser-smoke-$(date +%Y%m%d_%H%M%S).json"
    echo "STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT not set; writing evidence to $STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT"
  fi

  set --
  if [ -n "${STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT:-}" ]; then
    set -- "$@" --output "$STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT"
  fi
  if [ -n "${STAGE7_PUBLIC_BROWSER_SMOKE_ARTIFACT_TAG:-}" ]; then
    set -- "$@" --artifact-tag "$STAGE7_PUBLIC_BROWSER_SMOKE_ARTIFACT_TAG"
  fi
  if [ -n "${STAGE7_PUBLIC_BROWSER_SMOKE_TIMEOUT_MS:-}" ]; then
    set -- "$@" --timeout-ms "$STAGE7_PUBLIC_BROWSER_SMOKE_TIMEOUT_MS"
  fi
  if [ -n "${STAGE7_PUBLIC_BROWSER_PATH:-}" ]; then
    set -- "$@" --browser-path "$STAGE7_PUBLIC_BROWSER_PATH"
  fi
  if [ -n "${STAGE7_PUBLIC_FRONTEND_ORIGIN:-}" ]; then
    set -- "$@" --frontend-origin "$STAGE7_PUBLIC_FRONTEND_ORIGIN"
  fi
  if [ -n "${STAGE7_PUBLIC_USERNAME:-}" ]; then
    set -- "$@" --username "$STAGE7_PUBLIC_USERNAME"
  fi
  if [ -n "${STAGE7_PUBLIC_PASSWORD:-}" ]; then
    set -- "$@" --password "$STAGE7_PUBLIC_PASSWORD"
  fi
  if [ -n "${STAGE7_PUBLIC_SESSION_ID:-}" ]; then
    set -- "$@" --session-id "$STAGE7_PUBLIC_SESSION_ID"
  fi

  (cd "$ROOT_DIR" && node scripts/stage7_public_browser_smoke.mjs "$@")
  if [ -n "${STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT:-}" ]; then
    add_stage7_evidence_file "$STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT"
  fi
else
  echo "== Stage 7 public browser smoke skipped =="
  echo "Set RUN_STAGE7_PUBLIC_BROWSER_SMOKE=1 after deployment with STAGE7_PUBLIC_FRONTEND_ORIGIN, STAGE7_PUBLIC_USERNAME, STAGE7_PUBLIC_PASSWORD, and STAGE7_PUBLIC_SESSION_ID."
fi

if [ "${RUN_STAGE7_EVIDENCE_GATE:-0}" = "1" ]; then
  stage7_evidence_input=${STAGE7_EVIDENCE_FILES:-$stage7_evidence_files}
  if [ -z "$stage7_evidence_input" ]; then
    echo "RUN_STAGE7_EVIDENCE_GATE=1 needs evidence JSON files." >&2
    echo "Set STAGE7_EVIDENCE_FILES, or run an evidence-producing smoke in the same check script." >&2
    echo "Examples: RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE=1, RUN_MULTIPLAYER_LOADTEST=1 with LOADTEST_MODULE_ID/LOADTEST_SQLITE_DB, RUN_STAGE7_POSTDEPLOY_HEALTHCHECK=1, or RUN_STAGE7_PUBLIC_BROWSER_SMOKE=1." >&2
    exit 1
  fi
  echo "== Stage 7 evidence artifact gate =="
  set -- $stage7_evidence_input
  if [ "${STAGE7_EVIDENCE_NO_FILE_CHECK:-0}" = "1" ]; then
    set -- --no-file-check "$@"
  fi
  (cd "$ROOT_DIR" && node scripts/verify_stage7_evidence.mjs "$@")
else
  echo "== Stage 7 evidence artifact gate skipped =="
  echo "Set RUN_STAGE7_EVIDENCE_GATE=1 to verify smoke result JSON before release handoff."
  echo "Use STAGE7_EVIDENCE_FILES for existing artifacts, or run Feather Fall/load smoke in the same check script for auto-discovery."
fi

if [ "${RUN_STAGE7_DEPLOY_PREFLIGHT:-0}" = "1" ]; then
  echo "== Stage 7 deploy preflight =="
  set --
  if [ "${STAGE7_DEPLOY_PREFLIGHT_ALLOW_DIRTY:-0}" = "1" ]; then
    set -- "$@" --allow-dirty
  fi
  if [ -n "${STAGE7_DEPLOY_PREFLIGHT_FORMAT:-}" ]; then
    set -- "$@" --format "$STAGE7_DEPLOY_PREFLIGHT_FORMAT"
  fi
  if [ -n "${STAGE7_DEPLOY_PREFLIGHT_OUTPUT:-}" ]; then
    set -- "$@" --output "$STAGE7_DEPLOY_PREFLIGHT_OUTPUT"
  fi
  (cd "$ROOT_DIR" && node scripts/stage7_deploy_preflight.mjs "$@")
else
  echo "== Stage 7 deploy preflight skipped =="
  echo "Set RUN_STAGE7_DEPLOY_PREFLIGHT=1 before server pull/restart to verify clean git state and ignored local deploy paths."
fi

echo "== All checks passed =="
