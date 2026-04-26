# LucyWorks OS — Section Spec + Build Gap Map

## Purpose
This file is the build control document for LucyWorks OS.

Do not add random pages or generic dashboards. Every section must follow the hospital operating loop:

```text
Input → Decision → Ownership → Room/Staff impact → Blocker/Escalation → Output → Audit
```

LucyWorks OS is a hospital operations engine for specialist veterinary hospitals.

Core loop:

```text
Episode → Triage → Admission/Consult → Schedule → Rooms → Staff/Rota → Results → Discharge → Owner Comms → Work → Conflict/Ethics/Pulse → Audit
```

---

# 1. Lucy Pulse

## Purpose
Whole-hospital pressure and risk layer.

## Must show
- case pressure
- resource pressure
- staff pressure
- capacity pressure
- execution pressure
- conflict count
- red flags
- delayed decisions
- blocked discharge
- pending result review
- ICU/theatre pressure

## Inputs
- episodes
- work items
- room states
- schedule blocks
- result reviews
- handovers
- conflicts
- staff load

## Decisions
- is the hospital safe to keep accepting work?
- where is pressure building?
- what needs escalation now?

## Roles
- ops manager
- senior clinician
- lead nurse
- admin support

## Escalations
- red pressure
- overloaded staff
- blocked theatre chain
- ICU pressure
- pending result review
- discharge blocker

## Backend needed
- `/api/pulse` exists but is basic
- needs richer scoring model
- needs section-level pressure map
- needs trend/history later

## Frontend needed
- `/pulse` page
- pressure cards
- section map
- top risks
- drill-through links

## Current status
Partial / needs build.

---

# 2. Lucy Ethics

## Purpose
Ethical, welfare and governance risk layer.

## Must show
- pain red flags
- welfare concern
- financial constraint
- repeat sedation
- delayed consent
- treatment refusal risk
- communication risk
- consent gap
- escalation to vet/senior/manager

## Inputs
- triage notes
- work items
- messages
- episodes
- results
- admission/discharge blockers

## Decisions
- is this a clinical/welfare risk?
- does this require vet escalation?
- does this require manager awareness?
- is owner communication or consent inadequate?

## Roles
- clinician
- ops manager
- nurse
- admin

## Escalations
- pain / suffering unresolved
- owner unable/unwilling to consent
- financial constraint affecting treatment
- repeated sedation/procedure risk
- neglect/welfare concern

## Backend needed
- ethics flag model
- ethics endpoint
- create flag from triage/message/result/work
- resolve/escalate endpoint

## Frontend needed
- `/ethics` page
- ethics risk cards
- unresolved flags
- create/escalate/resolve controls

## Current status
Missing.

---

# 3. Triage

## Purpose
Front-door patient routing and red flag detection.

## Must show
- symptom capture
- species-aware risk
- red/amber/green score
- confidence threshold
- information-only advice
- handoff to vet when uncertain
- triage protocol
- red flag escalation

## Inputs
- owner message/call
- symptoms
- species
- patient/episode
- urgency markers

## Decisions
- emergency / same-day / routine
- needs vet now?
- safe to give information-only advice?

## Roles
- admin
- nurse
- clinician
- ops manager

## Escalations
- red flag symptoms
- low confidence
- pain/welfare concern
- owner refuses treatment

## Backend needed
- triage intake model
- triage assessment endpoint
- triage rules/config later
- red flag escalation endpoint

## Frontend needed
- `/triage` page currently exists as filtered work board only
- needs real triage form
- needs risk output and audit

## Current status
Partial placeholder.

---

# 4. Consult Rooms

## Purpose
Manage consult room flow, waiting cases, owner updates and clinical decision points.

## Must show
- room status
- patient waiting
- case in room
- responsible clinician
- nurse support
- diagnostics requested
- admit/discharge/follow-up decision
- owner update requirement

## Inputs
- rooms
- episodes
- work items
- messages
- results

## Decisions
- admit?
- discharge?
- diagnostics?
- procedure booking?
- owner update?

## Backend needed
- consult-board exists
- room-state enrichment exists only in older `main.py` logic, not fully in current stable implementation
- needs decision endpoint

## Frontend needed
- `/consult` exists
- needs shared shell consistency already partly fixed
- needs decision controls

## Current status
Partial.

---

# 5. Admissions

## Purpose
Admitted patient flow and inpatient ownership.

## Must show
- patient admitted
- location
- responsible clinician
- nurse owner
- consent status
- treatment plan
- pending diagnostics
- handover status

## Inputs
- admissions
- episodes
- patients
- rooms
- handovers
- results

## Decisions
- correct location?
- owner assigned?
- plan documented?
- handover complete?

## Backend needed
- admissions exist
- needs owner fields and consent fields later

