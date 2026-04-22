# LucyWorks OS

LucyWorks OS is a hospital command system and operational control layer for specialist veterinary hospitals.

It is **not** a thin triage app, a simple rota tool, a generic CRM, or a prototype dashboard.
It is an input-driven, workflow-driven operations platform that turns fragmented hospital activity into owned, routed, auditable work.

## Product framing

LucyWorks OS exists to reduce operational drift, fragmented communication, unsafe handoffs, queue blindness, and hidden blockers across a specialist referral hospital.

The system is built around:
- unified operational input
- routing and ownership
- time and dependency management
- role-based command views
- audit and compliance visibility

## Named system layers

- **Lucy Flow** — intake, triage, routing, urgency, escalation
- **Lucy Pulse** — live operational health, pressure, backlog, timing drift, ageing items
- **LucyRota** — staffing, skills matrix, on-call logic, gaps, approvals, safe staffing
- **Lucy Care** — continuity from admission through prep, procedure, ward, owner comms, discharge
- **Lucy Ethics** — safeguard and decision-risk layer for welfare, consent, repeat sedation, financial and operational concerns
- **Mail Ops** — operational email ingestion, ownership, thread-to-task linking, escalation
- **Messaging** — internal coordination with audit trail and operational attachment to work items
- **Theatre Board** — 15-minute scheduling, turnover, delay ripple effects, staffing fit
- **Ward / Inpatient View** — live inpatient state, due tasks, blockers, ownership, discharge readiness
- **Stock / Pharmacy** — shortage signals, ordering state, restricted workflows, auditability
- **Audit** — who changed what, when, why, and what it affected

## Core architectural rule

LucyWorks OS is built as:
- **input layer**
- **workflow / routing engine**
- **operational data model**
- **role-based command views**
- **time / dependency engine**
- **audit / compliance layer**

It should not be reduced to page-by-page CRUD scaffolding.

## Technical direction

- **Frontend:** Next.js + TypeScript + Tailwind
- **Backend:** FastAPI
- **Database:** PostgreSQL as target, SQLite only as local fallback
- **Ports:** frontend `3000`, backend `8000`
- **Dev flow:** GitHub Codespaces and phone-accessible forwarded ports

## Build rule

The first working build must prove the platform spine:

**Unified input -> workflow routing -> owned work item -> role queue -> audit trail -> command visibility**

The system only counts as real when pressing a button results in usable routed work, visible in the correct operational view with timing and ownership attached.

## Docs in this repo

- `docs/platform-spine.md`
- `docs/system-sections.md`
- `docs/data-model.md`
- `docs/screen-map-by-role.md`
- `docs/build-order.md`
