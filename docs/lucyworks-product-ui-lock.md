# LucyWorks OS Product + UI Lock

This document locks the product direction for LucyWorks OS so future frontend, backend, Codex, GitHub, and Codespaces work stays aligned with the intended specialist veterinary hospital operating system.

## 1. Product identity

LucyWorks OS is not a generic veterinary app, task list, CRM, booking board, or dashboard demo.

LucyWorks OS is an operational integrity system for specialist veterinary hospitals.

It exists to make the hospital state visible, actionable, and auditable in real time.

The system must always answer:

- What is unsafe now?
- What is blocking flow?
- Who owns the next action?
- What department, room, patient, owner, staff member, or result is involved?
- What happens if this is ignored?
- What is the clean next action?

## 2. Visual identity lock

The interface must move toward the LucyWorks visual concept:

- Dark cinematic hospital command surface.
- Deep slate / near-black background.
- Subtle teal-blue glow accents.
- Glass-panel cards with fine borders.
- Compact status chips and operational signals.
- Premium specialist-hospital feel, not SaaS toy styling.
- Large LucyWorks wordmark / logo treatment on major entry screens.
- Calm but serious clinical command tone.

Core palette:

- Background: #020617 / #07111f / #0f172a
- Panel: rgba(15, 23, 42, 0.82)
- Border: rgba(148, 163, 184, 0.18)
- Accent: #14b8a6 / #2dd4bf
- Critical: #ef4444
- Warning: #f59e0b
- Stable: #22c55e
- Info: #3b82f6

UI must avoid:

- Plain admin tables as the primary experience.
- Generic Bootstrap/SaaS look.
- Light-mode default dashboards.
- Random page structures that do not map to hospital flow.
- Decorative visuals that hide the operational state.

## 3. Navigation lock

The main operator navigation should be built around the actual hospital operating model:

- NOW
- FLOW
- RESOURCES
- MY SHIFT
- INTERRUPTS
- CASES
- GOVERNANCE

These are not decorative labels. They define the information architecture.

### NOW

Live operational truth.

Must show:

- Current unstable cases.
- Attention cases.
- Next required action.
- Owner role / named owner where available.
- Time since / time due.
- Current RAG state.
- One-click action path.

### FLOW

Department and case movement.

Must show:

- Triage.
- Booking.
- Imaging.
- Theatre.
- Inpatient / ward / ICU.
- Discharge.
- Blocked flow.
- Current queue pressure.

### RESOURCES

Capacity and constraints.

Must show:

- Rooms.
- Theatre availability.
- Imaging availability.
- Ward / ICU capacity.
- Staff visibility.
- Pharmacy / stock pressure.
- Equipment / kit blockers.

### MY SHIFT

Role-filtered personal command view.

Must show only what the logged-in user role needs:

- Nurse dashboard.
- PCA dashboard.
- Manager dashboard.
- Vet / clinician dashboard.
- Admin / owner comms dashboard.

No user should be forced into the full command board unless their role requires it.

### INTERRUPTS

Unplanned operational disruption.

Must show:

- Urgent walk-ins.
- Critical case escalation.
- Callback needed.
- Lab result review.
- Theatre blocker.
- Owner complaint / finance blocker.
- Staff or room reassignment.

## 4. Role presentation lock

Each role needs its own presentation layer.

### Manager / Clinical Director

Needs:

- Hospital overview.
- Clinical alerts.
- Operational issues.
- Financial / governance flags.
- Integrity scores.
- Resource status.
- Flow metrics.
- Top risks and next management action.

### Nurse

Needs:

- Current assigned patients.
- Prep checklists.
- Medication readiness.
- Consent / form status.
- Room assignment.
- Handoffs.
- Tasks due now.

### PCA

Needs:

- Current patients.
- Walk-in and urgent flags.
- Lab result pending.
- Patient handoff list.
- Interrupt queue.
- Quick log / assist action.

### Vet / Clinician

Needs:

- Cases requiring decision.
- Clinical status.
- Results to review.
- Consent / finance blocker visibility.
- Discharge readiness.
- Escalations and ethics flags.

### Admin / Owner Comms

Needs:

- Owner updates due.
- Callback queue.
- Consent / finance status.
- Discharge scripts.
- Complaint / boundary flags.

## 5. Logic-to-screen lock

Every screen must connect to operational logic, not just display placeholder cards.

A screen is not accepted unless it shows at least one of:

- real API-fed case state;
- real work item state;
- real schedule / flow state;
- real room / resource state;
- real audit or governance state;
- seeded fallback data that clearly maps to the real schema.

Cards must carry operational meaning:

- RAG state.
- Patient/case identity.
- Current department / room.
- Owner role.
- Time pressure.
- Blocker reason.
- Next required action.

## 6. Backend safety lock

Backend and CI are currently the stable green baseline. UI work must not break it.

Rules:

- Do not rewrite the backend during visual pass unless a screen requires a small API shape improvement.
- Do not delete legacy backend/frontend compatibility files while workflows still reference them.
- Do not create a new architecture.
- Do not bypass smoke tests.
- Keep PRs small enough to verify.

## 7. UI acceptance criteria

A UI/logic PR is not complete until:

- `npm run monorepo:check` passes or equivalent GitHub Actions pass.
- Port 3000 opens in Codespaces.
- `/hospital-board` has the LucyWorks visual language.
- The top navigation reflects NOW / FLOW / RESOURCES / MY SHIFT / INTERRUPTS.
- At least three role views exist: manager, nurse, PCA.
- Role views show different information, not the same generic dashboard.
- The command surface shows active/unstable/attention/next-action states.
- Screens preserve mobile usability.
- No blank 502 Codespaces state remains without a clear log route.

## 8. Branching rule

Stable baseline:

- `main`

Visual + logic alignment branch:

- `ui-logic-lock-lucyworks`

Do not destabilise `main` directly. Work visually on the branch, open a PR, pass checks, then merge.

## 9. Immediate implementation order

1. Create a LucyWorks design shell.
2. Replace generic top navigation with NOW / FLOW / RESOURCES / MY SHIFT / INTERRUPTS.
3. Rebuild `/hospital-board` as the premium NOW view.
4. Add `/resources` for rooms, theatre, imaging, ward, staff, pharmacy.
5. Add `/flow` for triage → booking → imaging → theatre → inpatient → discharge.
6. Add `/my-shift` with role switch or role-aware views.
7. Add `/interrupts` for urgent interruptions and escalation queue.
8. Connect each screen to existing API endpoints or clearly mapped seeded fallback data.
9. Run checks.
10. Open PR.

## 10. Working principle

LucyWorks OS should feel like the hospital's live command layer.

The UI must present the system as a working operational instrument for real staff, not a developer demo.
