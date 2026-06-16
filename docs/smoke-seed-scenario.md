# Smoke Seed Scenario

Use this seed when you need a repeatable local game state without invoking the
module parser or a live LLM call.

## Command

```powershell
cd backend
python seed_smoke_scenario.py --slug codex_smoke
```

The script uses the current `DATABASE_URL`, creates tables if needed, and prints
JSON with:

- login username/password
- module id
- player character id
- companion id
- session id
- combat state id

The default login is:

```text
username: test_codex_smoke
password: smoke-password
```

Pass a different namespace if you want a separate stable scenario:

```powershell
python seed_smoke_scenario.py --slug qa_20260529 --password local-only-password
```

Use `--variant` for focused combat edge-case QA:

```powershell
python seed_smoke_scenario.py --slug qa_reaction --variant reaction
python seed_smoke_scenario.py --slug qa_death_save --variant death-save
python seed_smoke_scenario.py --slug qa_feather_fall --variant feather-fall
```

- `standard`: default playable exploration + active combat seed.
- `reaction`: starts after a construct hit has already landed, with a pending
  Shield reaction prompt, damaged player HP, and one 1st-level slot.
- `death-save`: starts on the player turn with the player at 0 HP and existing
  death-save marks.
- `feather-fall`: starts in exploration with a pending private Feather Fall
  prompt after a fixed 6-damage fall trap. The player remains unharmed until
  the prompt is accepted or declined through
  `/game/sessions/{session_id}/exploration-reaction`.

## What It Seeds

The scenario is `The Clockwork Crossing`, a compact level 2-3 adventure with:

- a parsed module whose `parse_status` is already `done`
- a real login user with a cleanup-safe `test_` username
- one player Fighter with equipped armor, shield, weapon, derived stats, and resources
- one AI Rogue companion with personality fields for companion reactions
- a single-player session with DM style, current scene, choices, trap state, campaign memory, and quest/clue data
- an active combat state with two enemies, initiative, grid positions, difficult terrain, and turn-state records
- two initial logs so session restore has narrative/system history

Focused variants may adjust that baseline. For example, `feather-fall` pauses
the seed in exploration instead of active combat and temporarily equips the AI
companion with Feather Fall so Adventure restore can show the non-combat
ReactionPrompt without invoking the LLM.

For a full local browser verification of the `feather-fall` Adventure prompt,
run from the repository root:

```powershell
node scripts\feather_fall_adventure_browser_smoke.mjs
```

That smoke uses a temporary SQLite database, starts backend/frontend processes
when needed, logs in as the seeded user, opens the Adventure session, accepts
the Feather Fall prompt, verifies HP/slot/pending state through HTTP refresh,
and writes prompt/resolved screenshots under `artifacts/`.

The same `--slug` is idempotent: rerunning it replaces the previous seeded rows
with the same deterministic ids instead of accumulating duplicate test data.

## Cleanup

The seed intentionally uses names recognized by `backend/cleanup_test_data.py`:

- users start with `test_`
- modules start with `__test_module`

To preview cleanup:

```powershell
cd backend
python cleanup_test_data.py --dry-run
```

To remove seeded test data:

```powershell
python cleanup_test_data.py --apply
```
