# LucyWorks OS — Build + Debug Handover Pack

## Current status
This file is the current source-of-truth handover for LucyWorks OS after the backend stabilisation pass.

The project now uses a safer backend entrypoint:

```text
backend/app/main_fixed.py
```

The older `backend/app/main.py` still exists, but the smoke test and full run script now target `main_fixed.py`.

---

# 1. Product Definition

## Product name
LucyWorks OS

## Product type
Hospital operations engine for specialist veterinary hospitals.

## Core positioning
**Run the hospital. Not just the schedule.**

LucyWorks OS coordinates:
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

Core loop:

```text
Episode → Schedule → Rooms → Staff → Conflicts → Results → Messages → Work → Audit
```

---

# 2. Repository

GitHub repository:

```text
edgallagheris-lucyworksos/lucyworks-os
```

Expected structure:

```text
lucyworks-os/
  backend/
    app/
      main.py
      main_fixed.py
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
      staff/
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

Framework: FastAPI

ORM / DB: SQLModel with SQLite for development.

Default DB is defined in `backend/app/database.py`:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lucyworks.db")
```

## Current backend entrypoint
Use:

```text
backend/app/main_fixed.py
```

Run target:

```bash
uvicorn app.main_fixed:app --host 0.0.0.0 --port 8000
```

## Main backend files

### `backend/app/models.py`
Core entities:
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

Important current fix:

```python
ScheduleBlock.assigned_staff_member_id
```

This means schedule blocks can now store the actual assigned staff member, not just the role.

`ConflictAction` now also supports resolution state:

```python
status
resolved_at
resolution_note
```

---

# 4. Critical Backend Endpoints

## Health
```text
GET /api/health
```

## Users / staff / shifts
```text
GET /api/users
GET /api/staff
GET /api/shifts
GET /api/staff-load
```

## Patients / episodes
```text
GET /api/patients
GET /api/episodes
GET /api/episode-command/{episode_ref}
```

## Boards required by frontend
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

This now writes:

```text
assigned_staff_member_id
owner_role
```

## Conflicts
```text
GET  /api/conflicts
POST /api/conflicts/to-work
GET  /api/conflict-actions
POST /api/conflict-actions/{action_id}/resolve
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

# 5. Frontend Stack

Framework: Next.js 15 + React 19

## Product landing
`frontend/app/page.tsx`

Should position LucyWorks OS as:

```text
Hospital Operations Engine
Run the hospital. Not just the schedule.
```

## Shared shell
`frontend/components/hospital-shell.tsx`

Includes role navigation and now links to `/staff` for ops manager, clinician, and nurse roles.

## Episode command view
`frontend/app/episodes/[episodeRef]/page.tsx`

Uses:

```text
GET /api/episode-command/{episode_ref}
GET /api/staff-load
```

Current controls:
- shift schedule block by -15 / +15 minutes
- assign staff to a block
- convert conflict to work
- mark result reviewed
- show assigned staff name using `assigned_staff_member_id`
- show staff load cards

## Conflicts page
`frontend/app/conflicts/page.tsx`

Current controls:
- show detected conflicts
- convert detected conflict to work
- show conflict actions
- resolve conflict actions

## Staff page
`frontend/app/staff/page.tsx`

Shows:
- staff member
- role
- on shift / off shift
- active assigned blocks
- assigned block IDs
- skills

---

# 6. Run Scripts

## Backend smoke check
File:

```text
run-backend-check.sh
```

Command:

```bash
bash run-backend-check.sh
```

## Full development run
File:

```text
run-all.sh
```

Command:

```bash
bash run-all.sh
```

Important: this now runs:

```bash
uvicorn app.main_fixed:app --host 0.0.0.0 --port 8000
```

---

# 7. Smoke Test

File:

```text
backend/smoke_test.py
```

It imports:

```python
from app.main_fixed import app
```

It uses an isolated clean SQLite database every run.

It validates:
1. `/api/health`
2. seeded episodes
3. `EP-1042` episode command
4. director, consult, ward, and theatre boards
5. schedule generation
6. schedule block chain
7. schedule shifting
8. staff list
9. staff allocation
10. `/api/staff-load`
11. `/api/conflicts`
12. conflict-to-work
13. `/api/conflict-actions`
14. conflict resolution
15. episode command after actions

Expected pass output:

```text
--- ALL TESTS PASSED ---
```

---

# 8. Current Known Risks

## Risk 1 — frontend build still needs external verification
The backend has been hardened, but the frontend build has not been executed inside this assistant runtime.

Required check:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
```

## Risk 2 — no migration system
There is still no Alembic migration system. Development uses SQLite + SQLModel create_all.

Production requires migrations.

## Risk 3 — schedule duplication policy not resolved
`/api/schedule/generate` creates a new case procedure and new block chain every call.

Need a product decision:
- allow multiple procedures per episode, or
- replace/void prior planned blocks for same episode/procedure.

## Risk 4 — old `main.py` remains
The safer app is `main_fixed.py`. The older `main.py` is not the recommended run target.

Future cleanup should either:
- replace `main.py` with `main_fixed.py`, or
- keep `main_fixed.py` as stable entrypoint and document it clearly.

## Risk 5 — UI is functional but not polished
Current UI is operational and dark-command styled, but still needs:
- stronger logo component
- product/pitch page
- demo story
- screenshots
- pricing hypothesis
- technical architecture diagram

---

# 9. Branding / Marketing State

Name: LucyWorks OS

Category: Hospital Operations Engine

Tagline:

```text
Run the hospital. Not just the schedule.
```

Visual direction:
- dark operational UI
- clinical / command-centre feel
- teal accent `#14b8a6`
- near-black background `#020617`
- no cute vet branding
- no SaaS fluff

---

# 10. Next Build Order

Do not add new concepts until validation is done.

## Step 1 — backend verification
Run:

```bash
bash run-backend-check.sh
```

Fix any failure.

## Step 2 — frontend build verification
Run:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
```

Fix any build errors.

## Step 3 — product cleanup
- decide schedule duplication policy
- replace/retire old `main.py`
- add CI workflow manually if GitHub connector blocks it
- add product/pitch page
- add better logo/brand component

---

# 11. Prompt for another LLM

```text
You are debugging LucyWorks OS in repo edgallagheris-lucyworksos/lucyworks-os.
Use LUCYWORKS_BUILD_AND_DEBUG_HANDOVER.md as source of truth.
Use backend/app/main_fixed.py as the current stable backend entrypoint.
Do not guess from chat.
First make backend/smoke_test.py pass on a clean isolated DB.
Then make frontend npm build pass.
Do not add new concepts until validation passes.
Product direction: LucyWorks OS is a hospital operations engine, not a dashboard.
Core loop: Episode → Schedule → Rooms → Staff → Conflicts → Results → Messages → Work → Audit.
```
