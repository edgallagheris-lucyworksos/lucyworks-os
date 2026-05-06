# LucyVet OS — Time-First Hospital Board

## Correction
The main hospital board must not start with Theatre 1, Theatre 2, Theatre 3, or static room rows.

The organising principle is:

1. **Time slot** — 15-minute blocks across the day.
2. **What is happening** — procedure, consult, scan, observation, medication, owner update, lab/result review, cleaning, admission/discharge step.
3. **Where it is happening** — room, theatre, MRI, CT, ward, ICU bay, consult room, pharmacy, lab.
4. **Who it is happening with** — specialist, anaesthetist, nurse, admin, imaging staff, pharmacy owner, ward owner.
5. **What team/system it links into** — Imaging, Theatre, ICU, Ward, Pharmacy, Reception, Owner Comms, LucyRota, LucyTrace.
6. **What action is required next** — start, acknowledge, review, assign, escalate, move state, resolve blocker, update owner, clean/ready room.

The point is that every team can look at the shared time-board and see what is happening without repeatedly asking the clinical director.

## Primary board structure

Columns are time.

```text
07:00 | 07:15 | 07:30 | 07:45 | 08:00 | 08:15 | ...
```

Rows are not simply rooms. Rows are **time-slot event stacks** grouped by operational layer:

- Red / critical events
- Admissions / intake
- Consult / triage
- Diagnostics / imaging
- Surgery / theatre
- ICU / ward
- Pharmacy / meds
- Lab / results
- Owner comms / admin / insurance
- Room turnover / cleaning
- Staffing conflicts

Each 15-minute slot shows what is happening inside that quarter-hour and who needs to know.

## Event block shape

Every event in the grid must show:

```text
Time
Episode / patient
Action/state
Location
Owner/team
Required people
Blocker/risk
Next action
```

Example:

```text
10:15
EP-2041 Bella / Dog
Anaesthesia start
Theatre 2 / Prep
Owner: Anaesthesia + Ortho
Nurse: Theatre Nurse 1
Risk: ICU bed needed 12:00
Next: start through gate
```

## Why this matters

The clinical director or day runner does not want to manage from a static list of rooms. They need a chronological control surface:

- What is happening now?
- What happens next?
- Which team owns it?
- Which room/person/resource is involved?
- What is blocked?
- What has changed?
- Who needs to act without asking again?

## View model

The board should be generated from the database, not invented in the UI.

Input tables:

- ScheduleBlock
- Episode
- WorkItem
- RoomState
- StaffMember
- Shift
- ResultReview
- PharmacyRequest
- StockItem
- Admission / InpatientStay
- ObservationTask
- MedicationDue
- Blocker
- EthicsFlag
- OwnerCommsRequirement
- AuditEvent

## Required frontend views

1. `/hospital-board` — time-first day control board.
2. `/hospital-board?view=exceptions` — late, blocked, unowned, unsafe.
3. `/hospital-board?view=my-team` — filtered by role/team.
4. `/cases/[episode_ref]` — case timeline and state/action history.
5. `/departments/[department]` — department-specific queue derived from the same time board.

## Mobile behaviour

Phone view should show:

```text
NOW
current 15-minute slot
next 15-minute slot
red/blocked events
my team events
quick actions
```

The phone is not for staring at the whole day grid. It is for knowing what matters now and acting quickly.

## Acceptance criteria

- The board begins with time, not room names.
- Every slot shows what is happening, where, with whom and what team owns it.
- Every event links to an episode/case, department, team and action.
- Staff can filter to their team and see their responsibilities without asking the clinical director.
- State-changing actions call backend workflow gates and write audit events.
