# Stage 7.5 Launch Experience QA

Stage 7.5 sits after the Stage 7 deployment evidence gate. Its purpose is to
prove that the public build is usable as a player-facing experience, not only
that CI and health checks are green.

## Current Scope

Stage 7.5 has two evidence layers:

- a read-only public UI smoke that verifies the deployed shell without mutating
  shared public data
- a resettable smoke seed that creates a disposable public session for the
  mutating exploration-to-combat path

The reusable read-only gate is:

```powershell
node scripts\stage7_5_launch_experience_smoke.mjs --frontend-origin https://www.ai5edm.top --username test --password <password> --exploration-session-id <non-combat-session-id> --combat-session-id <combat-active-session-id> --output artifacts\stage7_5-launch-experience-result-YYYYMMDD.json
```

Supported environment variables:

- `STAGE7_5_FRONTEND_ORIGIN`
- `STAGE7_5_USERNAME`
- `STAGE7_5_PASSWORD`
- `STAGE7_5_EXPLORATION_SESSION_ID`
- `STAGE7_5_COMBAT_SESSION_ID`
- `STAGE7_5_MUTATING`
- `STAGE7_5_COMBAT_CHOICE_TEXT`
- `STAGE7_5_CLAIM_LOOT_ID`
- `STAGE7_5_ARTIFACT_TAG`
- `STAGE7_5_OUTPUT`
- `STAGE7_5_TIMEOUT_MS`
- `STAGE7_5_BROWSER_PATH`

The smoke intentionally avoids story and combat mutations. It does not advance
the story, claim loot, attack, or end turns against public data. Opening Journal
may still trigger the app's normal journal-generation request when the session
has no generated journal text yet.

## Resettable Seed

After deploying a main build that includes the Stage 7.5 seed, reset the public
smoke account on the server with:

```bash
cd /opt/ai-trpg/app/backend
python seed_smoke_scenario.py --slug stage7_5_launch --variant stage7-5 --username test --password 123456
```

This attaches the deterministic Stage 7.5 smoke module, party, session, visible
loot, and password reset to the existing `test` user when it exists. The printed
JSON includes:

- `stage7_5.exploration_session_id`
- `stage7_5.combat_session_id`
- `stage7_5.combat_choice_text`
- `stage7_5.gold_loot_id`
- `stage7_5.gear_loot_id`

For the `stage7-5` variant, exploration and combat use the same session id. The
session starts with `combat_active=false`; clicking/submitting the fixed
`combat_choice_text` through `/game/action` starts a controlled combat handoff
without invoking the DM agent.

After reset, run the mutating smoke against that same session id:

```powershell
node scripts\stage7_5_launch_experience_smoke.mjs --mutating --frontend-origin https://www.ai5edm.top --username test --password 123456 --exploration-session-id <stage7_5-session-id> --output artifacts\stage7_5-mutating-result-YYYYMMDD.json
```

The mutating mode still logs in through the deployed frontend and opens
Adventure tools first. It then clicks the fixed exploration choice, waits for
the real combat route, uses the authenticated browser session to resolve one
deterministic attack-roll / damage-roll / end-turn sequence, claims the
`Gate Token` to the party stash, refreshes Combat, and records the before/after
HP, turn-token, loot, and log checks in the JSON artifact. The default
`claim_loot_id` is `loot_gear_gate_token_0`.

## Evidence Covered

The script verifies and captures screenshots for:

- public login through the real frontend
- a non-combat Adventure page
- Adventure dialogue shell and recovery/free-speak controls
- Journal modal
- Map modal
- Loot modal and loot API
- Adventure-to-Combat handoff for a combat-active session
- Combat page shell
- combat API
- combat skill-bar API and DOM skill bar
- battlefield units, end-turn control presence, and combat log presence
- browser runtime/console/network error events

The generated artifact uses:

```json
{
  "mode": "stage7.5-launch-experience-smoke",
  "ok": true
}
```

## Completion Rules

Stage 7.5 is not complete until the final summary has current evidence for:

- baseline public health and deployed HEAD
- latest GitHub Actions `backend`, `frontend`, and `frontend-prod-build`
- read-only launch-experience smoke
- mutating exploration progress or an explicitly documented substitute
- a full combat round on a resettable or disposable smoke session
- loot/journal follow-up after combat, or an explicitly documented blocker
- P0 = 0 and P1 = 0

The current read-only smoke is a prerequisite evidence slice, not the whole
Stage 7.5 completion claim.

## Mutating QA Requirement

Full combat-round QA should not run against a shared long-lived public save by
default. The preferred path is now the server-side `stage7-5` seed command above
rather than a public reset endpoint. Before marking Stage 7.5 complete, use that
seed or an equivalent disposable public session to capture current evidence for:

- real Adventure tool inspection on the seeded session
- real exploration choice submission that starts combat
- at least one complete combat round or an explicit blocker
- loot/journal follow-up after the combat path
- no P0/P1 issues left open

The `--mutating` smoke is the preferred evidence generator for those bullets.
Run it only after the public server has been updated and the seed command has
freshly reset the session.
