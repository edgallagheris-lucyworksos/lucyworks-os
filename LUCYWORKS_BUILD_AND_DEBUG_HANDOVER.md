# LucyWorks OS — Full Build + Debug Handover Pack

## Purpose of this file
This document is the clean handover pack for debugging and continuing LucyWorks OS with another LLM, developer, or automation agent.

It exists because the build history became messy. Use this file as the stable source of truth instead of trying to reconstruct decisions from chat.

---

# 1. Product Definition

## Product name
LucyWorks OS

## Product type
Hospital operations engine for specialist veterinary hospitals.

## Core positioning
**Run the hospital. Not just the schedule.**

LucyWorks OS is not a generic dashboard, task board, CRM, reception tool, or SaaS toy. It is intended to be an operational control system for high-throughput specialist veterinary environments.

## What it should coordinate
- Episodes / cases
- Patients and owners
- Rooms
- Procedure scheduling
- Prep / anaesthesia / procedure / recovery / cleaning blocks
- Staff and shifts
- Work ownership
- Conflicts
- Results review
- Mail Ops / communications
- Handover
- Audit trail

---

# 2. Repository

## GitHub repository
`edgallagheris-lucyworksos/lucyworks-os`

## Current expected structure

```text
lucyworks-os/
  backend/
    app/
      main.py
      models.py
      schemas.py
      database.py
      seed.py
    requirements.txt
    smoke_test.py
  frontend/
    app/
      page.tsx
      login/
      command/
      episodes/
      schedule/
      conflicts/
      rooms/
      results/
      mail/
      consult/
      ward/
      theatre/
      queues/
      audit/
      input/
    components/
      hospital-shell.tsx
    lib/
      session.ts
    package.json
    tsconfig.json
  run-backend-check.sh
  run-all.sh
  SYSTEM_AUDIT.md
  LUCYWORKS_BUILD_AND_DEBUG_HANDOVER.md
```

---

# 3. Backend Stack

## Framework
FastAPI

## ORM / DB
SQLModel with SQLite for development.

