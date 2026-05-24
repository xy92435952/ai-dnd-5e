# Multiplayer Deep Test Report

> Last verified: 2026-05-23
> Backend: `http://127.0.0.1:8002`
> Frontend: `http://127.0.0.1:3000`
> Chrome CDP: `http://127.0.0.1:9222`

## Summary

The current multiplayer room-to-adventure flow passed a two-user browser smoke test with isolated browser contexts. This run went beyond room start and exercised the real Adventure UI:

- Host and guest were registered as separate users.
- Host created a room and guest joined by room code.
- Both users had claimed player characters.
- Host clicked the real frontend start-adventure button in the browser.
- Both browser contexts navigated to `/adventure/{session_id}`.
- `/ready` reported two active websocket connections before and after Adventure loaded.
- Host submitted a real free action through Adventure.
- The backend advanced speaker ownership from host to guest after the DM response.
- Host, now a non-speaker, submitted a group intent and marked it ready.
- Guest opened the rest UI and started a short-rest vote.
- Host voted yes, the majority threshold was met, and the rest vote resolved.

A follow-up multiplayer Combat browser smoke also passed with two isolated users. It seeded deterministic combat, opened the real Combat UI for host and guest, verified turn-gated controls, rejected guest attempts to operate the host character, passed the turn by clicking the host UI, and confirmed the guest could move their own character after websocket refresh.

An extended multiplayer Combat browser smoke now covers five isolated scenarios with per-scenario cleanup: turn ownership plus movement, deterministic host attack plus damage, a full host -> guest -> enemy AI -> host round cycle, host-owned Shield reaction prompt/resolution, and guest-owned Shield reaction prompt/resolution. Each scenario closes its two browser contexts, ends seeded combat, and waits for `/ready.ws.room_connections` to return to `{}` before continuing.

## Reproduction

```powershell
python scripts\multiplayer_deep_browser_smoke.py `
  --base-api http://127.0.0.1:8002 `
  --base-web http://127.0.0.1:3000 `
  --cdp http://127.0.0.1:9222
```

Combat browser smoke:

```powershell
python scripts\multiplayer_combat_browser_smoke.py `
  --base-api http://127.0.0.1:8002 `
  --base-web http://127.0.0.1:3000 `
  --cdp http://127.0.0.1:9222
```

Extended Combat browser smoke:

```powershell
python scripts\multiplayer_combat_extended_browser_smoke.py `
  --base-api http://127.0.0.1:8002 `
  --base-web http://127.0.0.1:3000 `
  --auto-chrome `
  --max-scenarios 5
```

Both scripts create disposable test data and capture screenshots under `doc/test-artifacts/`.

## Run Evidence

| Field | Value |
| --- | --- |
| `session_id` | `7401ae58-50a7-4528-aaff-44379a78f95f` |
| `room_code` | `327987` |
| host user | `deep_host_b4b6e1` / `dd3f52eb-45ed-4f69-937e-5029b746b63c` |
| guest user | `deep_guest_b4b6e1` / `97c3d3ce-14da-47f2-864e-469e03b0c1f9` |
| host character | `HostHerob4b6e1` |
| guest character | `GuestHerob4b6e1` |
| host URL after click | `http://127.0.0.1:3000/adventure/7401ae58-50a7-4528-aaff-44379a78f95f` |
| guest URL after click | `http://127.0.0.1:3000/adventure/7401ae58-50a7-4528-aaff-44379a78f95f` |
| WS before start | `room_connections[7401ae58-50a7-4528-aaff-44379a78f95f] = 2` |
| WS after Adventure | `room_connections[7401ae58-50a7-4528-aaff-44379a78f95f] = 2` |
| speaker after start | host user id `dd3f52eb-45ed-4f69-937e-5029b746b63c` |
| speaker after host action | guest user id `97c3d3ce-14da-47f2-864e-469e03b0c1f9` |
| speak round | `1` |
| host group intent count | `1` |
| host group readiness | `ready` |
| rest vote created yes count | `1` |
| rest vote after resolve | `null` |

