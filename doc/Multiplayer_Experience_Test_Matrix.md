# Multiplayer Experience Test Matrix

> Status: active QA baseline for the AI DnD platform.
> Scope: single-player and multiplayer sessions on the current single-worker closed-beta runtime.

This matrix is the project baseline for making multiplayer feel playable while keeping single-player stable. It should be updated whenever room flow, WebSocket events, Adventure, Combat, voting, or turn ownership changes.

## Quality Gates

| Gate | Command or procedure | Pass condition |
| --- | --- | --- |
| Frontend focused regression | `cd frontend && npm test -- --run src/hooks/__tests__/useAdventureRoom.test.js src/pages/__tests__/Adventure.smoke.test.jsx` | No single-player Adventure page calls multiplayer room lookup; Adventure mounts without hook/TDZ errors. |
| Backend room/session regression | `python -m pytest backend/tests/integration/test_game_flow.py::test_get_session_shape backend/tests/integration/test_multiplayer_flow.py::test_get_room_returns_full_info` | `/game/sessions/{id}` returns correct `is_multiplayer` and `room_code` for single-player and room sessions. |
| Backend action entry regression | `python -m pytest backend/tests/integration/test_game_flow.py::test_player_action_succeeds backend/tests/integration/test_game_flow.py::test_player_action_stream_sends_narrative_delta_before_final` | Normal and streaming action entrypoints still work with session action locking. |
| Smoke import/route check | `python -m pytest backend/tests/smoke/test_imports.py` | Route surface is still registered. |
| Browser deep test | `python scripts\multiplayer_deep_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --cdp http://127.0.0.1:9222` | Room start, Adventure navigation, host free action, speaker rotation, group intent readiness, and rest vote resolution all pass. |
| Combat browser deep test | `python scripts\multiplayer_combat_browser_smoke.py --base-api http://127.0.0.1:8002 --base-web http://127.0.0.1:3000 --cdp http://127.0.0.1:9222` | Host turn controls are enabled only for host, guest is blocked from host actions, host UI end-turn hands off through WS, and guest can move their own character. |
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
| MP-08 | Multiplayer Combat turn ownership | Multiplayer session in combat. | Host and guest try actions during each other's turns. | Only current actor can mutate combat; all clients refresh on combat updates. | Combat permission tests plus `multiplayer_combat_browser_smoke.py`. |
| MP-09 | Group/focus table flow | Multiplayer Adventure with split groups. | Submit pending actions in two groups; set readiness; trigger action. | Table decision processes/switches focus without leaking private group text. | `test_multiplayer_dm_agent.py`, room state tests. |
| OPS-01 | 50-user closed-beta smoke | Running backend and frontend against test DB. | Run `python scripts/load_smoke_50.py --base-url http://127.0.0.1:8002 --users 50 --concurrency 10 --forwarded-for-prefix 10.252.0.`. | Auth/session/ready endpoints complete within thresholds; errors are reported as nonzero exit. | Load smoke script. |

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
14. Refresh both tabs and confirm session/room state restores without extra room lookups in single-player routes.

## Known Runtime Boundary

The 50-user target assumes one backend worker, PostgreSQL in production, nginx WebSocket upgrade support, and no multi-instance deployment. Before multi-worker deployment, replace in-process WebSocket state and in-process session action locks with Redis pub/sub or another external coordination layer.
