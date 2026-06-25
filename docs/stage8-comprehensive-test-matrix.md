# Stage 8 Comprehensive Test Matrix

Stage 8 turns the Stage 7.5 public launch smoke into a broader regression
system. The goal is to prove the current implemented product surface still
works across account setup, module/character setup, exploration, combat, loot,
multiplayer, and production parity.

## Completion Rule

Stage 8 is complete only when every required suite below has current evidence.
Fast unit/integration tests can satisfy local behavior. Browser, public, and
PostgreSQL-specific behavior needs explicit smoke artifacts or a documented
blocker.

The executable gate has two layers:

- local matrix integrity: required backend/frontend/script targets still exist
- suite evidence manifest: every public/manual/production-parity item below is
  marked `pass` with supporting details or `blocked` with a reason and
  `next_action`

Use `--allow-blockers` only for an audit handoff where the blocker is accepted
as known work. Do not use blocker mode to mark a launch promotion ready.

## Evidence Manifest

`scripts/stage8_comprehensive_gate.mjs --require-suite-evidence` reads a JSON
manifest through `--evidence-manifest <file>`. The manifest may store suites as
an object keyed by suite id or as an array of `{ "id": "<suite>" }` records.
Start from `docs/stage8-evidence-manifest-template.json` when preparing a
current release artifact.

Required evidence ids:

- `account-module-character`: `deployed-login`, `fresh-character-create`
- `adventure`: `exploration-tools`, `skill-check-path`
- `combat`: `stage7.5-mutating-smoke`, `combat-log-reload`
- `loot-economy`: `party-stash-claim`, `gold-or-shop-economy`
- `multiplayer`: `two-browser-room-join`, `speak-turn-handoff`,
  `combat-sync-or-blocker`
- `production-parity`: `github-actions-green`, `postdeploy-healthcheck`,
  `postgres-seed-reset`

Each `pass` evidence item must include supporting detail such as `notes`,
`command`, `url`, `checks`, or a JSON artifact `file`. The gate re-verifies
these artifact-backed items automatically:

- `combat.stage7.5-mutating-smoke` must pass
  `scripts/verify_stage7_evidence.mjs --type stage7.5-launch-smoke`
- `production-parity.postdeploy-healthcheck` must pass
  `scripts/verify_stage7_evidence.mjs --type postdeploy-healthcheck`
- `production-parity.github-actions-green` must include
  `checks.required_jobs_ok=true` or `checks.jobs` containing `backend`,
  `frontend`, and `frontend-prod-build`
- `production-parity.postgres-seed-reset` must include
  `checks.seed_reset_ok=true` or `checks.postgres_seed_reset_ok=true`

Minimal manifest shape:

```json
{
  "stage": "stage8",
  "generated_at": "2026-06-25T00:00:00.000Z",
  "release": {
    "branch": "main",
    "commit": "<commit>",
    "frontend_origin": "https://www.ai5edm.top",
    "health_url": "https://www.ai5edm.top/api/health"
  },
  "suites": {
    "combat": {
      "evidence": [
        {
          "id": "stage7.5-mutating-smoke",
          "result": "pass",
          "file": "artifacts/stage7_5-mutating-result-YYYYMMDD-COMMIT.json"
        }
      ]
    }
  }
}
```

Documented blocker shape:

```json
{
  "suites": {
    "multiplayer": {
      "blockers": [
        {
          "covers": ["combat-sync-or-blocker"],
          "reason": "Public two-browser combat sync needs a second disposable smoke account.",
          "next_action": "Create the account, rerun room join, then replace this blocker with pass evidence."
        }
      ]
    }
  }
}
```

## Suites

### account-module-character

Purpose: prove a player can enter the product and create playable state.

Required local targets:

- `backend/tests/integration/test_health_and_routes.py`
- `backend/tests/integration/test_inventory_endpoints.py`
- `backend/tests/integration/test_character_progression_endpoints.py`
- `backend/tests/integration/test_character_leveling_progression_endpoints.py`
- `backend/tests/unit/test_character_creation_service.py`
- `frontend/src/pages/__tests__/Home.responsive.test.jsx`
- `frontend/src/pages/__tests__/CharacterCreate.smoke.test.jsx`
- `frontend/src/pages/__tests__/CharacterSheet.inventory.test.jsx`

Manual/public evidence:

- login/register sanity on the deployed origin
- at least one fresh character-create path

### adventure

Purpose: prove exploration tools and state transitions work beyond one click.

Required local targets:

- `backend/tests/integration/test_game_flow.py`
- `backend/tests/integration/test_full_game_flow.py`
- `backend/tests/integration/test_state_restoration.py`
- `backend/tests/integration/test_smoke_seed_feather_fall.py`
- `frontend/src/pages/__tests__/Adventure.smoke.test.jsx`
- `frontend/src/components/adventure/__tests__/DialogueChoices.test.jsx`
- `frontend/src/components/adventure/__tests__/JournalModal.test.jsx`
- `frontend/src/components/adventure/__tests__/LocationMapModal.test.jsx`
- `frontend/src/components/adventure/__tests__/LootModal.test.jsx`

Manual/public evidence:

- public Adventure screenshot
- Journal, Map, Loot opened from the same session
- skill-check click path or a documented replacement

### combat

Purpose: prove the implemented rules engine, combat UI, and recovery flows are
alive together.

Required local targets:

- `backend/tests/integration/test_combat_endpoints.py`
- `backend/tests/integration/test_combat_rules_endpoints.py`
- `backend/tests/integration/test_stage7_5_smoke_seed.py`
- `backend/tests/unit/test_combat_attack_prepare_service.py`
- `backend/tests/unit/test_combat_spell_effects.py`
- `backend/tests/unit/test_combat_reaction_service.py`
- `backend/tests/unit/test_combat_condition_duration_service.py`
- `frontend/src/pages/__tests__/Combat.smoke.test.jsx`
- `frontend/src/components/combat/__tests__/CombatHudSkillBar.test.jsx`
- `frontend/src/components/combat/__tests__/CombatHudCombatLog.test.jsx`
- `frontend/src/components/combat/__tests__/SpellModal.test.jsx`
- `frontend/src/components/combat/__tests__/ReactionPrompt.test.jsx`

Manual/public evidence:

- Stage 7.5 mutating smoke artifact
- combat screenshot after a real action
- persisted combat log after reload

### loot-economy

Purpose: prove rewards, ownership, and economy-facing state persist correctly.

Required local targets:

- `backend/tests/integration/test_session_loot_endpoints.py`
- `backend/tests/integration/test_inventory_endpoints.py`
- `backend/tests/unit/test_context_builder_snapshots.py`
- `frontend/src/components/adventure/__tests__/LootModal.test.jsx`
- `frontend/src/pages/__tests__/CharacterSheet.inventory.test.jsx`

Manual/public evidence:

- party-stash claim
- gold split or documented substitute
- shop buy/sell smoke before promotion

### multiplayer

Purpose: prove room lifecycle, WebSocket sync, and reconnect-sensitive state do
not regress while single-player paths improve.

Required local targets:

- `backend/tests/integration/test_multiplayer_flow.py`
- `backend/tests/integration/test_multiplayer_happy_path.py`
- `backend/tests/integration/test_multiplayer_ws_realtime.py`
- `backend/tests/unit/test_room_multiplayer_state.py`
- `backend/tests/unit/test_ws_cleanup_service.py`
- `frontend/src/pages/__tests__/RoomLobby.smoke.test.jsx`
- `frontend/src/components/room/__tests__/RoomMultiplayerStatusPanel.test.jsx`
- `frontend/src/components/adventure/__tests__/MultiplayerSpeakBar.test.jsx`
- `frontend/src/components/combat/__tests__/MultiplayerTurnBar.test.jsx`