Screenshots:

- `doc/test-artifacts/multiplayer-deep-7401ae58-host-room.png`
- `doc/test-artifacts/multiplayer-deep-7401ae58-host-after-action.png`
- `doc/test-artifacts/multiplayer-deep-7401ae58-rest-vote-resolved.png`
- `doc/test-artifacts/multiplayer-deep-7401ae58-host-adventure.png`
- `doc/test-artifacts/multiplayer-deep-7401ae58-guest-adventure.png`

## Combat Browser Run Evidence

2026-05-22 Combat browser/CDP run:

| Field | Value |
| --- | --- |
| `session_id` | `13d9b632-33c5-4bcc-b44a-bc6fb6ab4667` |
| `room_code` | `775237` |
| host user | `combat_host_4b2fb2` / `f604b17c-5820-4980-ab7d-11c7a03b67b0` |
| guest user | `combat_guest_4b2fb2` / `e100ac6d-87fa-479e-b17f-1bd1da762652` |
| host character | `HostBlade4b2fb2` / `2e6761d4-ad8a-48cf-9fa7-f008b58adb4e` |
| guest character | `GuestBlade4b2fb2` / `33602062-dc2e-4079-bcd9-2a294ac55d8f` |
| seeded enemy | `combat-goblin-4b2fb2` |
| initial WS count | `room_connections[13d9b632-33c5-4bcc-b44a-bc6fb6ab4667] = 2` |
| guest end host turn API check | `403` |
| guest move host character API check | `403` |
| guest move-mode UI state | `✓ 移动` |
| guest final position | `{ "x": 8, "y": 5 }` |
| browser runtime events | `[]` |

Screenshots:

- `doc/test-artifacts/multiplayer-combat-13d9b632-host-turn.png`
- `doc/test-artifacts/multiplayer-combat-13d9b632-guest-waiting.png`
- `doc/test-artifacts/multiplayer-combat-13d9b632-guest-turn.png`
- `doc/test-artifacts/multiplayer-combat-13d9b632-guest-moved.png`

## Extended Combat Browser Run Evidence

2026-05-23 extended Combat browser/CDP run:

| Scenario | Session | Key assertions | Screenshot |
| --- | --- | --- | --- |
| `turn_move` | `b9159c06-b832-47ef-afd5-e525ade8b53b` | guest ending host turn returned `403`; guest moving host returned `403`; host UI end-turn handed off to guest; guest moved to `{ "x": 8, "y": 5 }`; cleanup WS returned to `{}` | `doc/test-artifacts/multiplayer-combat-b9159c06-turn-move-guest-moved.png` |
| `attack_damage` | `a0d5afb1-f99f-4de6-b59d-393d050d8e1d` | guest attacking as host returned `403`; deterministic host attack damaged `combat-goblin-03775f` from `30` to `21`; host turn state recorded `attacks_made = 1`; cleanup WS returned to `{}` | `doc/test-artifacts/multiplayer-combat-a0d5afb1-attack-damage.png` |
| `ai_turn_cycle` | `cb29d8d5-e757-4c1f-b438-1694f2ae02d1` | host ended turn; guest ended turn; frontend-triggered enemy AI turn advanced combat to `round_number = 2` and `current_turn_index = 0`; current turn returned to host character `1d524228-dfb6-40c8-aef1-0fa0de94df12`; cleanup WS returned to `{}` | `doc/test-artifacts/multiplayer-combat-cb29d8d5-ai-turn-cycle.png` |
| `reaction_prompt` | `95b14417-0a49-4548-9158-d1204f63633e` | seeded enemy hit produced a Shield reaction prompt only on the host page; host clicked the real reaction button; pending AI attack was cleared; combat advanced to `round_number = 2`, `current_turn_index = 0`; host gained `shield_spell`; cleanup WS returned to `{}` | `doc/test-artifacts/multiplayer-combat-95b14417-reaction-resolved.png` |
| `guest_reaction_prompt` | `635cf143-d0b3-4502-9fdf-525a252b5e7d` | seeded enemy hit produced a Shield reaction prompt only on the guest page; host page had no reaction prompt; guest clicked the real reaction button; guest pending AI attack was cleared; combat advanced to `round_number = 2`, `current_turn_index = 0`; guest gained `shield_spell`; cleanup WS returned to `{}` | `doc/test-artifacts/multiplayer-combat-635cf143-guest-reaction-resolved.png` |

