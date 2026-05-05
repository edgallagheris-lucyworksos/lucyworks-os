# LucyWorks OS — Imported Operational Primitives

This note captures useful primitives from the uploaded LucyWorks thread files. These are implementation ideas to fold into the current FastAPI/Next.js system.

## Confirmed module registry

The uploaded `__init__.py` exposes a broader module spine than the current app navigation:

- models
- triage
- ethics
- rota
- rota_store
- discharge
- severity
- audit
- trace
- pulse
- policies
- staff
- intake
- room_state
- occupancy
- handover_flow
- results_flow
- admissions_flow
- discharge_flow
- alerts
- messaging
- speech
- governance
- medication
- dashboard_map

These should be treated as the candidate system areas to map into LucyWorks OS.

## Data primitives worth keeping

From `models.py`:

- CaseInput
- TriageOutput
- EthicsOutput
- RotaOutput
- DischargeDraft
- SeverityAssessment
- StaffMember
- IntakeRecord
- RoomStateRecord
- AlertRecord

These are useful because they define the minimum data contracts for intake, triage, ethics, rota, discharge, severity, staff, room state and alerts.

## Rota / HR assignment primitive

From `rota.py`:

- parse comma-separated skills into a skill set
- filter staff by role
- score skill match against required skills
- calculate load_ratio = current_load / max_cases_per_day
- choose the best staff member by highest skill match and lowest load
- return LOW / MED / HIGH rota risk

Procedure examples:
- TPLO requires Surgery, Ortho and TPLO for vet allocation, plus Theatre/Surgery nursing
- Dental requires Dental skill
- Neuro_Spine requires Neuro and Surgery
- Rabbit cases add Rabbit nursing skill

This should become the LucyRota assignment engine for real staff-to-case allocation.

## Rota store / schedule primitive

From `rota_store.py`:

- load_staff
- load_rota
- load_assignments
- save_assignments
- append_assignment
- get_master_rota
- get_staff_schedule

The current system should move these from CSV-style store logic into SQL-backed routes while preserving the concepts:

- master rota
- personal staff schedule
- assignment history
- case-to-staff matching
- role/team/date filters

## Severity engine

From `severity.py`:

- triage red flags => CRITICAL
- safeguarding escalation => CRITICAL
- high rota risk => MODERATE
- minor/default => MINOR

Actions:

- MINOR: log and proceed
- MODERATE: require reviewer identity and reason if overriding
- CRITICAL: block LIVE until safeguarding acknowledged

This should become a backend gate engine used before procedure start, discharge, handover, staff allocation, medication release and owner communication closure.

## Staff type catalogue

From `staff.py`:

- specialist
- nurse
- reception
- coordinator
- ops_manager
- ward_staff
- icu_staff
- imaging_staff
- theatre_staff
- lab_staff
- pharmacy_stock

These should become canonical staff categories for LucyRota / HR / permissions / workspace filtering.

## Intake state primitive

From `intake.py`:

- received
- triaged
- booked
- arrived
- handed_over

These should become the intake lifecycle states from first contact through physical arrival and clinical handover.

## Room state primitive

From `room_state.py`:

- ready
- occupied
- cleaning
- blocked
- reserved
- out_of_service

These must drive the 15-minute grid and prevent false availability.

## Occupancy primitive

From `occupancy.py`:

- space_id
- space_type
- case_id
- occupied_from
- expected_release
- status

Statuses:
- occupied
- due_transfer
- cleaning

This is the missing link between room state, overnight inpatients, recovery, wards, ICU and discharge pressure.

## Discharge draft primitive

From `discharge.py`:

- internal discharge draft includes case ID, patient, species, procedure, priority, assigned vet/nurse and reasoning
- client summary includes patient, procedure/reason, priority and editable at-home care advice

This should become a clinician-editable discharge pack generator, not an auto-send clinical instruction.

## Flow schemas

### Handover flow

Fields:
- from_owner
- to_owner
- case_id
- note
- acknowledged

### Results flow

Fields:
- result_type
- case_id
- review_owner
- status
- reviewed_at

### Admissions flow

Fields:
- case_id
- admitted_to
- admitted_at
- status

### Discharge flow

Blockers:
- meds_not_ready
- review_pending
- owner_not_contacted
- notes_incomplete

These should be turned into persistent backend tables/actions rather than only displayed as static policy tables.

## Alert catalogue

Alert types:
- overdue_result
- blocked_discharge
- room_unavailable
- staffing_gap
- unacknowledged_handover
- icu_pressure
- imaging_backlog
- cleaning_overrun

These map directly into Lucy Pulse, Command Layer and Personal Layer.

## Messaging templates

Message types:
- referral_ack
- arrival_delay
- owner_update
- discharge_ready
- result_reminder

These should become Mail Ops / Messaging templates with patient/case placeholders and audit trail.

## Speech targets

Speech input should be allowed for:
- case_note
- handover_note
- discharge_summary

This should be implemented as speech/dictation target routing, not a generic free-text box.

## CSV assets uploaded

The thread also includes CSV assets that should become database seed/import sources:

- procedures.csv
- formulary.csv
- diagnostics.csv
- assignments.csv

These were uploaded as assets and should be inspected/imported in the codebase rather than treated as complete evidence from this note.

## Compliance primitives

### Clinical responsibility disclaimer

LucyWorks AI is a coordination and scheduling platform. Diagnosis and treatment decisions remain the responsibility of licensed veterinary professionals. The system must not replace clinical judgment.

This needs to be surfaced in product/legal copy and anywhere AI outputs could be mistaken for clinical advice.

### GDPR handling rule

Required controls:

- client data encrypted at rest
- role-based access restriction
- consent for communications and retention
- audit logs for all access events

These must become release gates, not just policy text.

## Backlog ideas not yet built

- DEFRA + microchip registry sync
- insurance claim autofill
- vet-only discussion board
- mobile app mode
- QR-tracking for samples / meds

These are backlog features, not core MVP blockers. Insurance claim autofill and QR-tracking are likely higher value for operational integration than discussion board.

## Next implementation slice

1. Add persistent flow tables/routes for handover, results, admissions and discharge blockers.
2. Add severity gate function and enforce it across high-risk actions.
3. Add LucyRota assignment scoring using skill match and load ratio.
4. Add canonical staff categories and use them for role permissions and My Workspace filtering.
5. Add intake lifecycle states: received, triaged, booked, arrived, handed_over.
6. Add room state gates: ready, occupied, cleaning, blocked, reserved, out_of_service.
7. Add occupancy records for beds / kennels / bays / rooms with expected release.
8. Add alert catalogue to backend seed/state.
9. Add messaging template catalogue and UI actions.
10. Add speech target metadata to support dictated notes, handovers and discharge drafts.
11. Add compliance gates for disclaimer visibility, role access, consent and audit logging.
12. Import procedure / formulary / diagnostic CSV assets into SQL-backed seed/import commands.
13. Surface all of this through Lucy Pulse, Command Layer and My Workspace.
