# Multiplayer Party Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first playable version of multiplayer exploration party groups with per-group pending actions, while preserving the existing DM response and combat flows.

**Architecture:** Backend owns a normalized `session.game_state.multiplayer` structure through focused helper functions in `room_service`. Room APIs expose group state mutations and broadcast full room snapshots. Frontend treats room realtime data as the source of truth, adds a compact Adventure party panel, and lets the current speaker include group intent in the existing DM action path.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, React 19, Vitest, Pytest.

**Status audit 2026-06-15:** Complete on `main`. The current implementation also includes later hardening beyond this original MVP plan: group readiness, active focus switching, room-state snapshot consumption in Adventure/Combat, and redacted split-group pending actions. Keep future Stage 6 work focused on multiplayer pressure, privacy, WS drift, and clean-checkout verification rather than reimplementing this checklist.

---

### Task 1: Backend Multiplayer State Helpers

**Files:**
- Modify: `backend/services/room_service.py`
- Modify: `backend/schemas/room_schemas.py`
- Test: `backend/tests/unit/test_room_multiplayer_state.py`

- [x] Add tests for normalized multiplayer groups:
  - A new room has a default group containing room members.
  - Creating or joining a group moves the user out of other groups.
  - Submitting and clearing group actions only affects that group.
  - Room info exposes `party_groups`, `active_group_id`, and `pending_actions_by_group`.
- [x] Implement the minimal helper API:
  - `ensure_multiplayer_state(db, session_id)`
  - `set_member_group(db, session_id, user_id, group_id, group_name, location)`
  - `submit_group_action(db, session_id, user_id, group_id, action_text)`
  - `clear_group_actions(db, session_id, group_id)`
- [x] Extend `RoomInfo` with the three multiplayer state fields.

### Task 2: Backend Room Endpoints And WS Snapshots

**Files:**
- Modify: `backend/api/rooms.py`
- Modify: `backend/schemas/room_schemas.py`
- Modify: `backend/schemas/ws_events.py`
- Modify: `frontend/src/api/client.js`
- Test: `backend/tests/unit/test_ws_events.py`

- [x] Add request schemas:
  - `SetGroupRequest(group_id, group_name, location)`
  - `SubmitGroupActionRequest(group_id, action_text)`
  - `ClearGroupActionsRequest(group_id)`
- [x] Add endpoints:
  - `POST /game/rooms/{session_id}/groups/join`
  - `POST /game/rooms/{session_id}/groups/actions`
  - `POST /game/rooms/{session_id}/groups/actions/clear`
- [x] Add `RoomStateUpdated` WS event carrying `room: dict`.
- [x] Broadcast `RoomStateUpdated` after group changes.
- [x] Add frontend API client methods.

### Task 3: Frontend Room Realtime Reducers

**Files:**
- Modify: `frontend/src/types/ws.d.ts`
- Modify: `frontend/src/hooks/useRoomRealtime.js`
- Modify: `frontend/src/hooks/useDialogueWsSync.js`
- Modify: `frontend/src/hooks/useCombatPageActions.js`
- Test: `frontend/src/hooks/__tests__/useRoomRealtime.test.js`
- Test: `frontend/src/hooks/__tests__/useDialogueWsSync.test.js`

- [x] Normalize `room_state_updated` payload into room state.
- [x] Add helper `mergeRealtimeRoomEvent(prev, event)`.
- [x] Teach Adventure and Combat WS handlers to consume `room_state_updated`.
- [x] Preserve existing member snapshot behavior.

### Task 4: Adventure Party Panel

**Files:**
- Create: `frontend/src/components/adventure/MultiplayerPartyPanel.jsx`
- Modify: `frontend/src/pages/Adventure.jsx`
- Test: `frontend/src/pages/__tests__/Adventure.smoke.test.jsx`

- [x] Render current groups, members, locations, and pending actions.
- [x] Let a player submit a pending action for their group.
- [x] Let a player create/switch to a named group.
- [x] Let current speaker append pending group actions into the free text submission without changing the backend DM contract.
- [x] Let current speaker clear their group queue after a successful submit.

### Task 5: Verification

**Files:**
- No production files.

- [x] Run focused backend tests:
  - `backend/.venv-codex/bin/pytest backend/tests/unit/test_ws_events.py backend/tests/unit/test_room_multiplayer_state.py -q`
- [x] Run focused frontend tests:
  - `npm test -- src/hooks/__tests__/useRoomRealtime.test.js src/hooks/__tests__/useDialogueWsSync.test.js src/pages/__tests__/Adventure.smoke.test.jsx`
- [ ] Run build:
  - `npm run build`
- [x] Run whitespace check:
  - `git diff --check`

Verification note from the 2026-06-15 takeover audit:

- Backend focused suite: `32 passed`.
- Frontend focused suite: `3 files / 36 passed`.
- Build was not rerun for this docs-only audit.