Additional checks from the run:

- `/ready` before and after the full run showed no stuck websocket rooms outside active scenarios.
- `browser_events` was `[]` for all five scenario results.
- The AI turn screenshot showed a valid nested attack roll label such as `d20=20`, not `d20=undefined`.
- The reaction prompt scenario passed on the first attempt. Browser coverage verifies prompt/resolution/cleanup; backend integration coverage verifies Shield can turn a hit into a miss before damage lands.

## Fixes From This Run

- Fixed the browser smoke script so it exits the opening dialogue stage by waiting for a truly visible free-action input, not just for a DOM node to exist.
- Fixed browser click coordinates for tall/cropped Adventure dialogue buttons by clicking within the visible viewport intersection instead of the full element center.
- Fixed React-controlled input automation in the browser smoke by using the native input value setter and confirming the element is visible before filling.
- Added stable Adventure test IDs for free action, group intent, stage advance, top-bar rest/history/journal controls, and rest vote buttons.
- Implemented multiplayer rest voting as the only rest path for multiplayer sessions.
- Added backend vote endpoints for create, vote, and cancel.
- Added frontend rest-vote UI for Adventure.
- Fixed speaker-turn persistence: `_advance_speaker()` now copies the JSON state, writes `speaker_turn_started_at`, and calls `flag_modified(session, "game_state")` before commit. Without this, the DM response could be logged while room state stayed stuck on the previous speaker.
- Hardened multiplayer Combat action ownership so old player-facing combat endpoints resolve the current user's claimed character instead of blindly using `session.player_character_id`.
- Fixed multiplayer Combat roster hydration so combat state includes all claimed player characters plus companions, not only the host/main player.
- Split frontend Combat gating between "any human player turn" and "my claimed character's turn", so the guest UI stays disabled during the host turn and becomes interactive after turn handoff.
- Added stable Combat UI test IDs and a Combat browser smoke script that waits for move mode before clicking the battlefield.
- Added an extended Combat browser smoke script with isolated turn/move, attack/damage, and AI round-cycle scenarios plus per-scenario browser/WS cleanup.
- Added a deterministic browser-test dice queue hook so UI attack tests are stable without changing normal dice behavior.
- Fixed Combat HUD log dice labels for nested attack results so AI turn logs show `d20=<value>` instead of `d20=undefined`.
- Normalized Combat reaction prompt rendering for backend `available_reactions` and legacy `options` payloads, including stable reaction button test IDs.
- Filtered AI weapon-attack reaction prompts to currently supported/applicable reactions and kept an `options` compatibility alias.
- Broadcast combat updates after reaction resolution so both multiplayer clients refresh after a reaction.
- Serialized AI combat turns with the per-session action lock, broadcast AI turn combat updates, and made duplicate multiplayer AI turn calls idempotent when the turn has already advanced to a player.
- Updated the frontend AI turn hook so skipped duplicate AI calls reconcile latest combat state without adding an empty combat log.
- Extended the Combat browser smoke with a Shield reaction prompt scenario and retry-safe cleanup for non-prompt dice outcomes.
- Moved AI weapon-hit reaction timing before damage settlement for player targets. AI attacks now store a `pending_ai_attack`, Shield/Uncanny Dodge/skip resolve that pending attack, and the turn advances only after the reaction choice is settled.
- Updated frontend reaction handling so Skip reaction calls the backend settlement path and reaction responses can update HP, turn index, and combat-over state directly.
- Scoped AI attack reaction prompts to the actual targeted player character. Each client now derives prompts from its own character's `pending_ai_attack`, direct AI prompt returns only render on the matching client, and duplicate AI-turn requests pause while any pending reaction is unresolved.
- Extended the Combat browser smoke with a guest-owned Shield reaction scenario and a `--scenario` selector for targeted reruns.