Manual/public evidence:

- two-browser room join
- speak-turn handoff
- combat refresh/sync or a documented blocker

### production-parity

Purpose: catch environment differences that unit tests miss.

Required local targets:

- `scripts/check.sh`
- `scripts/stage7_reaction_backend_gate.sh`
- `scripts/verify_stage7_evidence.mjs`
- `scripts/stage7_5_launch_experience_smoke.mjs`
- `scripts/stage8_comprehensive_gate.mjs`
- `backend/tests/unit/test_smoke_scenario_seed.py`
- `frontend/src/__tests__/stage7EvidenceVerifier.test.js`
- `frontend/src/__tests__/stage7_5LaunchExperienceSmoke.test.js`
- `frontend/src/__tests__/stage8ComprehensiveGate.test.js`

Manual/public evidence:

- latest GitHub Actions `backend`, `frontend`, and `frontend-prod-build`
- public `/api/health`
- Stage 7.5 read-only or mutating artifact verified by
  `scripts/verify_stage7_evidence.mjs --type stage7.5-launch-smoke`
- PostgreSQL seed/reset result or a current blocker note

## Recommended Commands

Fast matrix integrity check:

```powershell
node scripts\stage8_comprehensive_gate.mjs --json
npm --prefix frontend run test:stage8:gate
```

Verify current Stage 7.5 public mutating artifact:

```powershell
node scripts\stage8_comprehensive_gate.mjs --require-stage7-5-evidence --stage7-5-evidence artifacts\stage7_5-mutating-result-YYYYMMDD.json
```

Run the same Stage 8 matrix gate from the standard check script:

```powershell
$env:RUN_STAGE8_COMPREHENSIVE_GATE='1'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

Require a current Stage 7.5 launch artifact during that check:

```powershell
$env:RUN_STAGE8_COMPREHENSIVE_GATE='1'
$env:STAGE8_REQUIRE_STAGE7_5_EVIDENCE='1'
$env:STAGE8_STAGE7_5_EVIDENCE_FILES='artifacts/stage7_5-mutating-result-YYYYMMDD.json'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

Require the full Stage 8 suite evidence manifest:

```powershell
node scripts\stage8_comprehensive_gate.mjs --json --require-suite-evidence --evidence-manifest artifacts\stage8-evidence-YYYYMMDD-COMMIT.json
```

Run the same full manifest gate from the standard check script:

```powershell
$env:RUN_STAGE8_COMPREHENSIVE_GATE='1'
$env:STAGE8_REQUIRE_SUITE_EVIDENCE='1'
$env:STAGE8_EVIDENCE_MANIFEST='artifacts/stage8-evidence-YYYYMMDD-COMMIT.json'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
```

Audit with documented blockers, without treating the release as launch-ready:

```powershell
node scripts\stage8_comprehensive_gate.mjs --json --require-suite-evidence --evidence-manifest artifacts\stage8-evidence-YYYYMMDD-COMMIT.json --allow-blockers
```

Full local release gate:

```powershell
npm --prefix frontend run test:stage8:gate
npm --prefix frontend run test:stage7:reaction
& 'C:\Program Files\Git\bin\bash.exe' scripts/check.sh
& 'C:\Program Files\Git\bin\bash.exe' scripts/stage7_reaction_backend_gate.sh
git diff --check
```

Public launch-experience gate after server reset:

```powershell
node scripts\stage7_5_launch_experience_smoke.mjs --mutating --frontend-origin https://www.ai5edm.top --username test --password 123456 --exploration-session-id <stage7_5-session-id> --output artifacts\stage7_5-mutating-result-YYYYMMDD.json
node scripts\verify_stage7_evidence.mjs --type stage7.5-launch-smoke artifacts\stage7_5-mutating-result-YYYYMMDD.json
```
