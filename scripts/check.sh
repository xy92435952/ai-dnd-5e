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

echo "== Frontend build =="
(cd "$ROOT_DIR/frontend" && npm run build)

echo "== All checks passed =="
