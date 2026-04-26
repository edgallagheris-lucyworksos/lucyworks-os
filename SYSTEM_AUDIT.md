# LucyWorks OS — Current System Audit

## Purpose
LucyWorks OS is a hospital operations engine, not a generic dashboard. The current repo is structured as:

- `backend/` — FastAPI + SQLModel API
- `frontend/` — Next.js UI
- `run-backend-check.sh` — backend smoke verification
- `run-all.sh` — development runner

## Current Backend Coverage
The backend currently exposes the core runtime surfaces required by the frontend:

- Health: `/api/health`
- Auth demo: `/api/auth/login-demo`
- Users/staff/shifts: `/api/users`, `/api/staff`, `/api/shifts`
- Patients/episodes: `/api/patients`, `/api/episodes`, `/api/episode-command/{episode_ref}`
- Core boards: `/api/director-board`, `/api/consult-board`, `/api/ward-board`, `/api/theatre-board`
- Schedule: `/api/procedure-types`, `/api/case-procedures`, `/api/schedule-blocks`, `/api/schedule/generate`, `/api/schedule/block/{block_id}/shift`
- Work: `/api/work-items`, assignment, status updates
- Conflicts: `/api/conflicts`, `/api/conflicts/to-work`
- Results: `/api/results`, `/api/results/{result_id}/action`
- Messaging: `/api/message-threads`, `/api/message-threads/{thread_id}/entries`, `/api/messages/thread`, `/api/messages/{thread_id}`
- Rooms: `/api/rooms`, `/api/room-states`, `/api/room-states/{room_state_id}/set`
- Audit: `/api/audit`

## Current Frontend Coverage
The frontend currently includes:

- Product landing page
- Login / access flow
- Command board
- Episode list
- Episode command view
- Schedule view
- Conflicts view
- Rooms control
- Results review
- Mail Ops
- Consult / Ward / Theatre boards
- Queues / Audit / Input pages

## Known Strengths
- The app now has a single episode command endpoint.
- Board endpoints have been restored to match current frontend pages.
- Backend smoke test uses an isolated test database to avoid old schema poison.
- The landing page now presents the product as a hospital operations engine.

## Known Risks Still To Fix
1. No GitHub Actions workflow is currently committed because the connector blocked `.github/workflows` creation.
2. Frontend build has not been independently executed inside this assistant environment.
3. There is no database migration system yet; current approach is rebuild/reset for development.
4. Staff allocation only stores role on schedule blocks, not a real `staff_member_id` assignment.
5. Conflict resolution creates work but does not yet mark the source conflict as resolved.
6. Marketing is present on the landing page, but there is no full pitch page/deck yet.

## Immediate Next Engineering Steps
1. Add a dedicated `assigned_staff_member_id` field to `ScheduleBlock`.
2. Add a staff load endpoint for frontend visibility.
3. Add a conflict action list/resolution endpoint.
4. Add frontend staff page.
5. Add a frontend smoke script or Playwright check.
6. Add CI manually in GitHub if the connector continues blocking workflow file creation.

## Current Recommended Validation
Run:

```bash
bash run-backend-check.sh
```

Expected end state:

```text
--- ALL TESTS PASSED ---
```

Then run:

```bash
bash run-all.sh
```

Open forwarded port 3000 in Codespaces.