## Regression Coverage

- Backend rest vote integration covers direct multiplayer rest rejection plus majority-approved rest application.
- Frontend `RestModal` tests cover single-player direct rest and multiplayer voting states.
- WebSocket realtime integration now verifies both the `dm_speak_turn` event and the persisted room `current_speaker_user_id`.
- Browser deep smoke now verifies room start, Adventure navigation, two websocket connections, speaker rotation, group intent readiness, and rest vote resolution.
- Backend Combat/multiplayer regression: `80 passed in 24.71s` for `test_combat_endpoints.py`, `test_combat_rules_endpoints.py`, `test_multiplayer_flow.py`, `test_multiplayer_ws_realtime.py`, and `test_imports.py`.
- Frontend Combat focused regression: `12 passed` test files and `26 passed` tests across dice overlay, Combat HUD controls/logs, battlefield, quick inventory, multiplayer turn bar, turn controls, AI turns, player actions, spell flow, and special actions.
- `python -m py_compile scripts\multiplayer_combat_extended_browser_smoke.py` passed.
- `python -m py_compile backend\api\combat\ai_turn.py backend\api\combat\ai_turn_context.py backend\api\combat\ai_turn_attack.py backend\api\combat\reactions.py scripts\multiplayer_combat_extended_browser_smoke.py` passed.
- Backend focused reaction/AI regression passed: `6 passed, 18 deselected`.
- Backend Combat regression passed: `216 passed` across `backend/tests/unit/test_combat_*.py`, `test_combat_endpoints.py`, and `test_combat_rules_endpoints.py`.
- Frontend focused reaction/AI regression passed: `3 passed` files and `8 passed` tests.
- Frontend focused reaction/AI/log regression passed: `4 passed` files and `9 passed` tests.
- Frontend focused reaction/AI/log regression passed: `5 passed` files and `15 passed` tests.
- Extended Combat browser smoke passed with `--max-scenarios 5`, including turn/move, attack/damage, AI round-cycle, host Shield reaction prompt, and guest Shield reaction prompt scenarios.
- `npm run build` passed.
- `git diff --check` passed with Windows line-ending warnings only.

## 50-User Smoke

The 50-user HTTP smoke is a server-level online concurrency check: 50 simultaneous authenticated users across independent sessions/rooms. It is not a single-game party size target; the normal multiplayer game/table remains designed around 4 players unless room configuration is explicitly changed.

The smoke passed in the earlier 2026-05-22 run after fixing local proxy handling in the smoke script and bearer-token rate-limit identity in the backend.

Command:

```powershell
python scripts\load_smoke_50.py `
  --base-url http://127.0.0.1:8002 `
  --users 50 `
  --concurrency 10 `
  --username-prefix load_smoke_202605221830 `
  --forwarded-for-prefix 10.252.0.
```

Earlier result:

```text
elapsed=17.04s users=50 concurrency=10
requests=200 failures=0
auth.register: count=50 ok=50 p50=1766.6ms p95=3575.7ms max=3832.8ms statuses=[200]
auth.me: count=50 ok=50 p50=206.0ms p95=917.3ms max=1674.2ms statuses=[200]
game.sessions: count=50 ok=50 p50=264.1ms p95=1211.4ms max=1674.6ms statuses=[200]
ready: count=50 ok=50 p50=184.5ms p95=1345.8ms max=1404.6ms statuses=[200]
```

Follow-up Combat verification run:

```powershell
python scripts\load_smoke_50.py `
  --base-url http://127.0.0.1:8002 `
  --users 50 `
  --concurrency 10 `
  --username-prefix lc22522 `
  --forwarded-for-prefix 10.253.1.
```

