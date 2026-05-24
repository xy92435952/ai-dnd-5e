# Multiplayer Experience Test Matrix

> Status: active QA baseline for the AI DnD platform.
> Scope: single-player and multiplayer sessions on the current single-worker closed-beta runtime.
> Party-size boundary: one multiplayer game is designed around a 4-player room; the 50-user target means 50 concurrent online users across independent rooms/sessions, not 50 players in one game.

This matrix is the project baseline for making multiplayer feel playable while keeping single-player stable. It should be updated whenever room flow, WebSocket events, Adventure, Combat, voting, or turn ownership changes.

## Quality Gates

| Gate | Command or procedure | Pass condition |
| --- | --- | --- |
| Frontend focused regression | `cd frontend && npm test -- --run src/hooks/__tests__/useAdventureRoom.test.js src/pages/__tests__/Adventure.smoke.test.jsx` | No single-player Adventure page calls multiplayer room lookup; Adventure mounts without hook/TDZ errors. |
| Backend room/session regression | `python -m pytest backend/tests/integration/test_game_flow.py::test_get_session_shape backend/tests/integration/test_multiplayer_flow.py -k "get_room_returns_full_info or room_queries_reject_non_members"` | `/game/sessions/{id}` returns correct `is_multiplayer` and `room_code` for members; non-members cannot read room info, room members, or multiplayer session detail. |
| Backend ID-boundary regression | `python -m pytest backend/tests/integration/test_authorization_boundaries.py backend/tests/integration/test_character_progression_endpoints.py backend/tests/integration/test_inventory_endpoints.py -q` | Cross-user private modules, cross-session skill checks, character reads/mutations, inventory mutations, and multiplayer combat condition changes are rejected before they can leak or mutate another table/session. |
| Backend WS/action-lock isolation | `python -m pytest backend/tests/unit/test_ws_manager.py backend/tests/unit/test_session_action_lock.py backend/tests/integration/test_multiplayer_ws_realtime.py -q` and `python -m pytest backend/tests/integration/test_multiplayer_flow.py -k "concurrent_join_never_exceeds_room_size or group_state_and_broadcasts_are_session_scoped" -q` | Same-user multi-room websocket connections do not replace each other; non-members cannot connect; disconnect is session-scoped; same-session actions serialize; different sessions can proceed in parallel; concurrent joins cannot exceed the 4-player room cap; same group ids in different rooms do not share state or broadcasts. |
| Backend action entry regression | `python -m pytest backend/tests/integration/test_game_flow.py::test_player_action_succeeds backend/tests/integration/test_game_flow.py::test_player_action_stream_sends_narrative_delta_before_final` | Normal and streaming action entrypoints still work with session action locking. |
| Smoke import/route check | `python -m pytest backend/tests/smoke/test_imports.py` | Route surface is still registered. |
| Browser deep test | `python scripts\multiplayer_deep_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --cdp http://127.0.0.1:9222` | Room start, Adventure navigation, host free action, speaker rotation, group intent readiness, and rest vote resolution all pass. |
| Combat browser deep test | `python scripts\multiplayer_combat_extended_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --auto-chrome --max-scenarios 5` | Turn ownership plus movement, deterministic attack/damage, host -> guest -> enemy AI -> host round cycle, host Shield reaction prompt/resolution, and guest Shield reaction prompt/resolution all pass; each scenario cleans browser contexts and returns WS room connections to zero. |
| Closed-beta readiness | `curl -s http://127.0.0.1:8000/ready` | 200 response before player access is opened. |

## Core Manual/E2E Scenarios

