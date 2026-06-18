# Multiplayer WebSocket Load Smoke

This runbook covers the local smoke test for the multiplayer target:
50 users online on one backend, with each game room capped at 4 players.

## Prerequisites

Start the backend first:

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

The script needs a parsed module. To avoid invoking the LLM parser during load
testing, either pass an existing module id whose `parse_status` is `done`, or
let the script seed a temporary ready module directly into the local SQLite DB.

## Standard Check Entrypoint

Prefer the same `scripts/check.sh` entrypoint used by the Stage 7 deployment
checklist. It uses the workspace backend Python resolver on Windows/Git Bash and
keeps the load smoke opt-in.

```powershell
$env:RUN_MULTIPLAYER_LOADTEST = "1"
$env:LOADTEST_SQLITE_DB = "backend/ai_trpg.db"
$env:LOADTEST_PREFIX = "codex_load_YYYYMMDD_HHMM"
$env:LOADTEST_RESULT_JSON = "artifacts/multiplayer-load-smoke-YYYYMMDD_HHMM.json"
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

For a live browser check while the 50 WebSocket clients remain connected, keep
the same entrypoint and add a short hold window:

```powershell
$env:RUN_MULTIPLAYER_LOADTEST = "1"
$env:LOADTEST_SQLITE_DB = "backend/ai_trpg.db"
$env:LOADTEST_PREFIX = "codex_load_YYYYMMDD_HHMM"
$env:LOADTEST_HOLD_SECONDS = "90"
$env:LOADTEST_RESULT_JSON = "artifacts/multiplayer-load-smoke-YYYYMMDD_HHMM.json"
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

When the scripted checks have passed, the script prints a `phase: holding` JSON
line with an observer username, password, room code, and session id. Log in with
that observer account and open `/room/<session_id>` before the hold window ends.

If you want to reuse an existing parsed module instead:

```powershell
$env:RUN_MULTIPLAYER_LOADTEST = "1"
$env:LOADTEST_MODULE_ID = "<ready-module-id>"
$env:LOADTEST_PREFIX = "codex_load_YYYYMMDD_HHMM"
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

For direct low-level script debugging, call `scripts/multiplayer_ws_loadtest.py`
with the matching flags directly.

Set `LOADTEST_RESULT_JSON` through `scripts/check.sh`, or pass
`--result-json artifacts/multiplayer-load-smoke-YYYYMMDD_HHMM.json` directly,
when you want to keep the final users/rooms/WebSocket/timing/cleanup summary as
a machine-readable local evidence file. The `artifacts/` folder is ignored by
git and can be uploaded separately by CI or archived for a release checklist.
Verify the result before release handoff with
`node scripts\verify_stage7_evidence.mjs artifacts\multiplayer-load-smoke-YYYYMMDD_HHMM.json`.
To generate and verify the JSON in one `scripts/check.sh` run, also set
`RUN_STAGE7_EVIDENCE_GATE=1` and set `STAGE7_EVIDENCE_FILES` to the same
`LOADTEST_RESULT_JSON` path.

The default test shape is fixed on purpose:

- 50 registered/logged-in users
- 13 rooms total
- room sizes: 12 rooms with 4 players, 1 room with 2 players
- every room is created with `max_players=4`
- 50 simultaneous WebSocket connections

## What It Verifies

The script checks that:

- the backend health endpoint responds
- users can register or log in
- rooms can be created and joined
- a full 4-player room rejects an overflow join
- all 50 users can connect through WebSocket
- WebSocket ping/pong works for every connection
- room state keeps `max_players=4`
- DM style survives room creation
- party group membership matches room membership
- every room member can read their own room snapshot and members list
- non-members cannot read another room's snapshot or members list
- every room member can restore their own game session snapshot
- non-members cannot restore another room's game session snapshot
- typing events broadcast only inside the sender's room
- typing events do not echo back to the sender
- optional `--hold-seconds` keeps rooms and sockets open for a manual browser
  responsiveness check before cleanup
- created test room members leave, and the rooms are dissolved at the end
- dissolved rooms reject former-member room/session reads with 403
- dissolved room codes reject new joins with 404

## GitHub Actions

Use the manual `Multiplayer Load Smoke` workflow when you want CI to run the
50-user WebSocket smoke. It starts a local backend, seeds a temporary ready
module in SQLite, runs the load script, uploads the backend log and the
machine-readable load smoke result JSON, and then stops the backend.

## Notes

The script intentionally leaves created users in the database so repeated runs
with the same prefix can log them in. Test room members leave through the normal
multiplayer `/leave` endpoint, and the final host leave dissolves each room.
The multiplayer `Session` rows may remain as dissolved room records because the
backend intentionally blocks direct session deletion for multiplayer rooms.
SQLite-seeded modules are cleaned up by default unless `--keep-seeded-module`
is provided.

HTTP calls ignore local proxy environment variables by default so `127.0.0.1`
load runs do not get routed through a system proxy. Pass `--trust-env` only when
you intentionally want the script to honor `HTTP_PROXY` / `HTTPS_PROXY`.
