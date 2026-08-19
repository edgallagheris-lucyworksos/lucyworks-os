# LucyWorks Hospital Command System

## Purpose

LucyWorks Hospital Command is the professional operating workspace for a referral hospital with:

- up to 100 active patients/episodes;
- up to 100 workforce profiles and live rota rows;
- exactly four configured theatres;
- MRI, CT, X-ray, ultrasound and laboratory services;
- ward, ICU, recovery, pharmacy, reception and consultation capacity.

It is an operational coordination system. Clinical decisions remain with the responsible clinician.

## Primary staff workspace

The canonical staff entry point is `/hospital-board`.

| View | Operational question | Authoritative source |
| --- | --- | --- |
| Overview | What needs intervention now? | Authenticated v11 master board |
| Patient flow | Where is every active patient, who owns the next action, and what is blocked? | Authenticated v11 master board |
| Resource grid | What is using each room in each 15-minute period, and what happens if it moves? | Authenticated v11 master board and versioned commands |
| Workforce | Who is on duty, competent, available and required for safe coverage? | Authenticated workforce, rota and coverage services |

The previous `/staff` and `/hospital-ops` screens redirect to the corresponding command views. They are no longer independent operational surfaces.

## System-of-record rules

1. The browser is never the source of truth for clinical operational state.
2. Patient episodes, operational blocks, areas, conflicts and consequences come from the database-backed hospital operations services.
3. Workforce profiles, verified competencies, rota shifts, approved availability exceptions and coverage requirements come from the database-backed workforce services.
4. Every operational write is authenticated and role checked.
5. Safety-relevant writes use expected versions and reject stale changes.
6. Duplicate submissions use idempotency keys.
7. Commands, overrides and consequences create attributable evidence.
8. Cross-site requests are rejected against the authenticated operating context.
9. Legacy day-control data may be used only for shadow comparison or migration; it must not drive a live clinical screen.

## End-to-end operating flow

1. Referral or intake creates a patient episode.
2. The episode enters the governed clinical/operational state machine.
3. Timed blocks allocate rooms, staff, equipment and dependencies.
4. The constraint engine checks room capacity, staff overlap, required skills, gates, equipment and blockers.
5. Overview, patient flow, resource and workforce views project the same server state for different staff decisions.
6. A permitted user previews consequences, submits a versioned command and supplies a reason when required.
7. The server validates authority and current versions in a transaction.
8. The change, conflicts and evidence are stored.
9. Live projections refresh for other staff.

## Capacity contract

Fresh hospital configuration creates:

- Theatre 1–4 only;
- one MRI;
- one CT;
- one X-ray service;
- two-place ultrasound capacity;
- laboratory, pharmacy, preparation, recovery, ICU and ward capacity;
- four consultation rooms.

Existing databases are not silently altered. If their theatre configuration differs from four, the overview shows a configuration mismatch. The site must reconcile and approve the real room register before go-live.

## Scale evidence

Automated acceptance now exercises:

- a 100-patient operational simulation against the four-theatre target;
- a 100-person workforce and live-rota projection;
- emergency insertion, ranked displacement, stale-plan rejection and idempotent replay;
- staff overlap and room-capacity conflict detection;
- competency, absence, rest and coverage-gap assessment;
- desktop, tablet and phone traversal through overview, patient flow, workforce and resource grid;
- the existing hospital-day failure scenarios for emergency arrival, theatre overrun, staffing gap, imaging delay, estimate overrun and critical results.

Scale evidence proves bounded application behaviour; it does not replace load testing with production-like infrastructure and representative concurrent users.

## Production no-go conditions

Do not treat the system as production-ready until all of these are complete:

- every required CI and professional UI check is green;
- production authentication enforcement and OIDC are configured;
- the real four-theatre and diagnostic register is verified;
- real workforce identities, registrations, competencies, shifts and coverage requirements are imported and reconciled;
- backup, restore, retention, incident response and error reporting are configured and tested;
- concurrent-user load, degraded network, downtime and recovery exercises pass;
- clinical safety, information governance and operational owners approve the workflows;
- role-based user acceptance passes a representative hospital day and night handover;
- staff training, support ownership and rollback procedures are signed off.

## Implementation status

Implemented on the hospital-command evolution branch:

- professional hospital overview;
- one-row-per-patient flow;
- 15-minute resource grid integration;
- workforce and safe-coverage view;
- direct links to each command view;
- retirement of the duplicate staff-load and operations pages;
- four-theatre canonical defaults and fixtures;
- 100-patient and 100-person scale acceptance.

Still required before merge or deployment:

- green CI for the complete stacked branch;
- rendered visual review from the CI screenshots;
- reconciliation plan for any existing eleven-theatre data;
- production environment and real-hospital acceptance gates listed above.