## Backend default DB
Defined in `backend/app/database.py`:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lucyworks.db")
```

## Main backend files

### `backend/app/models.py`
Defines the core database entities:
- `User`
- `HospitalSection`
- `Room`
- `Patient`
- `Episode`
- `Admission`
- `Handover`
- `ResultReview`
- `MessageThread`
- `MessageEntry`
- `StaffMember`
- `Shift`
- `ProcedureType`
- `CaseProcedure`
- `ScheduleBlock`
- `RoomState`
- `ConflictAction`
- `WorkItem`
- `AuditEvent`

### `backend/app/schemas.py`
Defines request payloads:
- `LoginDemoRequest`
- `WorkItemCreate`
- `WorkItemAssign`
- `WorkItemStatusUpdate`
- `ScheduleGenerateRequest`
- `ScheduleShiftRequest`
- `ResultActionRequest`
- `MessageThreadCreate`
- `MessageEntryCreate`
- `StaffAllocateRequest`

### `backend/app/seed.py`
Seeds demo data:
- users
- hospital sections
- rooms
- staff
- shifts
- patients
- episodes
- admissions
- handovers
- results
- procedure types
- room states
- work items
- message threads
- message entries
- audit events

### `backend/app/main.py`
Main API router and system logic.

---

# 4. Frontend Stack

## Framework
Next.js 15 + React 19

## Main frontend surfaces

### Product landing
`frontend/app/page.tsx`

Should present LucyWorks OS as:
- Hospital Operations Engine
- “Run the hospital. Not just the schedule.”

Should link to:
- `/login`
- `/command`
- `/episodes`
- `/episodes/EP-1042`
- `/schedule`
- `/conflicts`
- `/rooms`
- `/results`
- `/mail`
- `/consult`
- `/ward`
- `/theatre`
- `/queues`
- `/audit`

### Shared shell
`frontend/components/hospital-shell.tsx`

Purpose:
- shared navigation
- alert summary
- role-based links
- consistent product frame

### Episode command view
`frontend/app/episodes/[episodeRef]/page.tsx`

This should use:

```text
GET /api/episode-command/{episode_ref}
```

Not multiple scattered endpoint calls.

It should show:
- case / patient / owner
- current phase
- room state
- schedule blocks
- conflicts
- results
- message threads
- work items
- controls for shifting schedule blocks
- controls for staff allocation
- controls for converting conflict to work
- controls for marking results reviewed

---

# 5. Critical Backend Endpoints

## Health
```text
GET /api/health
```

## Users / staff / shifts
```text
GET /api/users
GET /api/staff
GET /api/shifts
```

## Patients / episodes
```text
GET /api/patients
GET /api/episodes
GET /api/episode-command/{episode_ref}
```

## Boards required by frontend
These must exist or frontend pages will break:

```text
GET /api/director-board
GET /api/consult-board
GET /api/ward-board
GET /api/theatre-board
```

## Schedule
```text
GET  /api/procedure-types
GET  /api/case-procedures
GET  /api/schedule-blocks
POST /api/schedule/generate
POST /api/schedule/block/{block_id}/shift
```

## Staff allocation
```text
POST /api/staff/allocate
```

## Conflicts
```text
GET  /api/conflicts
POST /api/conflicts/to-work
```

## Results
```text
GET  /api/results
POST /api/results/{result_id}/action
```

## Messaging / Mail Ops
```text
GET  /api/message-threads
GET  /api/message-threads/{thread_id}/entries
POST /api/messages/thread
POST /api/messages/{thread_id}
```

## Rooms
```text
GET  /api/rooms
GET  /api/room-states
POST /api/room-states/{room_state_id}/set
```

## Audit
```text
GET /api/audit
```

---

# 6. Current Run Scripts

## Backend smoke check
File:

```text
run-backend-check.sh
```

Expected command:

```bash
bash run-backend-check.sh
```

Current content should:
- enter backend
- install requirements
- run smoke test

## Full development run
File:

```text
run-all.sh
```

Expected command:

```bash
bash run-all.sh
```

Current content should:
- install backend requirements
- start backend on port 8000
- install frontend packages
- start frontend on port 3000

---

# 7. Smoke Test

## File
`backend/smoke_test.py`

## Current intended behaviour
The smoke test should:
1. Use an isolated clean SQLite database every run.
2. Import the FastAPI app after setting `DATABASE_URL`.
3. Trigger app startup through `TestClient`.
4. Check `/api/health`.
5. Check seeded episodes exist.
6. Check `EP-1042` episode command endpoint.
7. Check director, consult, ward, and theatre board endpoints.
8. Generate a schedule.
9. Confirm schedule blocks exist.
10. Shift a schedule block.
11. Confirm staff exists.
12. Test staff allocation endpoint.
13. Test conflicts endpoint.
14. Test conflict-to-work endpoint.
15. Recheck episode command after actions.

## Expected pass output

```text
--- ALL TESTS PASSED ---
```

## Important note
If this test fails, fix the backend before touching the frontend.

---

# 8. Known Current Risks / Weak Points

## Risk 1 — No migrations
There is no Alembic migration system yet. SQLite tables are created with SQLModel metadata.

For development, isolated DB testing is okay. For production, migrations are required.

## Risk 2 — Staff allocation is not properly stored
Current `ScheduleBlock` has:

```python
owner_role: Optional[str]
```

But it does **not** currently have:

```python
assigned_staff_member_id: Optional[int]
```

This means staff allocation is not fully traceable yet.

### Required fix
Add to `ScheduleBlock`:

```python
assigned_staff_member_id: Optional[int] = Field(default=None, foreign_key="staffmember.id")
```

Then update `/api/staff/allocate` to store that field.

## Risk 3 — Conflict lifecycle incomplete
Current system can:
- detect conflict
- convert conflict to work item

But does not fully:
- persist every detected conflict
- mark source conflict resolved
- link resolution state back into schedule

### Required fix
Improve `ConflictAction` lifecycle:
- `open`
- `assigned`
- `resolved`
- `ignored`

## Risk 4 — Schedule generation can duplicate schedules
Current `/api/schedule/generate` creates a new `CaseProcedure` and block chain every time.

### Required fix options
Option A: allow multiple procedures per episode intentionally.
Option B: delete/void prior planned procedure blocks for same episode/procedure before new schedule.

Need explicit decision.

## Risk 5 — Frontend build not externally verified here
The repo has Next.js and TypeScript, but the assistant has not executed a real `npm run build` in the Codespaces environment.

Potential risks:
- route typing issues
- strict TS edge cases
- CSS/layout roughness
- missing pages referenced in navigation

## Risk 6 — GitHub Actions workflow missing
An attempt to create `.github/workflows/smoke.yml` was blocked by the connector. CI is not currently committed.

### Required fix
Manually create GitHub Actions workflow or retry through direct repo editing.

---

# 9. Branding / Marketing State

## Current brand direction

### Name
LucyWorks OS

### Tagline
Run the hospital. Not just the schedule.

### Category
Hospital Operations Engine

### Product description
Case-driven operational control for specialist veterinary hospitals: episodes, rooms, schedule blocks, conflicts, results, comms, work ownership, staff availability, and audit trail.

## Visual direction
- dark operational UI
- clinical / command-centre feel
- accent colour: teal `#14b8a6`
- background: dark slate / near black
- avoid soft “cute vet app” design
- should feel like control infrastructure

