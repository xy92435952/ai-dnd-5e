# Stage 7 Deployment Smoke Checklist

Last updated: 2026-06-18

This checklist is the deployment-readiness gate for the current Stage 7 work.
It focuses on rule trust, multiplayer privacy/reconnect behavior, ReactionPrompt
recovery, reaction combat-log readability, and production build safety.

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
npm run test:stage7:reaction
npm run build
cd ..

& 'C:\Program Files\Git\bin\bash.exe' scripts/stage7_reaction_backend_gate.sh
git diff --check
```

For a fast standard-entry smoke of `scripts/check.sh` without running the full
backend suite, provide a focused backend target. The script still runs the full
frontend Vitest suite and production build:

```powershell
$env:CHECK_BACKEND_TARGETS='backend/tests/unit/test_ws_events.py::TestSampleEvents::test_reaction_prompt_projection_uses_compact_reactor_identity'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

To include the focused Stage 7 ReactionPrompt backend and frontend gates in the
existing full local check script, run:

```powershell
$env:RUN_STAGE7_REACTION_GATE='1'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

On Windows, prefer the explicit Git Bash path above. `scripts/check.sh` will use
the workspace backend test venv when present, including for the optional
multiplayer load smoke, and routes frontend commands through `npm.cmd` when Git
Bash exposes it, avoiding the WSL shell shim.

To include the browser-level Adventure Feather Fall smoke in the same check
entrypoint, opt in explicitly because it starts temporary backend/frontend
processes and drives Chrome/Edge:

```powershell
$env:RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE='1'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

To run both Feather Fall accept and decline browser paths from `scripts/check.sh`:

```powershell
$env:RUN_STAGE7_FEATHER_FALL_BROWSER_SMOKE='1'
$env:RUN_STAGE7_FEATHER_FALL_DECLINE_SMOKE='1'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
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

& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
git diff --check
```

By default `scripts/check.sh` runs `backend/tests -q`, full frontend Vitest,
and `npm run build`, while leaving slower optional Stage 7 browser/load smokes
disabled. Use `CHECK_BACKEND_TARGETS` only for a deliberate focused smoke, not
for the full release gate.

For a narrower but faster multiplayer reconnect gate, use:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' scripts/stage7_reaction_backend_gate.sh

cd frontend
npm run test:stage7:reaction
npm run build
cd ..
```

`npm run test:stage7:reaction` includes the direct combat `ReactionPrompt`,
Adventure `ExplorationReactionPrompt`, `useDialogueWsSync`, and
`combatReactionPrompt` utility regressions in addition to Adventure/Combat page
smoke, hook recovery, privacy projection, and combat-log coverage. Keep new
frontend ReactionPrompt or Adventure WS recovery tests in that gate.

## CI Release Gate

The GitHub Actions workflow `.github/workflows/ci.yml` mirrors the deploy-safe
parts of the local release gate:

- `backend` installs backend dependencies, runs the full backend pytest suite,
  runs the named `Run Stage 7 reaction backend gate` step, and verifies
  `backend/openapi.json` is current.
- `frontend` installs frontend dependencies, verifies generated REST API types,
  runs full Vitest, runs the named `Run Stage 7 reaction frontend gate` step,
  and builds with full dependencies.
- `frontend-prod-build` installs production-only frontend dependencies with
  `npm ci --omit=dev` and verifies `npm run build` still succeeds.

The slower browser and multiplayer load smokes remain explicit local or
on-demand checks. Use the local commands below when a slice touches Feather Fall
Adventure reaction UX, live browser behavior, WebSocket fan-out, reconnect
behavior, or manual multiplayer observation.

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

Latest local dry-run evidence:

- 2026-06-15: `npm ci --omit=dev` followed by `npm run build` passed in an isolated detached worktree under `.codex-test-artifacts`, leaving the active `frontend/node_modules` untouched. The prod-only install reported npm audit findings (`2 moderate`, `4 high`) but completed successfully; the production Vite build transformed 281 modules and produced the expected `dist/` bundle.
- 2026-06-15: dependency audit cleanup upgraded direct production frontend dependencies to `axios@^1.18.0`, `react-router-dom@^7.17.0`, and `vite@^8.0.16`, pulling patched production transitive versions `follow-redirects@1.16.0`, `react-router@7.17.0`, and `postcss@8.5.15`. `npm audit fix` then patched the remaining dev-only `brace-expansion` chain to `brace-expansion@1.1.15`. Both `npm audit --omit=dev` and full `npm audit` reported 0 vulnerabilities after the cleanup.

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
- Exploration Feather Fall prompts restore in Adventure, spend the caster's 1st-level
  slot on accept, prevent the saved fall damage, and leave refresh clear of stale
  `pending_exploration_reaction`.
- Exploration Feather Fall decline remains private in multiplayer: only the reactor
  can answer, the triggering player gets no private prompt, decline applies the
  saved fall damage without spending the slot, and both viewers refresh without
  stale `pending_exploration_reaction`.

For a focused automated multiplayer check of that non-combat prompt privacy:

```powershell
.codex-test-artifacts\backend-venv\Scripts\python.exe -m pytest `
  backend\tests\integration\test_multiplayer_ws_realtime.py::test_multiplayer_exploration_feather_fall_prompt_is_private_across_ws_and_refresh `
  -q
