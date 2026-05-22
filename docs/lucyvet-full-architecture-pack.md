# LucyVet OS Full Architecture Pack

This document is the architecture contract for LucyVet OS within the wider LucyWorks OS platform.

It is intended for senior developers, systems engineers, product designers, Codex tasks, and future implementation work. It defines what the system is, what it is not, the operational model, the core data spine, department logic, scheduling model, dashboards, conflict detection, audit, compliance, and staged build boundary.

## System definition

LucyVet OS is a real-time hospital operations coordination and conflict-resolution layer.

It does not replace the patient record by default. It sits above or alongside existing practice software and focuses on what the hospital is doing now:

- cases;
- people;
- rooms;
- theatres;
- imaging;
- ICU;
- wards;
- labs;
- handoffs;
- delays;
- pressure;
- next actions.

The system exists to expose operational truth and reduce hidden coordination failure.

## 1. Product position

LucyVet OS should be understood as a hospital command and operational intelligence system, not a generic SaaS dashboard and not cutesy pet software.

Product hierarchy:

- LucyWorks OS = parent platform.
- LucyVet OS = hospital product.

The system should feel like:

- hospital command system;
- operational intelligence;
- live control layer;
- clinical x operational x premium.

It should not feel like:

- generic SaaS;
- pet owner app;
- AI fluff;
- admin spreadsheet clone.

## 2. Capacity and scale assumptions

The system must be designed for a large specialist referral hospital, not a small clinic.

Assumptions:

- 200 to 500 active operational patient records in scope.
- 50 to 150 concurrent inpatients / ICU / ward patients.
- 5 live theatres simultaneously, with more theatre / procedure resources configured.
- 10 to 11 consult rooms as a known baseline, plus imaging, ICU, wards, isolation, labs, prep and recovery.
- Thousands of tasks, schedule blocks and events per day under load.
- Many simultaneous users across specialists, nurses, imaging, reception and operations.

## 3. Hospital operational model

| Operational area | Examples at large hospital scale | Why it matters systemically |
|---|---|---|
| Departments | Surgery, imaging, internal medicine, neurology, oncology, ICU, wards, reception, labs, pharmacy | Cases move across departments; ownership must not become ambiguous. |
| Resources | Theatres, MRI, CT, consult rooms, ICU beds, ward beds, isolation, prep, recovery | Schedules fail when rooms, kit or capacity are invisible. |
| Staffing | Specialists, anaesthetists, imaging staff, nurses, PCAs, reception and operations | Specialist labour is scarce and cannot be double-booked. |
| Case movement | Triage -> consult -> diagnostics -> theatre -> ICU/ward -> discharge | The system must detect where cases stall or conflict. |

## 4. Core modules

| Module | Responsibility | Notes |
|---|---|---|
| LucyCore | Identity, permissions, departments, specialists, rooms, roles, audit and access logging | Foundation layer shared across modules. |
| LucyFlow | Case intake, triage, stage movement, handoffs and next required action | Case is the operational anchor. |
| LucyRota | Planned shifts, actual availability, on-call, role and specialist coverage | Must separate planned shifts from live exceptions. |
| LucyTrack | Tasks, case timeline, handover objects and result review loop | Operational continuity layer. |
| LucyPulse | Pressure index, bottleneck metrics and system tension scoring | Turns operating data into management signal. |
| LucyPharm | Drug and stock movement, controlled item ledger and case-linked dispense | Governance-heavy; likely V1.5 / V2 depth. |
| LucyCompliance | GDPR, access logs, incident trails, credential and visibility controls | Low-visibility during Shadow Mode; core audit remains active. |

## 5. Core data spine

The system should be built around a deliberately small number of first-class entities. Everything else should be linked, derived or evented from them.

| Entity | Purpose | Key links |
|---|---|---|
| Case | Patient episode and operational anchor | Patient, owner, department, tasks, procedures, handoffs, results, billing and audit. |
| Department | Specialist operational unit | Specialists, resources, SLA targets, handoff rules. |
| Specialist / StaffMember | Named operator with skill and authority | Shift, assignment, department, procedure list, on-call. |
| Shift | Planned working window | User, shift type, on-call state, extension / overtime. |
| Resource | Theatre, MRI, CT, consult room, ICU bed, ward bed, stock or kit | Schedule blocks, department, capacity, status. |
| ProcedureType | Procedure catalogue entry | Default duration, prep, recovery, cleaning, staff and room requirements. |
| CaseProcedure | A procedure planned for a case | Case, procedure type, scheduled blocks, complexity and overruns. |
| ScheduleBlock | 15-minute-snapped operational block | Prep, anaesthesia, procedure, recovery, cleaning, consult, imaging and review. |
| Task | Assignable work item | Case, owner, due time, status, escalation. |
| Handoff | Cross-user or cross-department transfer | From/to roles, reason, acknowledgement SLA. |
| Result | Lab or imaging output requiring review | Case, source resource, reviewer, review SLA. |
| AuditLog / AccessLog | Tamper-evident change and view trail | All major entities. |