```text
elapsed=18.41s users=50 concurrency=10
requests=200 failures=0
auth.me: count=50 ok=50 p50=326.1ms p95=1176.0ms max=2101.1ms statuses=[200]
auth.register: count=50 ok=50 p50=1534.1ms p95=4063.1ms max=4220.3ms statuses=[200]
game.sessions: count=50 ok=50 p50=329.8ms p95=894.4ms max=2102.2ms statuses=[200]
ready: count=50 ok=50 p50=299.5ms p95=920.2ms max=1500.6ms statuses=[200]
```

One discarded smoke attempt used a username prefix longer than the auth limit after numeric suffixing and failed at registration with `用户名长度需要 2-30 个字符`. The successful run above used the shorter `lc22522` prefix.

2026-05-23 room-isolation smoke:

This run specifically verifies the corrected 4-vs-50 boundary: 50 online users were distributed into independent multiplayer rooms of size 4. The smoke created `13` rooms (`12` full 4-player rooms plus one 2-player room), verified each player only saw their own room members, verified no room exceeded `max_players=4`, verified an outsider could not join a full room, and verified cross-room reads of room info, member list, and session detail were rejected with `403`.

Small preflight:

```powershell
python scripts\load_smoke_50.py `
  --base-url http://127.0.0.1:8002 `
  --users 8 `
  --concurrency 4 `
  --username-prefix ri8f1 `
  --forwarded-for-prefix 10.254.8. `
  --room-isolation `
  --room-size 4
```

```text
elapsed=4.11s users=8 concurrency=4 room_isolation=true room_size=4
requests=77 failures=0
room.create: count=2 ok=2 statuses=[200]
room.join: count=6 ok=6 statuses=[200]
room.get: count=8 ok=8 statuses=[200]
room.isolation: count=8 ok=8
room.size_cap: count=8 ok=8
room.full_reject: count=1 ok=1 statuses=[409]
room.cross_read_reject: count=1 ok=1 statuses=[403]
room.cross_members_reject: count=1 ok=1 statuses=[403]
session.cross_read_reject: count=1 ok=1 statuses=[403]
```

Full 50-user isolation run:

```powershell
python scripts\load_smoke_50.py `
  --base-url http://127.0.0.1:8002 `
  --users 50 `
  --concurrency 10 `
  --username-prefix ri50f1 `
  --forwarded-for-prefix 10.254.50. `
  --room-isolation `
  --room-size 4
```

```text
elapsed=21.61s users=50 concurrency=10 room_isolation=true room_size=4
requests=455 failures=0
auth.register: count=50 ok=50 p50=1563.8ms p95=3775.0ms max=4273.5ms statuses=[200]
auth.me: count=50 ok=50 p50=479.5ms p95=1178.2ms max=1179.1ms statuses=[200]
game.sessions: count=50 ok=50 p50=398.2ms p95=944.3ms max=1036.6ms statuses=[200]
ready: count=50 ok=50 p50=241.8ms p95=930.5ms max=1172.4ms statuses=[200]
room.create: count=13 ok=13 p50=1695.3ms p95=3019.8ms max=3461.5ms statuses=[200]
room.join: count=37 ok=37 p50=17.6ms p95=36.2ms max=54.7ms statuses=[200]
room.get: count=50 ok=50 p50=20.7ms p95=38.8ms max=138.8ms statuses=[200]
room.isolation: count=50 ok=50
room.size_cap: count=50 ok=50
room.expected_count: count=1 ok=1
room.full_reject: count=1 ok=1 statuses=[409]
room.cross_read_reject: count=1 ok=1 statuses=[403]
room.cross_members_reject: count=1 ok=1 statuses=[403]
session.cross_read_reject: count=1 ok=1 statuses=[403]
```

Post-run health:

- `GET /ready` returned `200`.
- `GET /ready.ws` returned `404` because the current backend exposes websocket stats inside `/ready`, not as a standalone route. This run did not open browser WebSocket connections; the room-isolation smoke is HTTP-only.
- Focused backend checks passed after the run: `2 passed, 29 deselected` for room/session isolation and `7 passed, 17 deselected` for AI-turn/reaction combat authorization.

2026-05-23 API authorization hardening:

Follow-up backend isolation work tightened the remaining high-risk ID-based endpoints after the 50-user room-isolation smoke. The new guardrails require authenticated access for character detail/progression/inventory, module detail/delete, single-player session creation, multiplayer room creation by module, skill-check logging, and combat condition mutations. Private modules can only be read, deleted, or used to start sessions/rooms by their owner; shared modules (`user_id=None`) remain readable/usable but cannot be deleted by normal users. Player-created characters are now stored with `user_id`, and inventory mutations require control of the source character while target characters must belong to the same authorized session.

Verification:

```powershell
python -m pytest backend/tests/integration/test_authorization_boundaries.py backend/tests/integration/test_character_progression_endpoints.py backend/tests/integration/test_inventory_endpoints.py -q
python -m pytest backend/tests/integration/test_game_flow.py backend/tests/integration/test_full_game_flow.py -q
python -m pytest backend/tests/integration/test_multiplayer_flow.py -k "get_room_returns_full_info or room_queries_reject_non_members or host_creates_room_gets_room_code or start_game_after_claim_works or claim_character_binds_to_member" -q
python -m pytest backend/tests/integration/test_combat_endpoints.py -k "get_combat_state_returns_entities or get_skill_bar or end_turn_advances_round or condition_add_and_remove or end_combat_clears_flag" -q
python -m py_compile backend\api\deps.py backend\api\characters.py backend\api\character_create.py backend\api\character_inventory.py backend\api\modules.py backend\api\game_routes\sessions.py backend\api\game_routes\checks.py backend\api\combat\conditions.py backend\services\room_lifecycle_service.py backend\tests\integration\test_authorization_boundaries.py backend\tests\integration\test_inventory_endpoints.py backend\tests\integration\test_character_progression_endpoints.py
```

```text
22 passed
18 passed
5 passed, 26 deselected
5 passed, 19 deselected
py_compile passed
```

2026-05-24 WebSocket/action-lock isolation hardening:

This pass targeted the runtime isolation surface behind the 50-user/4-player-room boundary. The server still treats one multiplayer table as a small room, but concurrent rooms now have stronger protection against state collisions:

- `backend/api/rooms.py` wraps room state mutations in the per-session action lock, including join-by-code, leave, host operations, character claim, split-party group actions/readiness/focus, rest vote create/vote/cancel, and room info normalization reads.
- `backend/api/ws.py` wraps `speak_done` speaker advancement in the same per-session action lock.
- Join-by-code now resolves the target room session first and locks by that session id, so simultaneous joins to one room cannot race past `max_players=4`.
- WebSocket manager regression coverage confirms the same user can be connected to multiple independent rooms without one connection replacing or disconnecting the other.
- WebSocket route regression coverage confirms non-members are rejected before accept, and disconnecting a user from one room does not mark that same user offline in another room.
- Multi-room group regression coverage confirms two rooms can use the same group id while pending actions, readiness maps, and `room_state_updated` broadcasts stay scoped to their own `session_id`.

Verification:

```powershell
python -m py_compile backend\api\rooms.py backend\api\ws.py backend\tests\unit\test_ws_manager.py backend\tests\unit\test_session_action_lock.py backend\tests\integration\test_multiplayer_ws_realtime.py backend\tests\integration\test_multiplayer_flow.py
python -m pytest backend/tests/unit/test_ws_manager.py backend/tests/unit/test_session_action_lock.py backend/tests/integration/test_multiplayer_ws_realtime.py -q
python -m pytest backend/tests/integration/test_multiplayer_flow.py -k "concurrent_join_never_exceeds_room_size or second_player_joins_via_room_code or party_group_endpoints_update_room_snapshot or group_state_and_broadcasts_are_session_scoped or multiplayer_rest_requires_vote_and_majority_applies_rest" -q
python -m pytest backend/tests/unit/test_room_multiplayer_state.py backend/tests/unit/test_multiplayer_dm_agent.py backend/tests/unit/test_game_multiplayer_service.py -q
python -m pytest backend/tests/integration/test_game_flow.py::test_player_action_succeeds backend/tests/integration/test_game_flow.py::test_player_action_stream_sends_narrative_delta_before_final -q
python -m pytest backend/tests/integration/test_authorization_boundaries.py -q
python -m pytest backend/tests/integration/test_multiplayer_flow.py -q
python -m pytest backend/tests/integration/test_combat_endpoints.py -k "get_combat_state_returns_entities or get_skill_bar or end_turn_advances_round or condition_add_and_remove or end_combat_clears_flag" -q
git diff --check
```

