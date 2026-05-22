# Multiplayer Deep Test Report

> Last verified: 2026-05-22
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

## Regression Coverage

- Backend rest vote integration covers direct multiplayer rest rejection plus majority-approved rest application.
- Frontend `RestModal` tests cover single-player direct rest and multiplayer voting states.
- WebSocket realtime integration now verifies both the `dm_speak_turn` event and the persisted room `current_speaker_user_id`.
- Browser deep smoke now verifies room start, Adventure navigation, two websocket connections, speaker rotation, group intent readiness, and rest vote resolution.
- Backend Combat/multiplayer regression: `80 passed in 28.07s` for `test_combat_endpoints.py`, `test_combat_rules_endpoints.py`, `test_multiplayer_flow.py`, `test_multiplayer_ws_realtime.py`, and `test_imports.py`.
- Frontend Combat regression: `10 passed` test files and `43 passed` tests across Combat HUD, battlefield, derived state, turn controls, player actions, spell flow, special actions, quick inventory, and multiplayer turn bar tests.
- `python -m py_compile` passed for touched backend Combat/auth files and the Combat browser smoke script.
- `npm run build` passed.
- `git diff --check` passed with Windows line-ending warnings only.

## 50-User Smoke

The 50-user HTTP smoke passed in the earlier 2026-05-22 run after fixing local proxy handling in the smoke script and bearer-token rate-limit identity in the backend.

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

## Notes

The browser run captured transient websocket warnings during route transition and context cleanup. The final readiness state still confirmed two active websocket connections during Adventure, and the scripted gameplay assertions passed. A future stricter browser gate can filter route-cleanup warnings separately from runtime errors while pages remain open.

The Combat browser smoke closes the two CDP contexts on success. Before the successful Combat run, `/ready` still showed older websocket connections left by previous failed browser attempts, but this run's own `session_id` was released after completion and no browser runtime events were captured.