```

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
python seed_smoke_scenario.py --slug codex_feather_fall --variant feather-fall
```

See `docs/smoke-seed-scenario.md` for cleanup commands and seeded credentials.

For the Feather Fall variant, login as the printed seeded user, open the
Adventure session, confirm the pending Feather Fall panel is visible, then call
or click the exploration reaction accept path. A successful smoke should show
`combat_active=false`, remove `pending_exploration_reaction` after resolution,
keep the player HP unchanged, spend the AI caster's `1st` spell slot, and add a
Feather Fall reaction dice/log row.

For a repeatable browser-level check of that Adventure prompt, run:

```powershell
node scripts\feather_fall_adventure_browser_smoke.mjs --artifact-tag YYYYMMDD
node scripts\feather_fall_adventure_browser_smoke.mjs --decision decline --artifact-tag YYYYMMDD
```

The browser smoke starts a temporary SQLite-backed backend on `127.0.0.1:8002`,
starts Vite on `127.0.0.1:3000` when needed, logs in as the seeded user, opens
the seeded Adventure page, verifies the Feather Fall panel text, clicks either
`Cast Feather Fall` or `Decline`, verifies the prompt clears, checks HP/slot
state through refresh, and writes prompt/resolved screenshots plus a JSON
manifest under `artifacts/`. If `--artifact-tag` or
`FEATHER_FALL_SMOKE_ARTIFACT_TAG` is omitted, the script uses the current local
date as `YYYYMMDD`.

Latest local dry-run evidence:

- 2026-06-17: `node scripts\feather_fall_adventure_browser_smoke.mjs --decision decline` passed against a temporary SQLite backend DB and exited cleanly. The run restored the same seeded Adventure prompt, clicked `Decline`, confirmed `pending_exploration_reaction` cleared, applied the saved 6 fall damage so player HP became `22/28`, left the caster's `1st` slot at `1`, and wrote `artifacts\browser-feather-fall-adventure-decline-prompt-20260617.png` plus `artifacts\browser-feather-fall-adventure-decline-resolved-20260617.png`.
- 2026-06-17: `node scripts\feather_fall_adventure_browser_smoke.mjs` passed against a temporary SQLite backend DB and exited cleanly. The run restored the seeded Adventure prompt, verified the panel text included Feather Fall, Mara Quickstep, Smoke Sentinel, Gatehouse drop shaft, and `Prevents 6 fall damage`, clicked `Cast Feather Fall`, confirmed `pending_exploration_reaction` cleared, kept player HP at `28/28`, spent the caster's `1st` slot to `0`, and wrote `artifacts\browser-feather-fall-adventure-prompt-20260617.png` plus `artifacts\browser-feather-fall-adventure-resolved-20260617.png`.
- 2026-06-15: `seed_smoke_scenario.py` was run against a temporary SQLite backend DB for `standard`, `reaction`, and `death-save` variants. A real local backend on `127.0.0.1:8002` then verified `/auth/login`, `/game/sessions/{session_id}`, and `/game/combat/{session_id}` for all three seeded users. The same run consumed the reaction variant's pending Shield prompt through `/game/combat/{session_id}/reaction`, preventing 9 damage, restoring HP to 28, spending the 1st-level slot, and clearing `pending_attack_reaction`; it also submitted a death save with `d20_value=12`, updating death saves from `1/1` to `2/1`. Backend log scan found no `ERROR`/`Traceback`/`500` lines.

## Multiplayer Load Smoke

Run only when the backend is already listening on `127.0.0.1:8002` and you want
the 50-user WebSocket gate:

```powershell
$env:RUN_MULTIPLAYER_LOADTEST='1'
$env:LOADTEST_SQLITE_DB='backend\ai_trpg.db'
$env:LOADTEST_PREFIX='codex_load_YYYYMMDD_HHMM'
$env:LOADTEST_RESULT_JSON='artifacts\multiplayer-load-smoke-YYYYMMDD_HHMM.json'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

`scripts/check.sh` runs this load smoke with the same backend Python resolver as
the pytest gates. To target an existing parsed module instead of seeding a
SQLite module, set `LOADTEST_MODULE_ID` instead of `LOADTEST_SQLITE_DB`.

For a manual browser check while sockets remain open, keep the same standard
entrypoint and add a hold window:

```powershell
$env:RUN_MULTIPLAYER_LOADTEST='1'
$env:LOADTEST_SQLITE_DB='backend\ai_trpg.db'
$env:LOADTEST_PREFIX='codex_load_YYYYMMDD_HHMM'
$env:LOADTEST_HOLD_SECONDS='90'
$env:LOADTEST_RESULT_JSON='artifacts\multiplayer-load-smoke-YYYYMMDD_HHMM.json'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

For direct low-level script debugging, pass the same hold window as
`--hold-seconds 90` to `scripts\multiplayer_ws_loadtest.py`. Pass
`--result-json artifacts\multiplayer-load-smoke-YYYYMMDD_HHMM.json`, or set
`LOADTEST_RESULT_JSON` through `scripts/check.sh`, to keep the final load-smoke
summary as an ignored local evidence file under `artifacts/`.

The GitHub Actions workflow `Multiplayer Load Smoke` runs the same style of
check on demand, verifies the load-smoke result JSON with
`scripts/verify_stage7_evidence.mjs`, and uploads both the backend log and the
load-smoke result JSON artifact for later review.

Latest local dry-run evidence:

- 2026-06-15: `scripts\multiplayer_ws_loadtest.py --base-url http://127.0.0.1:8002 --seed-sqlite-module <temp-db> --prefix stage7_load_20260615_1936` passed against a temporary SQLite backend DB. Result: 50 users, 13 rooms, 50 WebSocket connections, room sizes `4x12 + 2`, seeded module cleanup OK, room leave cleanup OK, dissolved-room access checks returned expected 403/404 responses, and backend log scan found no `ERROR`/`Traceback`/`500` lines.

## Deployment Checks

Keep the local or CI evidence from this checklist with the release note:

- Stage 7 reaction backend/frontend gate output
- Feather Fall browser smoke JSON manifest and screenshots when Adventure
  reaction UX changed
- Multiplayer load smoke result JSON and backend log when WS, rooms, reconnect,
  or privacy changed
- CI `frontend-prod-build` result when frontend dependencies or build tooling
  changed

Verify machine-readable smoke evidence before handoff:

```powershell
node scripts\verify_stage7_evidence.mjs artifacts\browser-feather-fall-adventure-manifest-YYYYMMDD.json
node scripts\verify_stage7_evidence.mjs artifacts\browser-feather-fall-adventure-decline-manifest-YYYYMMDD.json
node scripts\verify_stage7_evidence.mjs artifacts\multiplayer-load-smoke-YYYYMMDD_HHMM.json
```

The same verifier can run from the standard local check entrypoint after the
frontend build and any optional evidence-producing browser/load smokes:

```powershell
$env:RUN_STAGE7_EVIDENCE_GATE='1'
$env:STAGE7_EVIDENCE_FILES='artifacts\browser-feather-fall-adventure-manifest-YYYYMMDD.json artifacts\browser-feather-fall-adventure-decline-manifest-YYYYMMDD.json artifacts\multiplayer-load-smoke-YYYYMMDD_HHMM.json'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

When checking a downloaded GitHub Actions JSON artifact without its sibling
screenshots or local result path, add `--no-file-check` to the direct verifier
command, or set `STAGE7_EVIDENCE_NO_FILE_CHECK=1` when using `scripts/check.sh`.

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
- deployment evidence links point to either local `artifacts/` files or GitHub
  Actions artifacts for the release candidate

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

After restart, run at least one browser session through login, Adventure load,
and Combat load on the public origin. When multiplayer or WS paths changed,
open two users in the same room and confirm:

- both clients show connected realtime sync
- private ReactionPrompt or exploration reaction text only appears for the
  reactor
- refresh restores the reactor's own pending prompt and does not leak it to an
  observer
- server logs stay free of `Traceback`, `ERROR`, and `500` during the check

## Stop Conditions

Do not deploy when any of these are true:

- `git status --short` shows uncommitted source changes not included in the deploy.
- focused tests pass but the affected shared path has no adjacent regression.
- schema changed but OpenAPI and generated frontend types were not refreshed.
- multiplayer private prompt tests fail or were skipped after changing WS/snapshot/reconnect code.
- `npm run build` fails or the production-only build guard is known broken.
- health check fails locally or on the server after restart.
- required smoke artifacts are missing for the area changed, or the result JSON
  has `ok: false`.
- server logs show `Traceback`, `ERROR`, or repeated `500` responses during the
  post-restart browser check.
