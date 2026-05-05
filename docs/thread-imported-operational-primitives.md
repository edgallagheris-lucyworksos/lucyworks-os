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

## Next implementation slice

1. Add persistent flow tables/routes for handover, results, admissions and discharge blockers.
2. Add severity gate function and enforce it across high-risk actions.
3. Add alert catalogue to backend seed/state.
4. Add messaging template catalogue and UI actions.
5. Add speech target metadata to support dictated notes, handovers and discharge drafts.
6. Surface all of this through Lucy Pulse, Command Layer and My Workspace.