## Current marketing surface
`frontend/app/page.tsx` has been reworked into a product landing/front-door.

## Missing marketing assets
- proper logo component
- pitch page
- investor/demo explanation
- screenshots / demo story
- one-page product PDF
- feature matrix
- pricing hypothesis
- technical architecture diagram

---

# 10. Recommended Next Build Order

## Step 1 — Make backend test pass reliably
Run or simulate `backend/smoke_test.py`. Fix any backend failure first.

## Step 2 — Add proper staff assignment field
Add `assigned_staff_member_id` to `ScheduleBlock` and update API + UI.

## Step 3 — Add staff load endpoint
Suggested endpoint:

```text
GET /api/staff-load
```

Should return:

```json
[
  {
    "staff_member_id": 1,
    "name": "Nina Nurse",
    "role": "nurse",
    "active_blocks": 3,
    "on_shift": true,
    "conflicts": []
  }
]
```

## Step 4 — Improve conflict lifecycle
Add:

```text
GET  /api/conflict-actions
POST /api/conflict-actions/{id}/resolve
```

## Step 5 — Frontend build verification
Run:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
```

Fix all build errors.

## Step 6 — Add CI
Add `.github/workflows/smoke.yml` manually if needed.

## Step 7 — Add pitch / brand page
Suggested route:

```text
/frontend/app/product/page.tsx
```

Should explain:
- problem
- solution
- operational loop
- feature map
- demo flow
- why it matters

---

# 11. Debug Instructions for Another LLM

If another LLM receives this file, it should:

1. Open `backend/app/main.py`, `models.py`, `schemas.py`, `seed.py`, and `smoke_test.py`.
2. Check imports and model/schema compatibility.
3. Confirm all endpoints listed above exist.
4. Confirm frontend pages call only existing endpoints.
5. Prioritise backend smoke test before UI changes.
6. Do not add new features until the smoke test and frontend build pass.
7. Keep changes small and verifiable.
8. Avoid overwriting full files unless absolutely necessary.
9. If overwriting, preserve all endpoint coverage.
10. Update this file after major changes.

---

# 12. Short Prompt To Give Another LLM

Copy this prompt:

```text
You are debugging and continuing LucyWorks OS in the GitHub repo edgallagheris-lucyworksos/lucyworks-os. Read LUCYWORKS_BUILD_AND_DEBUG_HANDOVER.md first. Do not guess from chat history. First verify backend/app/models.py, schemas.py, seed.py, main.py, and backend/smoke_test.py are compatible. Make the backend smoke test pass using a clean isolated database. Then verify frontend endpoint usage matches backend endpoints. Do not add new features until backend smoke and frontend build pass. Preserve the product direction: LucyWorks OS is a hospital operations engine, not a generic dashboard. Core concept: Episode → Schedule → Rooms → Staff → Conflicts → Results → Messages → Work → Audit. Fix staff assignment properly by adding assigned_staff_member_id to ScheduleBlock, improve conflict lifecycle, then add staff load and product branding page.
```

---

# 13. Current Human Next Step

The next useful step is not more feature building. It is:

1. Run or simulate `bash run-backend-check.sh`.
2. Fix any failure.
3. Run frontend build.
4. Fix build errors.
5. Then continue with staff assignment and conflict lifecycle.

This file should be treated as the handover baseline.
