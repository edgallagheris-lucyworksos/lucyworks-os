# LucyWorks Day-Control Persistence

This file documents the persisted operating spine for the LucyWorks day-control system.

## Purpose

The day-control model is the current source of truth for the live hospital board.

It stores and updates scheduled work blocks for:

```text
arrivals
reception
consults
insurance/admin
client/contact updates
clinical decisions
nursing/PCA work
rooms/procedures
imaging
care/recovery
supply
breaks/welfare
```

## API endpoints

```text
GET   /api/day-control/blocks
POST  /api/day-control/blocks
PUT   /api/day-control/blocks/bulk
PATCH /api/day-control/blocks/{block_id}
POST  /api/day-control/blocks/{block_id}/actions
GET   /api/day-control/conflicts
GET   /api/day-control/audit
GET   /api/day-control/staff-options
POST  /api/day-control/staff-options
PATCH /api/day-control/staff-options/{person_id}
GET   /api/day-control/resource-options
POST  /api/day-control/resource-options
PATCH /api/day-control/resource-options/{resource_id}
```

## Database tables

The SQLModel schedule tables are defined in:

```text
apps/api/app/schedule_state_models.py
backend/app/schedule_state_models.py
```

Schedule tables:

```text
ScheduleStateBlock
ScheduleStateEvent
```

`ScheduleStateBlock` includes assignment fields:

```text
episode_ref
assigned_role
assigned_staff_id
assigned_staff_name
resource_id
resource_name
```

The SQLModel assignment directory tables are defined in:

```text
apps/api/app/assignment_directory_models.py
backend/app/assignment_directory_models.py
```

Assignment directory tables:

```text
AssignmentPersonOption
AssignmentResourceOption
```

## Route files

```text
apps/api/app/day_control_routes.py
apps/api/app/day_control_conflict_routes.py
apps/api/app/day_control_options_routes.py
backend/app/day_control_routes.py
backend/app/day_control_options_routes.py
```

Both API trees must stay aligned until the repository is consolidated.

## Frontend client

The frontend store is:

```text
apps/web/lib/day-control-store.ts
```

The store is API-first:

```text
try API
seed API if empty
fallback to localStorage if backend is offline
poll API every 3 seconds
refresh API on browser focus
```

## Frontend assignment UI

Controlled assignment picker:

```text
apps/web/components/day-control-assignment-picker.tsx
```

Directory management page:

```text
apps/web/app/resource-directory/page.tsx
apps/web/components/assignment-directory-manager.tsx
```

Drawer host:

```text
apps/web/components/queue-detail-drawer.tsx
```

Assignment flow:

```text
select staff
select resource
PATCH /api/day-control/blocks/{block_id}
store refetches persisted blocks
warnings refresh from /api/day-control/conflicts
```

Directory flow:

```text
add staff option
add resource option
deactivate staff/resource option
assignment picker reads refreshed options from DB
```

## Conflict rules

Persisted conflicts are detected from saved DB state:

```text
resource_clash
staff_clash
unassigned_work
missing_resource
blocker
admin_blocker
contact_update_blocked
```

## Smoke test

Dedicated smoke test:

```text
apps/api/day_control_smoke_test.py
```

Run:

```bash
npm run backend:day-control-smoke
```

The smoke test covers:

```text
staff-options read/create/update
resource-options read/create/update
bulk seed
list persisted blocks
assignment patch
assignment clear
action update
audit output
conflict output
```

## Required invariants

1. No page should create its own disconnected work model.
2. Every view must read from the generated schedule or persisted schedule state.
3. Every action must create an auditable state change.
4. Backend persistence must replace localStorage as the primary source.
5. localStorage remains only as offline fallback.
6. Staff/resource assignments must use controlled IDs where possible.
7. Conflict detection must read persisted state, not static demo rows.
8. Assignment directory options must be DB-backed, not hardcoded.

## Next persistence work

1. Link block actions to authenticated user identity.
2. Add case/episode foreign keys rather than loose episode_ref strings.
3. Add schema migrations for ScheduleStateBlock, ScheduleStateEvent, AssignmentPersonOption and AssignmentResourceOption.
4. Add WebSocket/SSE push so polling can be removed later.
5. Merge or retire the duplicate legacy backend tree once deployment uses one API root.