```text
py_compile passed
8 passed
5 passed, 28 deselected
19 passed
2 passed
6 passed
33 passed
5 passed, 19 deselected
git diff --check passed with Windows line-ending warnings only
```

2026-05-24 current-code 50-user room-isolation smoke:

This run started the current backend code on a disposable local server and an isolated SQLite database under `.codex-test-artifacts`, so it did not mutate the normal `backend/ai_trpg.db` development database. Rate limiting was disabled for the local smoke server to measure room/session isolation rather than auth throttling.

Server setup:

- Backend URL: `http://127.0.0.1:8012`
- Test DB: `.codex-test-artifacts/smoke-50-20260524.sqlite`
- LangGraph DB: `.codex-test-artifacts/smoke-50-20260524-langgraph.sqlite`
- Startup readiness: `/ready` returned `200` with `rate_limit_enabled=false`, `ws.connections=0`, and `session_action_locks.locked_sessions=0`.

Command:

```powershell
python scripts\load_smoke_50.py `
  --base-url http://127.0.0.1:8012 `
  --users 50 `
  --concurrency 10 `
  --username-prefix wsf24 `
  --forwarded-for-prefix 10.254.52. `
  --room-isolation `
  --room-size 4 `
  --db-path .codex-test-artifacts\smoke-50-20260524.sqlite
```

Result:

```text
elapsed=18.63s users=50 concurrency=10 room_isolation=true room_size=4
requests=455 failures=0
auth.register: count=50 ok=50 p50=1462.4ms p95=3257.1ms max=3651.9ms statuses=[200]
auth.me: count=50 ok=50 p50=213.0ms p95=766.0ms max=1038.3ms statuses=[200]
game.sessions: count=50 ok=50 p50=213.9ms p95=884.9ms max=1367.4ms statuses=[200]
ready: count=50 ok=50 p50=208.4ms p95=728.7ms max=1038.5ms statuses=[200]
room.create: count=13 ok=13 p50=1699.7ms p95=2475.0ms max=2601.3ms statuses=[200]
room.join: count=37 ok=37 p50=10.4ms p95=38.7ms max=327.1ms statuses=[200]
room.get: count=50 ok=50 p50=9.1ms p95=50.5ms max=177.4ms statuses=[200]
room.isolation: count=50 ok=50
room.size_cap: count=50 ok=50
room.expected_count: count=1 ok=1
room.full_reject: count=1 ok=1 statuses=[409]
room.cross_read_reject: count=1 ok=1 statuses=[403]
room.cross_members_reject: count=1 ok=1 statuses=[403]
session.cross_read_reject: count=1 ok=1 statuses=[403]
```

Post-run readiness:

- `/ready` returned `200`.
- `session_action_locks.tracked_sessions=13`, matching the 13 created rooms.
- `session_action_locks.locked_sessions=0`, confirming no stuck room locks.
- `ws.rooms=0`, `ws.connections=0`, `ws.users=0`, and `ws.room_connections={}`, confirming no stuck websocket state from this HTTP-only smoke.
- The disposable uvicorn process was stopped after the run.

## Notes

The browser run captured transient websocket warnings during route transition and context cleanup. The final readiness state still confirmed two active websocket connections during Adventure, and the scripted gameplay assertions passed. A future stricter browser gate can filter route-cleanup warnings separately from runtime errors while pages remain open.

The Combat browser smoke closes the two CDP contexts on success. Before the successful Combat run, `/ready` still showed older websocket connections left by previous failed browser attempts, but this run's own `session_id` was released after completion and no browser runtime events were captured.