## 6. Department detail pack

### Reception / Intake

Purpose: creates and coordinates incoming operational flow.

Key entities:

- incoming contact;
- referral;
- appointment;
- case intake;
- owner communication;
- consult room;
- queue position.

Workflow states:

- contact received;
- referral captured;
- case created;
- awaiting triage;
- booked;
- arrived;
- waiting;
- handed to clinical team.

Conflicts:

- wrong urgency;
- duplicate case;
- wrong owner details;
- delayed intake;
- consult room unavailable;
- unclear handover.

Dashboard needs:

- arrivals;
- consult room usage;
- waiting times;
- urgent arrivals;
- owner updates due.

Inputs / outputs:

- owner / referring vet / emergency arrival in;
- triage / consult / communication updates out.

### Triage / Consult

Purpose: converts intake into clinical ownership and next-step direction.

Key entities:

- triage queue item;
- consult room;
- specialist;
- nurse support;
- case urgency;
- next required action.

Workflow states:

- awaiting triage;
- in consult;
- awaiting diagnostics;
- awaiting treatment decision;
- discharged to next stage.

Conflicts:

- triage backlog;
- room pressure;
- specialist unavailable;
- handoff ambiguity;
- no next action.

Dashboard needs:

- queue by urgency;
- current consults;
- blocked consults;
- pending ownership;
- time in state.

### Imaging

Purpose: provides MRI, CT, X-ray, ultrasound and related throughput.

Key entities:

- MRI suite;
- CT suite;
- imaging room;
- imaging specialist;
- imaging nurse;
- sedation / anaesthesia requirement;
- result;
- reviewer;
- imaging queue.

Workflow states:

- requested;
- booked;
- waiting;
- in scan;
- reporting;
- result returned;
- reviewed;
- actioned.

Conflicts:

- queue overflow;
- sedation delay;
- anaesthesia dependency;
- reviewer not assigned;
- unreviewed result;
- emergency scan jumping queue.

Dashboard needs:

- queue by urgency;
- slot utilisation;
- delayed scans;
- result review SLA;
- downstream ownership.

### Surgery / Theatre

Purpose: delivers scheduled and emergency procedures using theatres, anaesthesia, prep, recovery and specialist teams.

Key entities:

- theatre;
- procedure room;
- prep area;
- anaesthetist;
- specialist surgeon;
- theatre nurse;
- CaseProcedure;
- ScheduleBlock;
- CleaningBlock;
- equipment / implants.

Workflow states:

- waiting for theatre;
- in prep;
- anaesthesia start;
- procedure in progress;
- recovery;
- cleaning;
- ready again.

Conflicts:

- anaesthetist double-booked;
- theatre not cleaned in time;
- procedure overrun;
- kit missing;
- ICU bed unavailable after procedure;
- emergency add-on disrupts list.

Dashboard needs:

- live theatre board;
- start / expected end / actual end;
- overrun risk;
- next case waiting;
- cleaning state;
- ICU destination pressure.

### ICU

Purpose: handles highest-acuity inpatients requiring close monitoring, stabilisation and rapid escalation.

Key entities:

- ICU bed group;
- PatientStay;
- ICU nurse;
- ICU clinician;
- monitoring task;
- drug task;
- transfer task.

Workflow states:

- admitted;
- stable;
- unstable;
- escalated;
- transfer pending;
- discharged to ward;
- discharged from hospital.

Conflicts:

- bed full;
- monitoring overdue;
- transfer blocked;
- unsafe ratio;
- emergency admission with no capacity;
- recovery arrival from theatre with no ready bed.

Dashboard needs:

- census;
- bed occupancy;
- next observations due;
- critical alerts;
- transfer in / out flow;
- staffing visibility.

### Wards

Purpose: manages inpatient flow after ICU or surgery and before discharge.

Key entities:

- PatientStay;
- ward bed / ward capacity;
- ward nurse;
- monitoring task;
- medication task;
- discharge prep task.

Workflow states:

- admitted;
- settled;
- monitoring active;
- review due;
- discharge prep;
- transfer back to ICU;
- discharged.

Conflicts:

- too many inpatients;
- meds overdue;
- discharge blocked;
- nurse overload;
- unstable patient not escalated.

Dashboard needs:

- patient census;
- next meds due;
- next observations due;
- discharge blockers;
- escalation flags.

### Discharge

Purpose: moves a case safely out of the hospital with owner communication and task completion.

Key entities:

- discharge checklist;
- meds;
- instructions;
- owner update;
- final sign-off;
- complete.

Workflow states:

- pending discharge;
- blocked;
- ready for sign-off;
- complete.

Conflicts:

- meds not ready;
- owner not informed;
- review pending;
- transport delay;
- documentation incomplete.

Dashboard needs:

- discharge queue;
- blockers;
- sign-off ownership;
- time waiting to leave.

### Rota / Staffing

Purpose: defines who is planned, who is actually available, who is on-call, and who is extended or in overtime.

Key entities:

- PlannedShift;
- AvailabilityState;
- ExtendedShiftBlock;
- OvertimeRequest;
- OnCallDuty.

Workflow states:

- on shift;
- off shift;
- on call;
- extended;
- overtime requested;
- overtime approved.

Conflicts:

- overlaps;
- staffing gaps;
- unapproved overtime;
- on-call callout overload;
- skill mismatch.

Dashboard needs:

- who is on;
- who becomes free;
- who is extended;
- skill coverage;
- department pressure.

### Labs

Purpose: handles in-house lab processing and result return loops.

Key entities:

- sample;
- lab queue;
- result;
- reviewer;
- repeat task.

Workflow states:

- requested;
- sample received;
- in process;
- result returned;
- reviewed;
- actioned.

Conflicts:

- result backlog;
- repeat request delays;
- no reviewer assigned;
- result not actioned.

### Pharmacy / Stock

Purpose: tracks pharmaceuticals, consumables and controlled items needed to keep the hospital running.

Key entities:

- item;
- stock lot;
- stock move;
- purchase order;
- case-linked dispense.

Workflow states:

- in stock;
- low stock;
- ordered;
- received;
- dispensed;
- wasted / adjusted.

Conflicts:

- low stock;
- missing controlled-drug trail;
- discharge meds not ready;
- theatre stock missing.

## 7. Scheduling and time engine

- All schedule blocks snap to 15-minute boundaries: 00, 15, 30, 45.
- One planned procedure becomes a linked chain of blocks: prep -> anaesthesia -> procedure -> recovery -> cleaning.
- Anaesthesia is a separate personal timeline for the anaesthetist, but embedded in the global and departmental timeline.
- Cleaning and turnover are first-class schedule constraints, not notes.
- The system recalculates instantly on event change: overrun, room not ready, handoff delay, result return, approval or extension.

### Procedure knowledge model

- Procedure durations come from a configurable catalogue, not free text.
- Each ProcedureType defines default duration, prep time, recovery time, cleaning time, staff requirements, room requirements and equipment requirements.
- Optional overrides can depend on complexity, species, weight band or department practice.

## 8. Timeline and dashboard model

| View | Audience | Primary purpose |
|---|---|---|
| Global Command View | Ops manager / clinical director | Everything view: live theatres, imaging, ICU pressure, departments and blockers. |
| Department View | Department lead | Filtered timeline and conflict view for one service line plus cross-department impacts. |
| Specialist Day View | Individual specialist | My day, my timeline, my handoffs, my changes, my pending reviews. |
| Nurse / Ward View | Nursing teams | Ward census, monitoring tasks, transfers, meds, discharge blocks and critical alerts. |
| Personal Action Queue | All users | Next required action ordered by urgency and ownership. |

### Display philosophy

- Managers need all departments at once.
- Department leads need their department plus cross-department impacts.
- Specialists need their timeline, not full hospital noise.
- Nurses need execution focus: beds, tasks, transfers, meds, monitoring and discharges.
- Everyone needs to see what changed without asking.

## 9. Conflict detection engine

The system must identify and surface conflicts, not merely display schedules.

Conflict types:

- Resource conflict: same theatre, MRI, CT or consult room double-booked, or blocked by cleaning or overrun.
- Staff conflict: specialist, anaesthetist or nurse double-booked or scheduled beyond availability.
- Department conflict: handoff pending, review responsibility unclear, cross-department assumption loop.
- Time conflict: schedule chain slippage creating impossible downstream timings.
- Capacity conflict: ICU or ward saturation, imaging queue overflow, prep bottleneck.
- Result conflict: result returned without reviewer or review outside SLA.

## 10. LucyPulse

LucyPulse turns raw operating data into a live pressure picture. It is an operational stress model, not a generic analytics dashboard.

| Input | Examples |
|---|---|
| Case pressure | Unstable cases, backlog by stage, delayed discharges. |
| Resource pressure | Theatre overruns, imaging queues, cleaning delays. |
| Staff pressure | Availability extensions, nursing overtime, on-call callouts. |
| Capacity pressure | ICU occupancy, ward census, isolation occupancy. |
| Execution pressure | Unacknowledged handoffs, overdue tasks, unreviewed results. |

## 11. Handoffs and result review

- Every handoff must be an object with from/to department, from/to clinician, reason, required action, requested time, acknowledgement time and SLA.
- Every result must have an assigned reviewer and review SLA.
- No case should leave one operational stage without a clear next required action and owner.

## 12. Workforce, compliance and audit

| Need | Implementation direction |
|---|---|
| Role security | Role-based access control with department scope and specialist labels. |
| Authentication | Username/password plus JWT, later optional fast unlock for shared terminals. |
| Availability | PlannedShift plus live AvailabilityState / ExtendedShiftBlock / OvertimeRequest. |
| GDPR / access | AccessLog for record views, AuditLog for changes, data classification and retention policy. |
| Incident handling | InteractionSignal first; person-level BehaviourSignal only after review; HRIncident if escalated. |
| Tamper evidence | Append-only logs with hash chaining rather than blockchain complexity. |

## 13. Shadow Mode

During side-by-side validation, governance and behavioural features should remain low-visibility or disabled.

The first proving stage is:

- scheduling truth;
- conflict detection;
- operational awareness.

## 14. Stage plan

| Stage | Purpose | Must be true at the end |
|---|---|---|
| Stage 1 | Core machine | Backend, schema, auth, audit, shifts, resources, cases, procedures and scheduling spine exist. |
| Stage 2 | 99% operational product | Hospital workflows, dashboards, conflicts, pulse, Shadow Mode and side-by-side comparison exist. |
| Stage 3 | Polish only | Aesthetics, spacing, speed and usability refinement; no major architecture change. |

## 15. Recommended V1 boundary

### In scope

- Case;
- Department;
- Specialist;
- Shift;
- Resource;
- ProcedureType;
- ScheduleBlock;
- Task;
- Handoff;
- Result;
- AuditLog;
- Pulse;
- three core views;
- import contract;
- synthetic large-hospital day.

### Out of scope for first proving pass

- full billing;
- insurance;
- full clinical record replacement;
- heavy analytics;
- broad AI features;
- blockchain;
- owner collaboration;
- full external practice-management integration.

## 16. Technical stack recommendation

| Layer | Recommended stack |
|---|---|
| API / service layer | FastAPI (Python). |
| Database | PostgreSQL with Alembic migrations. |
| Realtime | WebSockets or Server-Sent Events. |
| Auth | JWT plus role-based access control. |
| UI | Mobile-first web client with role-weighted dashboards. |
| Hosting | GitHub as source of truth; real web-service host for runtime, not task-preview. |

## 17. Build path

- Sprint 0: auth, roles, departments, specialists, audit logging, deployment that exposes a real URL.
- Sprint 1: shifts, availability, on-call, extension / overtime distinctions, overlap guard.
- Sprint 2: ProcedureType, CaseProcedure, ScheduleBlock, linked block generation.
- Sprint 3: collision detection, overrun propagation, Pulse snapshots, global / department / personal views.
- Sprint 4: CSV import, reconciliation, synthetic day, side-by-side comparison.

## 18. Closing summary

LucyVet OS should be understood as hospital operations infrastructure rather than a general dashboard.

Its value is real-time coordination across departments, people, rooms, equipment and time.

The architecture must respect the hospital as a live system:

- cases move;
- schedules slip;
- cleaning matters;
- specialists are scarce;
- ICU fills;
- handoffs fail;
- people need to know what changed without asking around.

## Implementation rule

Future code changes must map back to this architecture pack. If a module, screen, API endpoint, dashboard or database entity cannot be explained against this document, it should not be treated as core LucyVet OS work.