| ID | Area | Setup | Steps | Expected result | Automated coverage |
| --- | --- | --- | --- | --- | --- |
| SP-01 | Single-player Adventure | Authenticated user, existing playable session. | Open Adventure, perform a free action, resolve a skill check choice. | No `/game/rooms/{session_id}` request, DM response appears, d20 flow works. | `Adventure.smoke.test.jsx`, `useAdventureRoom.test.js`; browser deep test required. |
| SP-02 | Single-player Combat | Single-player session with active combat. | Open Combat, move, attack, end turn, AI turn. | No room endpoint lookup, turn state updates, HP/logs stay consistent. | Combat endpoint tests; focused `useCombatMultiplayer` regression still needs a current test file. |
| MP-01 | Room creation/join | Two authenticated users. | Host creates room, guest joins by code. | Both see same room members and host id; session detail reports `is_multiplayer=true`. | `test_get_room_returns_full_info`. |
| MP-02 | Character claim | Host and guest in a room. | Each claims a character; one user attempts to claim another user's character. | Valid claims broadcast; duplicate claim is rejected. | `test_multiplayer_flow.py` claim tests. |
| MP-03 | Start game | Room has required player/AI composition. | Host starts game. | Adventure route opens; current speaker is set; guest receives WS update. | Multiplayer flow tests plus browser deep test. |
| MP-04 | Speaking turn | Multiplayer Adventure. | Current speaker acts; non-speaker tries to act. | Current speaker succeeds; non-speaker is blocked unless using approved group/table flow; speaker rotation is persisted in room state. | Multiplayer flow tests, WS realtime test, browser deep test. |
| MP-05 | Rest vote | Multiplayer Adventure. | Player starts rest vote; other eligible player votes yes/no; host cancels. | Vote state broadcasts; approved vote applies rest; rejected/cancelled vote does not; direct multiplayer rest is rejected. | Rest vote integration test, RestModal component test, browser deep test. |
| MP-06 | Creative action vote | Multiplayer Adventure. | Player proposes a creative action; eligible players vote. | Majority approval executes DM action once; rejection produces no DM action. | Creative vote integration and component tests. |
| MP-07 | Disconnect/reconnect | Multiplayer Adventure with active room. | Close guest tab, wait offline threshold, reconnect. | Online state and current speaker recover; no private logs leak to host or other players. | WS tests plus browser deep test. |
| MP-07B | Same user in multiple rooms | One account belongs to two active rooms. | Open one WS connection per room, then disconnect only one room. | The disconnected room marks the user offline; the other room remains connected and online; broadcasts stay scoped by `session_id`. | `test_same_user_ws_disconnect_is_session_scoped`, `test_same_user_can_stay_connected_to_independent_rooms`. |
| MP-08 | Multiplayer Combat turn ownership | Multiplayer session in combat. | Host and guest try actions during each other's turns. | Only current actor can mutate combat; all clients refresh on combat updates. | Combat permission tests plus `multiplayer_combat_extended_browser_smoke.py`. |
| MP-10 | Multiplayer Combat full round cycle | Multiplayer session seeded with host, guest, and one enemy. | Host ends turn; guest ends turn; enemy AI acts; host regains the turn. | Combat advances to round 2, host controls re-enable, AI attack logs render a real d20 value, and cleanup leaves no stuck WS connections. | `multiplayer_combat_extended_browser_smoke.py` scenario `ai_turn_cycle`. |
| MP-11 | Multiplayer Combat host reaction prompt | Multiplayer session seeded with a host character that knows Shield and a pending enemy attack. | Host sees the Shield prompt; guest page is checked for absence of the prompt; host clicks the reaction button. | Reaction prompt appears only on the host client; Shield consumes the reaction, applies `shield_spell`, broadcasts combat update, and cleanup leaves no stuck WS connections. | Reaction endpoint tests plus `multiplayer_combat_extended_browser_smoke.py` scenario `reaction_prompt`. |
| MP-12 | Multiplayer Combat guest reaction prompt | Multiplayer session seeded with a guest character that knows Shield and a pending enemy attack. | Guest sees the Shield prompt; host page is checked for absence of the prompt; guest clicks the reaction button. | Reaction prompt appears only on the guest client; Shield consumes the guest reaction, clears guest `pending_ai_attack`, applies `shield_spell`, and cleanup leaves no stuck WS connections. | Reaction endpoint tests plus `multiplayer_combat_extended_browser_smoke.py` scenario `guest_reaction_prompt`. |
| MP-09 | Group/focus table flow | Multiplayer Adventure with split groups. | Submit pending actions in two groups; set readiness; trigger action. | Table decision processes/switches focus without leaking private group text. | `test_multiplayer_dm_agent.py`, room state tests. |
| MP-09B | Cross-room group isolation | Two rooms both use the same split-party group id. | Submit pending actions/readiness in both rooms and observe broadcasts. | Pending actions and readiness maps remain session-local; `room_state_updated` broadcasts only target the room's session. | `test_group_state_and_broadcasts_are_session_scoped`. |
| OPS-01 | 50-user closed-beta smoke | Running backend and frontend against test DB. | Run `python scripts/load_smoke_50.py --base-url http://127.0.0.1:8002 --users 50 --concurrency 10 --forwarded-for-prefix 10.252.0.` for lightweight readiness; run `python scripts/load_smoke_50.py --base-url http://127.0.0.1:8002 --users 50 --concurrency 10 --username-prefix ri50f1 --forwarded-for-prefix 10.254.50. --room-isolation --room-size 4` for room isolation. | 50 independent online users can hit auth/session/ready paths concurrently; with `--room-isolation`, users are split into 4-player rooms, no room exceeds 4, full rooms reject outsiders, and cross-room room/session reads return `403`. This is a server concurrency check, not a 50-player room. | Load smoke script plus room/session isolation tests. |