## Frontend needed
- `/admissions` exists
- needs richer ownership/consent/handover state

## Current status
Partial.

---

# 6. Schedule / Theatre Chain

## Purpose
Procedure chain and time control.

## Must show
- prep
- anaesthesia
- procedure
- recovery
- cleaning
- room turnover
- staff assignment
- delay impact
- chain shift

## Inputs
- procedure types
- case procedures
- schedule blocks
- rooms
- staff

## Decisions
- who owns block?
- room available?
- staff available?
- what shifts when delayed?

## Backend needed
- schedule generation exists
- chain shift exists
- staff assignment exists
- needs duplication policy
- needs staff skill matching
- needs conflict persistence

## Frontend needed
- `/schedule` exists
- needs 15-minute grid
- needs staff names
- needs room grouping
- needs stronger shift controls

## Current status
Partial.

---

# 7. Ward / ICU

## Purpose
Inpatient monitoring, treatment tasks, medication timings and escalation.

## Must show
- inpatient location
- care tasks
- medication timings
- observation tasks
- handover
- discharge blockers
- escalation flags

## Backend needed
- ward board exists as work item grouping
- needs care plan/task model later

## Frontend needed
- `/ward` exists
- needs care timeline and obs/meds tasks

## Current status
Partial.

---

# 8. Results

## Purpose
Clinical result review and action ownership.

## Must show
- pending review
- abnormal flag
- assigned reviewer
- action required
- owner update needed
- reviewed timestamp

## Backend needed
- result reviews exist
- action endpoint exists
- needs abnormal flag and owner update flag

## Frontend needed
- `/results` exists
- needs better review workflow

## Current status
Partial.

---

# 9. Discharge

## Purpose
Ensure safe discharge with scripts, medication, owner comms and sign-off.

## Must show
- discharge scripts
- medication ready
- owner contacted
- invoice/admin ready
- clinician sign-off
- discharge blocker

## Backend needed
- currently generic work items only
- needs discharge checklist model

## Frontend needed
- `/discharge` exists as filtered work board only
- needs checklist/sign-off controls

## Current status
Partial placeholder.

---

# 10. Pharmacy / Stock

## Purpose
Medication, ordering, stock blockers and compliance traceability.

## Must show
- medication request
- controlled/legal status
- authorised supplier logic
- reorder flags
- stock blocker linked to patient/procedure
- audit trail

## Backend needed
- generic work items only
- needs stock item/order model
- needs pharmacy request model
- needs compliance flags

## Frontend needed
- `/pharmacy` exists as filtered work board
- `/stock` exists as filtered work board
- need real ordering/checklist controls

## Current status
Partial placeholder.

---

# 11. Mail Ops / Owner Comms

## Purpose
Owner communication linked to episode and material decisions.

## Must show
- inbound/outbound messages
- linked episode
- decision flag
- clinical handoff
- owner update due
- audit

## Backend needed
- message threads exist
- message entries exist
- material decision flag exists
- needs owner-update-due logic

## Frontend needed
- `/mail` exists
- needs stronger thread detail and reply flow

## Current status
Partial.

---

# 12. Rota / Staff

## Purpose
Staff shifts, skills, load and safe coverage.

## Must show
- shifts
- skills
- department coverage
- on-call
- overtime request
- manager approval
- rest/break rules
- skill matching

## Backend needed
- staff exists
- shifts exist
- staff load exists
- needs rota constraints endpoint
- needs overtime model

## Frontend needed
- `/rota` exists
- `/staff` exists
- needs overtime/approval controls

## Current status
Partial.

---

# 13. Audit

## Purpose
Traceable record of operational actions.

## Must show
- actor
- action
- entity
- summary
- timestamp

## Backend needed
- audit events exist
- logging inconsistent across all endpoints

## Frontend needed
- `/audit` exists
- needs filters

## Current status
Partial.

---

# Current build priority

## Phase 1 — Stabilise demo
1. backend smoke test passes
2. frontend build passes
3. all visible routes load
4. all nav links valid
5. all existing frontend fetches hit valid backend endpoints

## Phase 2 — Add missing control layers
1. Lucy Pulse page
2. Lucy Ethics model/page
3. triage form/model
4. discharge checklist model/page
5. pharmacy/stock models/pages
6. schedule duplication policy
7. rota warnings endpoint

## Phase 3 — Hospital-grade workflow
1. role-specific dashboards
2. staff skill matching
3. 15-minute schedule grid
4. theatre chain impact calculation
5. owner update due logic
6. consent and welfare flags
7. compliance/audit strengthening

---

# Rule for future building
Every section must include:

```text
Purpose
Inputs
Decisions
Roles
Escalations
Outputs
Audit
```

If a page only filters generic work items, it is a placeholder and must be upgraded later.
