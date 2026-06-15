# Stage 7 Deployment Smoke Checklist

Last updated: 2026-06-15

This checklist is the deployment-readiness gate for the current Stage 7 work.
It focuses on rule trust, multiplayer privacy/reconnect behavior, ReactionPrompt
recovery, combat-log readability, and production build safety.

## Scope

Run this checklist before deploying `main`, before a long manual playtest, or
after changing any of these areas:

- backend combat rules, resources, HP, conditions, saves, reactions, or rests
- multiplayer rooms, WebSocket events, reconnect/session restore, or privacy projection
- frontend combat/adventure reload paths, ReactionPrompt, or combat logs
- API response schemas, OpenAPI, generated frontend API types, or deployment config

## Quick Local Gate

Use this for small frontend-only or test-only slices:

```powershell
git status --short --branch --untracked-files=all
git log --oneline --decorate -8

cd frontend
npm run test -- <focused-test-files>
npm run build
cd ..

git diff --check
```

For backend-only slices:

```powershell
git status --short --branch --untracked-files=all
git log --oneline --decorate -8

.codex-test-artifacts\backend-venv\Scripts\python.exe -m py_compile <touched-python-files>
.codex-test-artifacts\backend-venv\Scripts\python.exe -m pytest <focused-pytest-targets> -q

git diff --check
```

If `.codex-test-artifacts\backend-venv\Scripts\python.exe` is not present, use
the active backend virtualenv or `python` from the shell.

## Standard Release Gate

Run this when a slice affects shared behavior, multiplayer, schemas, or deploy
confidence:

```powershell
git status --short --branch --untracked-files=all
git log --oneline --decorate -8

.codex-test-artifacts\backend-venv\Scripts\python.exe -m pytest backend\tests\smoke\test_imports.py -q
.codex-test-artifacts\backend-venv\Scripts\python.exe -m pytest backend\tests\unit\test_ws_events.py backend\tests\integration\test_multiplayer_ws_realtime.py -q

cd frontend
npm test
npm run build
cd ..

git diff --check
```

For a narrower but faster multiplayer reconnect gate, use:

```powershell
.codex-test-artifacts\backend-venv\Scripts\python.exe -m pytest `
  backend\tests\integration\test_multiplayer_ws_realtime.py::test_multiplayer_guest_reaction_uses_guest_character_and_broadcasts_update `
  backend\tests\integration\test_multiplayer_ws_realtime.py::test_multiplayer_counterspell_prompt_broadcasts_to_guest_reactor_and_cancels_spell `
  -q

cd frontend
npm run test -- src\utils\__tests__\combatSession.test.js src\hooks\__tests__\useCombatPageActions.test.js
npm run build
cd ..
```

## Schema Gate

Run this whenever backend request/response schemas, route payloads, or generated
types may have changed:

```powershell
cd backend
python scripts\export_openapi.py
cd ..\frontend
npm run types:api
cd ..

git diff -- backend\openapi.json frontend\src\types\api.d.ts
```

Commit `backend/openapi.json` and `frontend/src/types/api.d.ts` only when the
schema change is intentional.

## Production-Build Gate

The CI workflow includes a production dependency build job named
`frontend-prod-build`. It exists because production deploys may install only
runtime dependencies before running `npm run build`.

To reproduce that locally in a disposable checkout or after restoring
`node_modules`:

```powershell
cd frontend
npm ci --omit=dev
npm run build
```

Do not run `npm ci --omit=dev` in the active working tree unless you are ready
to reinstall normal dev dependencies afterwards.

## Manual Local Smoke

Start the app:

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8002

cd ..\frontend
npm run dev
```

Verify:

- `http://127.0.0.1:8002/health` returns healthy JSON.
- `http://127.0.0.1:3000` loads the frontend without console-breaking errors.
- Login or register works.
- A seeded or uploaded module can open an Adventure session.
- Adventure choice clicks, free-text action, and skill-check prompts respond.
- Combat loads, movement/attack/spell/end-turn work, and combat logs explain the result.
- ReactionPrompt appears only for the correct character and clears after accept/decline.
- A browser refresh during a pending reaction restores only that viewer's own prompt.
- A second player/observer does not see another player's private pending prompt text.

## Seeded Single-Player Smoke

Use the smoke seed when you need a repeatable local state without live module
parsing or LLM calls:

```powershell
cd backend
python seed_smoke_scenario.py --slug codex_smoke
```

Useful variants:

```powershell
python seed_smoke_scenario.py --slug codex_reaction --variant reaction
python seed_smoke_scenario.py --slug codex_death_save --variant death-save
```

See `docs/smoke-seed-scenario.md` for cleanup commands and seeded credentials.

## Multiplayer Load Smoke

Run only when the backend is already listening on `127.0.0.1:8002` and you want
the 50-user WebSocket gate:

```powershell
python scripts\multiplayer_ws_loadtest.py `
  --base-url http://127.0.0.1:8002 `
  --seed-sqlite-module backend\ai_trpg.db `
  --prefix codex_load_YYYYMMDD_HHMM
```

For a manual browser check while sockets remain open, add:

```powershell
  --hold-seconds 90
```

The GitHub Actions workflow `Multiplayer Load Smoke` runs the same style of
check on demand.

Latest local dry-run evidence:

- 2026-06-15: `scripts\multiplayer_ws_loadtest.py --base-url http://127.0.0.1:8002 --seed-sqlite-module <temp-db> --prefix stage7_load_20260615_1936` passed against a temporary SQLite backend DB. Result: 50 users, 13 rooms, 50 WebSocket connections, room sizes `4x12 + 2`, seeded module cleanup OK, room leave cleanup OK, dissolved-room access checks returned expected 403/404 responses, and backend log scan found no `ERROR`/`Traceback`/`500` lines.

## Deployment Checks

Before server pull/restart:

```powershell
git status --short
git check-ignore -v backend\.env frontend\dist backend\.venv
```

After server update:

- backend process is restarted if backend code or dependencies changed
- frontend `dist/` was rebuilt if frontend code changed
- nginx or reverse proxy still preserves WebSocket upgrade headers
- production `CORS_ALLOW_ORIGINS` contains the public frontend origin
- `JWT_SECRET`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, database paths/URLs,
  upload path, and Chroma/LangGraph paths are set in `backend/.env`

Health checks:

```bash
curl -s http://127.0.0.1:8000/health
curl -s https://your-domain.example/api/health
```

Log checks:

```bash
sudo journalctl -u ai-trpg -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

## Stop Conditions

Do not deploy when any of these are true:

- `git status --short` shows uncommitted source changes not included in the deploy.
- focused tests pass but the affected shared path has no adjacent regression.
- schema changed but OpenAPI and generated frontend types were not refreshed.
- multiplayer private prompt tests fail or were skipped after changing WS/snapshot/reconnect code.
- `npm run build` fails or the production-only build guard is known broken.
- health check fails locally or on the server after restart.