## Last Verified Deep Run

2026-05-22 browser/CDP run:

- Script: `python scripts\multiplayer_deep_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --cdp http://127.0.0.1:9222`
- Session: `7401ae58-50a7-4528-aaff-44379a78f95f`
- Host and guest both reached `/adventure/7401ae58-50a7-4528-aaff-44379a78f95f`.
- `/ready.ws.room_connections[session_id]` was `2` before start and `2` after Adventure loaded.
- Host submitted a real Adventure free action, and `current_speaker_user_id` advanced from host to guest.
- Host then submitted a group intent and marked it ready while not the current speaker.
- Guest started a short-rest vote; host voted yes; the majority threshold resolved the vote to `null`.
- Evidence screenshots use the `doc/test-artifacts/multiplayer-deep-7401ae58-*` prefix.
- 50-user HTTP smoke passed with `200` requests and `0` failures.
- Detailed evidence: `doc/Multiplayer_Deep_Test_Report.md`.

2026-05-22 Combat browser/CDP run:

- Script: `python scripts\multiplayer_combat_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --cdp http://127.0.0.1:9222`
- Session: `13d9b632-33c5-4bcc-b44a-bc6fb6ab4667`
- Host and guest both reached `/combat/13d9b632-33c5-4bcc-b44a-bc6fb6ab4667`.
- Initial host controls were enabled; initial guest controls were disabled while host owned the turn.
- Guest direct API attempts to end the host turn and move the host character both returned `403`.
- Host clicked the real end-turn button; guest controls became enabled through websocket refresh.
- Guest enabled move mode and moved to `{ x: 8, y: 5 }`.
- Evidence screenshots use the `doc/test-artifacts/multiplayer-combat-13d9b632-*` prefix.
- Combat-focused backend regression passed with `80` tests; frontend Combat regression passed with `43` tests; `npm run build` passed.

2026-05-23 extended Combat browser/CDP run:

- Script: `python scripts\multiplayer_combat_extended_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --auto-chrome --max-scenarios 5`
- `turn_move` session `b9159c06-b832-47ef-afd5-e525ade8b53b`: guest direct API attempts to end host turn and move host character returned `403`; guest moved to `{ x: 8, y: 5 }` after UI handoff.
- `attack_damage` session `a0d5afb1-f99f-4de6-b59d-393d050d8e1d`: deterministic host attack damaged `combat-goblin-03775f` from `30` to `21`; guest attack-as-host returned `403`.
- `ai_turn_cycle` session `cb29d8d5-e757-4c1f-b438-1694f2ae02d1`: host and guest clicked real end-turn buttons; frontend-triggered enemy AI advanced to round `2` and returned turn index `0` to the host.
- `reaction_prompt` session `95b14417-0a49-4548-9158-d1204f63633e`: host saw the Shield prompt, guest did not; host clicked the real reaction button, pending AI attack cleared, combat advanced to round `2`, and `shield_spell` was applied.
- `guest_reaction_prompt` session `635cf143-d0b3-4502-9fdf-525a252b5e7d`: guest saw the Shield prompt, host did not; guest clicked the real reaction button, guest pending AI attack cleared, combat advanced to round `2`, and `shield_spell` was applied to guest.
- Every scenario reported `ready_after_cleanup.ws = { rooms: 0, connections: 0, users: 0, room_connections: {} }`.
- Evidence screenshots use the `doc/test-artifacts/multiplayer-combat-b9159c06-*`, `doc/test-artifacts/multiplayer-combat-a0d5afb1-*`, `doc/test-artifacts/multiplayer-combat-cb29d8d5-*`, `doc/test-artifacts/multiplayer-combat-95b14417-*`, and `doc/test-artifacts/multiplayer-combat-635cf143-*` prefixes.
- Focused backend reaction/AI regression passed with `6` tests; the broader backend Combat regression passed with `216` tests; frontend focused reaction/AI/log regression passed with `5` files and `15` tests; `npm run build` passed.

