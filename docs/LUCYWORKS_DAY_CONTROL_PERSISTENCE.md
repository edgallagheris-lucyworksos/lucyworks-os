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
GET   /api/day-control/audit
```

## Database tables

The SQLModel tables are defined in:

```text
apps/api/app/schedule_state_models.py
backend/app/schedule_state_models.py
```

Tables:

```text
ScheduleStateBlock
ScheduleStateEvent
```

## Route files

```text
apps/api/app/day_control_routes.py
backend/app/day_control_routes.py
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

## Required invariants

1. No page should create its own disconnected work model.
2. Every view must read from the generated schedule or persisted schedule state.
3. Every action must create an auditable state change.
4. Backend persistence must replace localStorage as the primary source.
5. localStorage remains only as offline fallback.

## Next persistence work

1. Link block actions to authenticated user identity.
2. Add case/episode references to ScheduleStateBlock.
3. Add resource and staff assignment records.
4. Add conflict detection that reads persisted blocks.
5. Add migration strategy for schema changes.
