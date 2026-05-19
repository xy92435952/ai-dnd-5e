# Player Experience Structure Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the 50-player closed beta path by making campaign memory easier to inspect, failure states clearer, character creation state better bounded, and core player routes guarded by focused regression tests.

**Architecture:** Keep AI prompt and module context quality unchanged. Add small frontend-only presentation helpers around existing `campaign_state`, centralize Adventure and Combat retry/error rendering through existing feedback components, extract CharacterCreate async flow into a hook without changing API contracts, then extend smoke coverage around those boundaries.

**Tech Stack:** React 19, React Router 7, Vitest 4, Testing Library, FastAPI/Pytest existing gate.

---

### Task 1: Structured Journal Panel

**Files:**
- Modify: `frontend/src/components/adventure/JournalModal.jsx`
- Modify: `frontend/src/pages/Adventure.jsx`
- Test: `frontend/src/components/adventure/__tests__/JournalModal.test.jsx`

- [ ] **Step 1: Write failing JournalModal test**

Create `frontend/src/components/adventure/__tests__/JournalModal.test.jsx` with a test that renders `JournalModal` using `campaignState` containing active/completed quests, clues, NPC facts, and key decisions. Assert that section headings `任务`, `线索`, `人物`, and `关键决定` are visible, and that generated prose remains visible in the journal.

- [ ] **Step 2: Run JournalModal test to verify it fails**

Run: `cd frontend && npm test -- src/components/adventure/__tests__/JournalModal.test.jsx --runInBand`
Expected: FAIL because `JournalModal` does not accept or render `campaignState`.

- [ ] **Step 3: Implement structured sections**

Update `JournalModal` to accept `campaignState`, derive arrays from `quest_log`, `clues`, `npc_registry`, and `key_decisions`, and render compact sections above the generated prose. Preserve existing loading, generated text, regenerate, and close behavior.

- [ ] **Step 4: Pass campaign state from Adventure**

Update `Adventure.jsx` so the modal receives `campaignState={session?.campaign_state}`.

- [ ] **Step 5: Run JournalModal test to verify it passes**

Run: `cd frontend && npm test -- src/components/adventure/__tests__/JournalModal.test.jsx --runInBand`
Expected: PASS.

### Task 2: Adventure and Combat Failure State Polish

**Files:**
- Modify: `frontend/src/pages/Adventure.jsx`
- Modify: `frontend/src/pages/Combat.jsx`
- Test: `frontend/src/pages/__tests__/Adventure.smoke.test.jsx`
- Test: `frontend/src/pages/__tests__/Combat.smoke.test.jsx`

- [ ] **Step 1: Write failing Adventure retry test**

Extend Adventure smoke tests so a failed `gameApi.getSession` renders a full-screen error with retry action. Clicking retry must call `getSession` again and recover into the normal Adventure UI.

- [ ] **Step 2: Run Adventure smoke test to verify it fails**

Run: `cd frontend && npm test -- src/pages/__tests__/Adventure.smoke.test.jsx --runInBand`
Expected: FAIL because Adventure currently keeps showing loading while `session` is null even when `error` exists.

- [ ] **Step 3: Implement Adventure error state**

Update `Adventure.jsx` so the early `!session` branch renders `ErrorState` with `onRetry={loadSession}` when `error` is set. Keep existing toast-style errors after the session has loaded.

- [ ] **Step 4: Write failing Combat retry test**

Extend Combat smoke tests so a failed initial combat load renders a full-screen error with retry. Clicking retry must call `gameApi.getCombat` again.

- [ ] **Step 5: Run Combat smoke test to verify it fails**

Run: `cd frontend && npm test -- src/pages/__tests__/Combat.smoke.test.jsx --runInBand`
Expected: FAIL if retry is not wired to `loadCombat`.

- [ ] **Step 6: Implement Combat retry**

Update `Combat.jsx` to use `ErrorState error={error} onRetry={runtime.loadCombat} fullScreen` when no combat data exists.

- [ ] **Step 7: Run page smoke tests**

Run: `cd frontend && npm test -- src/pages/__tests__/Adventure.smoke.test.jsx src/pages/__tests__/Combat.smoke.test.jsx --runInBand`
Expected: PASS.

### Task 3: CharacterCreate Async Flow Hook

**Files:**
- Create: `frontend/src/hooks/useCharacterCreateFlow.js`
- Modify: `frontend/src/pages/CharacterCreate.jsx`
- Test: `frontend/src/hooks/__tests__/useCharacterCreateFlow.test.js`

- [ ] **Step 1: Write failing hook tests**

Create `useCharacterCreateFlow` tests covering: initial module/options load sets module/options/form level/party size; multiplayer save creates character, claims it, and navigates back to room; failed room claim reports an error and does not navigate.

- [ ] **Step 2: Run hook tests to verify they fail**

Run: `cd frontend && npm test -- src/hooks/__tests__/useCharacterCreateFlow.test.js --runInBand`
Expected: FAIL because `useCharacterCreateFlow` does not exist.

- [ ] **Step 3: Implement hook**

Create `useCharacterCreateFlow.js` with `useEffect` for module/options loading and exported handlers `handleSaveAndContinue`, `handleGenerateParty`, and `handleStartAdventure`. Inject APIs and navigation as dependencies for testing, defaulting to current `modulesApi`, `charactersApi`, `roomsApi`, and `gameApi`.

- [ ] **Step 4: Wire CharacterCreate to hook**

Remove async flow bodies from `CharacterCreate.jsx` and consume the new hook. Preserve all user-facing behavior and API payload shapes.

- [ ] **Step 5: Run hook and existing CharacterCreate state tests**

Run: `cd frontend && npm test -- src/hooks/__tests__/useCharacterCreateFlow.test.js src/hooks/__tests__/useCharacterCreateState.test.js --runInBand`
Expected: PASS.

### Task 4: Main Path Regression Gate

**Files:**
- Modify: `frontend/src/pages/__tests__/Adventure.smoke.test.jsx`
- Modify: `frontend/src/pages/__tests__/Combat.smoke.test.jsx`
- Modify: `frontend/src/components/adventure/__tests__/JournalModal.test.jsx`
- Verify: `scripts/check.sh`

- [ ] **Step 1: Add targeted assertions**

Ensure tests assert the structured Journal panel, Adventure retry recovery, Combat retry recovery, and CharacterCreate flow hook behavior. These guard the closed-beta main path without adding brittle full E2E automation.

- [ ] **Step 2: Run targeted frontend tests**

Run: `cd frontend && npm test -- src/components/adventure/__tests__/JournalModal.test.jsx src/pages/__tests__/Adventure.smoke.test.jsx src/pages/__tests__/Combat.smoke.test.jsx src/hooks/__tests__/useCharacterCreateFlow.test.js --runInBand`
Expected: PASS.

- [ ] **Step 3: Run full project gate**

Run: `./scripts/check.sh`
Expected: Backend pytest, frontend Vitest, and frontend build all pass.
