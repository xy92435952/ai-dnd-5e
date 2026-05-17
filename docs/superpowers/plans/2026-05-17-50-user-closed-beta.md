# 50 User Closed Beta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current monolith safe enough for a 50-user closed beta without changing the core FastAPI/React/LangGraph stack.

**Architecture:** Keep a single backend instance as the beta target, but add hard guardrails: per-user/IP rate limiting, production readiness checks, WebSocket occupancy reporting, and background module-parse concurrency/backlog limits. PostgreSQL remains the recommended production DB; Redis pub/sub is documented as the next step before multi-instance scaling.

**Tech Stack:** FastAPI middleware/dependencies, SQLAlchemy async, pytest/httpx, existing settings, existing WebSocket manager, existing BackgroundTasks.

---

### Task 1: Closed Beta Rate Limits

**Files:**
- Create: `backend/services/rate_limit_service.py`
- Modify: `backend/config.py`
- Modify: `backend/main.py`
- Test: `backend/tests/unit/test_rate_limit_service.py`
- Test: `backend/tests/integration/test_beta_guardrails.py`

- [x] Add settings for enabling rate limits and 50-user beta defaults.
- [x] Add a small in-memory token-window limiter keyed by user id or client IP.
- [x] Apply the limiter as middleware, with stricter policies for auth and AI/game-heavy endpoints.
- [x] Return `429` with a clear JSON error and `Retry-After`.

### Task 2: Production Readiness and WS Status

**Files:**
- Modify: `backend/services/ws_manager.py`
- Modify: `backend/main.py`
- Test: `backend/tests/unit/test_ws_manager.py`
- Test: `backend/tests/integration/test_beta_guardrails.py`

- [x] Expose `ws_manager.stats()` with rooms, connections, and per-room counts.
- [x] Add `/ready` that fails production if JWT secret is missing/weak, DB is still SQLite, or upload directory is unavailable.
- [x] Include WebSocket occupancy and configured beta limits in `/ready`.

### Task 3: Module Parse Backlog Guard

**Files:**
- Create: `backend/services/background_job_limits.py`
- Modify: `backend/config.py`
- Modify: `backend/api/modules.py`
- Test: `backend/tests/unit/test_background_job_limits.py`

- [x] Add parse concurrency and queue limits for closed beta.
- [x] Reserve a parse backlog token before accepting upload parse work.
- [x] Acquire a parse run slot before doing extraction / LLM parsing.
- [x] Release the token and run slot when background parse finishes, succeeds, or fails.
- [x] Return `429` when the parse backlog is full so beta users do not silently overload LLM/RAG.

### Task 4: Closed Beta Deployment Notes

**Files:**
- Modify: `doc/DEPLOY.md`
- Create: `doc/Closed_Beta_50_User_Runbook.md`

- [x] Document the single-instance 50-user target.
- [x] Document required env values and recommended beta limits.
- [x] Document when Redis/pubsub and worker queues become mandatory.

### Verification

- [ ] `backend/.venv-codex/bin/pytest backend/tests/unit/test_rate_limit_service.py backend/tests/unit/test_background_job_limits.py backend/tests/unit/test_ws_manager.py backend/tests/integration/test_beta_guardrails.py -q`
- [ ] `backend/.venv-codex/bin/pytest backend/tests/smoke/test_imports.py -q`
- [ ] `git diff --check`
