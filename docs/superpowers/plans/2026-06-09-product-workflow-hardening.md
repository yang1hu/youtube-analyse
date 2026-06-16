# Product Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a practical task center, viral sample library, and configuration health checks so the creator agent feels reliable for daily use.

**Architecture:** Keep the existing WorkspaceStore snapshot pattern so JSON and MySQL backends continue to work. Add focused services for task status/Redis queue mirroring, sample-library mutations, and health checks, then expose them through FastAPI and React pages.

**Tech Stack:** FastAPI, SQLAlchemy/MySQL snapshot store, Redis ping/list mirroring, React/Vite TypeScript.

---

### Task 1: Backend Task Center

**Files:**
- Create: `backend/creator_agent/services/task_service.py`
- Modify: `backend/creator_agent/api/routes.py`
- Test: `backend/tests/test_product_workflow.py`

- [ ] Write failing API tests for `GET /api/tasks`, `POST /api/tasks/{task_id}/retry`, and Redis status fields.
- [ ] Implement a task service that lists jobs, normalizes step metadata, retries failed jobs by cloning payload, and pings Redis.
- [ ] Wire routes without breaking existing synchronous actions.
- [ ] Run `python -m pytest backend/tests/test_product_workflow.py -q`.

### Task 2: Viral Sample Library

**Files:**
- Create: `backend/creator_agent/services/sample_library_service.py`
- Modify: `backend/creator_agent/api/routes.py`
- Test: `backend/tests/test_product_workflow.py`

- [ ] Write failing tests for tagging/favoriting samples and merging multiple samples into a reusable style profile.
- [ ] Implement update and merge operations on top of `WorkspaceStore`.
- [ ] Keep existing `sample_analyses` compatible by storing extra fields in each raw sample dict.
- [ ] Run `python -m pytest backend/tests/test_product_workflow.py -q`.

### Task 3: Health Checks

**Files:**
- Create: `backend/creator_agent/services/health_check_service.py`
- Modify: `backend/creator_agent/api/routes.py`
- Test: `backend/tests/test_product_workflow.py`

- [ ] Write failing tests for a health endpoint that reports MySQL, Redis, yt-dlp, ffmpeg, LLM, browser/CDP, and cache paths.
- [ ] Implement bounded checks with short timeouts and human-readable remediation text.
- [ ] Avoid heavy YouTube/network activity in tests.
- [ ] Run `python -m pytest backend/tests/test_product_workflow.py -q`.

### Task 4: Frontend Surfaces

**Files:**
- Create: `frontend/src/components/TaskCenter.tsx`
- Create: `frontend/src/components/SampleLibrary.tsx`
- Modify: `frontend/src/components/Settings.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`

- [ ] Add bilingual nav entries for Task Center and Sample Library.
- [ ] Add polling/refresh and retry controls for tasks.
- [ ] Add sample tag/favorite controls and style merge controls.
- [ ] Add health-check panel inside Settings.
- [ ] Run `npm run build`.

### Task 5: Verification

**Files:**
- Existing backend and frontend test/build files.

- [ ] Run `python -m pytest -q` from `backend`.
- [ ] Run `npm run build` from `frontend`.
- [ ] Summarize Redis/MySQL status and remaining product gaps.
