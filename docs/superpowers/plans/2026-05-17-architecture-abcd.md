# Architecture ABCD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue the current architecture optimization in A, B, C, D order: backend split quality, CharacterCreate frontend structure, release stability, and multiplayer table-decision boundaries.

**Architecture:** Keep existing behavior and public routes stable. Prefer focused helpers, compatibility facades, and contract tests over broad rewrites. Multiplayer host behavior must remain player-only, not DM/observer authority.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest, React 19, Vite, Vitest, Testing Library, ESLint.

**Status Sync 2026-05-21:** The codebase now contains the facade smoke coverage, `useCharacterCreateState`, lint noise exclusion/release gate work, and multiplayer table visibility boundary tests. Full final verification remains a release-time action unless the exact commands are rerun.

---

### Task A: Backend Split Contract Guards

**Files:**
- Modify: `backend/tests/smoke/test_imports.py`
- Optional modify only if tests expose drift: route facade modules under `backend/api/` and service facades under `backend/services/`

- [x] Add smoke coverage for all facade helpers created by recent route/service splits.
- [x] Run the targeted smoke test and confirm the new assertions catch missing exports when they are absent.
- [x] Restore/adjust facade exports only where the new contract tests expose a real split-boundary gap.

### Task B: CharacterCreate Hook Extraction

**Files:**
- Create: `frontend/src/hooks/useCharacterCreateState.js`
- Create: `frontend/src/hooks/__tests__/useCharacterCreateState.test.js`
- Modify: `frontend/src/pages/CharacterCreate.jsx`

- [x] Write a hook test for default state, modal controls, toggles, score adjustment, and standard-array assignment.
- [x] Run the hook test and confirm it fails before the hook exists.
- [x] Extract stateful creation helpers from `CharacterCreate.jsx` into `useCharacterCreateState`.
- [x] Update `CharacterCreate.jsx` to consume the hook without changing UI or API behavior.
- [x] Run the targeted hook test and existing character-create utility test.

### Task C: Release Stability

**Files:**
- Modify only if needed: `frontend/eslint.config.js`, `scripts/check.sh`, deployment scripts/docs

- [x] Run targeted backend smoke tests and frontend hook tests after A/B.
- [x] Run `npm run lint` and inspect current failure class.
- [x] If lint noise is from generated or design-preview artifacts, exclude those paths in ESLint config.
- [x] Run the repo check script or the closest practical subset.

### Task D: Multiplayer Table Boundary

**Files:**
- Modify: `backend/tests/unit/test_multiplayer_dm_agent.py`
- Optional modify only if test exposes drift: `backend/services/graphs/multiplayer_dm_agent.py` or `backend/services/graphs/multiplayer_dm_agent_formatters.py`

- [x] Add a test that a host outside the focus group does not gain group visibility from a table decision fallback.
- [x] Add a test that party-scope table notices keep `visible_to_user_ids` empty instead of enumerating room members.
- [x] Run the multiplayer DM unit tests.

### Final Verification

- [ ] Run backend smoke/import and multiplayer DM tests.
- [ ] Run frontend CharacterCreate hook test.
- [ ] Run `npm run lint` after any lint config adjustment.
- [ ] Run `git diff --check`.