2026-05-23 50-user room-isolation run:

- Script: `python scripts\load_smoke_50.py --base-url http://127.0.0.1:8002 --users 50 --concurrency 10 --username-prefix ri50f1 --forwarded-for-prefix 10.254.50. --room-isolation --room-size 4`
- Result: `455` requests, `0` failures, elapsed `21.61s`.
- Room split: `13` rooms for `50` users (`12` full 4-player rooms plus one 2-player room).
- Room metrics: `room.create=13`, `room.join=37`, `room.get=50`, `room.isolation=50`, `room.size_cap=50`.
- Isolation boundaries: full room outsider join returned `409`; cross-room `GET /game/rooms/{session_id}`, `/members`, and `/game/sessions/{session_id}` returned `403`.
- Follow-up focused tests passed: room/session isolation `2 passed`, AI-turn/reaction combat authorization `7 passed`.

2026-05-24 WebSocket/action-lock isolation run:

- Room state mutation routes now use the per-session action lock for join, leave, host operations, character claim, split-party group state, rest vote state, and room info normalization.
- `speak_done` speaker advancement now uses the same per-session action lock.
- Concurrent join regression passed: with host plus four simultaneous guests and `max_players=4`, exactly three joins succeeded, one join returned `409`, and final member count was `4`.
- Same-user multi-room websocket regression passed: the same user can stay connected to two rooms, and disconnecting one room does not mark them offline in the other.
- Cross-room group isolation regression passed: two rooms using group id `scout` kept separate pending actions/readiness and only broadcast `room_state_updated` to their own session.
- Verification passed: `8 passed` for WS manager/action lock/WS realtime; `5 passed, 28 deselected` for focused multiplayer flow; full `test_multiplayer_flow.py` passed with `33 passed`; adjacent room/DM/action/auth/combat checks also passed; `git diff --check` had only Windows line-ending warnings.
- Current-code disposable-server smoke passed: `python scripts\load_smoke_50.py --base-url http://127.0.0.1:8012 --users 50 --concurrency 10 --username-prefix wsf24 --forwarded-for-prefix 10.254.52. --room-isolation --room-size 4 --db-path .codex-test-artifacts\smoke-50-20260524.sqlite` completed with `455` requests and `0` failures. It created `13` rooms for `50` users, kept all rooms within the 4-player cap, rejected full-room outsider join with `409`, and rejected cross-room room/member/session reads with `403`. Post-run `/ready` showed `locked_sessions=0` and no websocket connections.

## Browser Deep Test Script Outline

1. Start backend and frontend with a clean test database and usable model configuration.
2. Open host context and guest context.
3. Register/login both users.
4. Host creates a room; guest joins by room code.
5. Host and guest claim characters or create room-bound characters.
6. Host fills AI companions if needed and starts the room.
7. In Adventure, validate speaker bar and room state.
8. Current speaker submits a free action; guest observes speaker rotation after the DM response.
9. Non-speaker submits a group intent and marks readiness.
10. Start a rest vote and resolve it.
11. Start a creative action vote and resolve it.
12. Force or seed a combat state, then open Combat in both contexts.
13. Validate turn ownership, movement/attack updates, and WS refresh.
14. Let the player turns advance into an enemy AI turn and confirm the round returns to the first player.
15. Trigger supported host-owned and guest-owned reaction prompts, resolve Shield, and confirm the reaction broadcasts to combat state without leaking the prompt to the other client.
16. Close test browser contexts and confirm `/ready.ws.room_connections` returns to zero before the next scenario.
17. Refresh both tabs and confirm session/room state restores without extra room lookups in single-player routes.

## Known Runtime Boundary

The 50-user target means server-level online concurrency across independent sessions/rooms. A single multiplayer game remains a 4-player party/table unless the room configuration is intentionally changed. The current 50-user target assumes one backend worker, PostgreSQL in production, nginx WebSocket upgrade support, and no multi-instance deployment. Before multi-worker deployment, replace in-process WebSocket state and in-process session action locks with Redis pub/sub or another external coordination layer.
