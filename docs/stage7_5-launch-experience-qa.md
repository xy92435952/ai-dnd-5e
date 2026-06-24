# Stage 7.5 Launch Experience QA

Stage 7.5 sits after the Stage 7 deployment evidence gate. Its purpose is to
prove that the public build is usable as a player-facing experience, not only
that CI and health checks are green.

## Current Scope

The first reusable Stage 7.5 gate is:

```powershell
node scripts\stage7_5_launch_experience_smoke.mjs --frontend-origin https://www.ai5edm.top --username test --password <password> --exploration-session-id <non-combat-session-id> --combat-session-id <combat-active-session-id> --output artifacts\stage7_5-launch-experience-result-YYYYMMDD.json
```

Supported environment variables:

- `STAGE7_5_FRONTEND_ORIGIN`
- `STAGE7_5_USERNAME`
- `STAGE7_5_PASSWORD`
- `STAGE7_5_EXPLORATION_SESSION_ID`
- `STAGE7_5_COMBAT_SESSION_ID`
- `STAGE7_5_ARTIFACT_TAG`
- `STAGE7_5_OUTPUT`
- `STAGE7_5_TIMEOUT_MS`
- `STAGE7_5_BROWSER_PATH`

The smoke intentionally avoids story and combat mutations. It does not advance
the story, claim loot, attack, or end turns against public data. Opening Journal
may still trigger the app's normal journal-generation request when the session
has no generated journal text yet.

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
default. Use one of these approaches before marking Stage 7.5 complete:

- create a disposable public smoke account/session that can be reset after each
  run
- add a server-side public smoke seed endpoint guarded for deployment QA
- run the local deterministic smoke seed and record that public mutating QA is
  deferred with a clear release-risk decision

The preferred production-like path is a disposable public smoke session.
