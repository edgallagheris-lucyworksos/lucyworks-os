# LucyWorks OS

LucyWorks OS is a hospital command system and operational control layer for specialist veterinary hospitals.

It is not a thin triage app, a simple rota tool, a generic CRM, or a prototype dashboard. It is an input-driven, workflow-driven operations platform that turns fragmented hospital activity into owned, routed, auditable work.

## Start here on a phone

You do not need commit numbers. You do not need to type every test.

### Best way in GitHub Codespaces / VS Code

Open the command palette:

```text
Ctrl/Cmd + Shift + P
```

Then run one of these tasks:

```text
Tasks: Run Task -> LucyWorks: Check All
Tasks: Run Task -> LucyWorks: Run Dev
```

### If using the terminal

Check the whole system:

```bash
bash scripts/check-all.sh
```

Run the full dev system:

```bash
bash scripts/run-dev.sh
```

That is the phone-friendly workflow.

## What opens

When `LucyWorks: Run Dev` is running:

```text
Backend:  http://localhost:8000
Frontend: http://localhost:3000
```

In Codespaces, use the forwarded port links for `3000` and `8000`.

## What to test first

Open these pages in this order:

1. `/readiness` — tells you what is ready, partial, or missing.
2. `/command` — Lucy Command view.
3. `/workspace` — role-filtered staff queues.
4. `/actions` — buttons for acknowledge/review/resolve/approve/start.
5. `/flow-state` — blockers, gates, handovers, occupancy and staff-risk.
6. `/catalogues` — procedures, diagnostics and formulary.
7. `/hr` — LucyRota / HR depth.
8. `/overnight` — Lucy Care / inpatient layer.

## Lucy module spine

- **Lucy Command** — clinical director / ops command surface.
- **Lucy Pulse** — live operational health, pressure, backlog, timing drift and ageing items.
- **Lucy Flow** — intake, triage, routing, urgency and escalation.
- **Lucy Ethics** — safeguard and decision-risk layer.
- **Lucy Care** — continuity from admission through prep, procedure, ward, owner comms and discharge.
- **LucyRota** — staffing, skills, on-call, gaps, approvals, safe staffing and HR depth.
- **Lucy Theatre** — 15-minute scheduling, turnover, delay ripple effects and staffing fit.
- **Lucy Ward** — live inpatient state, due tasks, blockers, ownership and discharge readiness.
- **Lucy Diagnostics** — imaging/lab result lifecycle, review ownership and overdue results.
- **Lucy Pharmacy** — formulary, stock, restricted workflows and auditability.
- **Lucy Comms** — owner communication and internal coordination.
- **LucyTrace** — audit, governance, override history and decision trail.

## Current coded build

The repo now includes a usable platform spine:

- FastAPI backend
- Next.js frontend
- hospital structure, rooms, staff, shifts and schedule blocks
- command/dashboard views
- role-filtered Workspace
- Live Actions page
- Flow State page
- Readiness checker
- HR / LucyRota depth
- catalogue import models/routes
- procedures/formulary/diagnostics pages
- overnight/inpatient layer
- live action gates
- audit events
- CI smoke tests

## Test rule

Every serious module should have all five:

1. backend model/route
2. smoke test
3. CI entry
4. frontend page
5. user action path

## Docs in this repo

- `docs/lucy-module-spine.md`
- `docs/platform-spine.md`
- `docs/system-sections.md`
- `docs/data-model.md`
- `docs/screen-map-by-role.md`
- `docs/build-order.md`
