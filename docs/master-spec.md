# LucyWorks OS — Master Spec Lock

This file is the hard product spine for LucyWorks OS.
It exists to stop loss between chats, stop drift between docs and code, and define what the system must become.

---

## 1. Product identity

LucyWorks OS is a **hospital command system** and **operational control layer** for specialist veterinary hospitals.

It is not:
- a thin triage app
- a simple rota tool
- a generic CRM
- a demo dashboard
- a receptionist-only workflow

It is an **input-driven, workflow-driven, role-aware operations system** that turns fragmented hospital activity into routed, owned, timed, auditable work.

---

## 2. Core product objective

LucyWorks OS exists to reduce:
- fragmented communication
- hidden blockers
- queue blindness
- unsafe handoffs
- timing drift
- missing ownership
- invisible operational pressure
- department isolation
- poor discharge coordination
- undocumented decisions

The system should behave like a **clinical director and operations command layer**, not a passive record system.

---

## 3. Core system layers

### 3.1 Input layer
Unified input surface for:
- reception/admission input
- phone calls
- emails
- internal messages
- triage entries
- consult updates
- inpatient updates
- ward tasks
- imaging/lab results
- procedure changes
- recovery handoffs
- discharge blockers
- staffing issues
- stock/pharmacy issues
- ethics/safeguarding concerns

### 3.2 Workflow / routing engine
Must determine:
- what the input is
- urgency
- owner role
- owner user
- due window
- linked patient / episode
- linked room / section
- dependencies
- escalation path
- downstream consequences

### 3.3 Operational data model
Must include:
- user
- patient
- owner/client
- episode / visit
- work item
- task
- alert
- thread
- message
- handoff
- procedure
- theatre slot
- ward item
- discharge pack
- shift
- staff member
- stock item
- order
- ethics flag
- audit event
- hospital section
- room
- resource position

### 3.4 Time / dependency engine
Must understand:
- queue ageing
- due times
- blockers
- dependency chains
- room occupancy
- theatre overruns
- turnover windows
- scheduling drift
- staffing fit
- handoff delays

### 3.5 Role-based command views
Different surfaces for:
- ops manager
- clinician
- nurse
- admin / reception
- theatre / anaesthesia / imaging
- pharmacy / stock

### 3.6 Audit / compliance layer
Every material change should record:
- actor
- action
- target entity
- time
- old/new state where relevant
- operational consequence where relevant

---

## 4. Named product layers

### Lucy Flow
Intake, triage, routing, urgency, escalation, handoff.

### Lucy Pulse
Live hospital health layer:
- backlog
- ageing items
- section pressure
- unresolved blockers
- staffing strain
- theatre slippage
- ward pressure
- unowned work

### LucyRota
Staffing layer:
- shifts
- skills matrix
- on-call rules
- gap detection
- overtime approvals
- safe staffing warnings

### Lucy Care
Continuity layer from admission through discharge.

### Lucy Ethics
Safeguard/risk layer:
- pain concerns
- consent issues
- repeat sedation concerns
- welfare concerns
- financial constraint impact on care
- operational ethical pressure

### Mail Ops
Operational email layer:
- thread ownership
- attachment to live work/episode
- unresolved/ageing flags
- audit trail

### Messaging
Internal coordination layer:
- thread ownership
- attachment to operational work
- material decision visibility
- unresolved thread state

---

## 5. Hospital topology

### Sections
- Reception
- Triage
- Consults
- Theatres
- Recovery
- ICU
- Wards
- Imaging
- Lab
- Pharmacy
- Discharge
- later: Isolation, Stores, Admin base, Staff base

### Rooms / spaces currently in active build target
- Front Desk
- Meet and Greet
- Triage Bay
- Consult Room 1
- Consult Room 2
- Theatre 1
- Theatre 2
- Recovery Bay
- ICU Bay Area
- Ward Dogs
- Ward Cats
- Imaging Room
- Lab Bench
- Pharmacy Store
- Discharge Desk

### Resource positions later needed
- kennel/cage
- bay
- treatment table
- scanner slot
- theatre slot
- bed space

Every work item should be placeable by:
- section
- room
- optional patient location / resource position

---

## 6. Role model

### Ops Manager
Needs:
- command board
- pulse
- section pressure
- staffing pressure
- audit overview
- escalation visibility
- access to ward / theatre / consult / queues / audit / input

### Clinician
Needs:
- command access
- consult view
- ward / ICU
- theatre / recovery
- own work
- review queues
- audit visibility where relevant

### Nurse
Needs:
- ward / ICU
- theatre / recovery
- queues
- input
- task ownership
- blocker visibility

### Admin / Reception
Needs:
- input
- queues
- audit where appropriate
- later: admissions / owner communication / discharge support / mail ops

---

## 7. Current coded areas in repo

Current active implemented or partially implemented areas:
- access / login page (demo session)
- workspace shell
- command board
- ward / ICU board
- theatre / recovery board
- unified input
- queues
- audit
- topology APIs
- seeded location-aware work items

---

## 8. Areas that must exist in full hospital system

### 8.1 Command / Clinical Director
Must show:
- red alerts
- unowned work
- section pressure
- priority work
- discharge blockers
- theatre risk
- ward pressure
- imaging reviews
- consult pressure
- staffing risk

### 8.2 Consult Rooms
Must show:
- room-by-room consult state
- in-room work
- notes incomplete
- owner update overdue
- follow-up pending
- escalation / onward pathway
- room occupancy / consult overrun later

### 8.3 Ward / ICU
Must show:
- location-level inpatient load
- meds / monitoring due
- blockers
- discharge readiness
- clinician review due
- nurse queue
- handoff issues

### 8.4 Theatre / Recovery
Must show:
- prep blockers
- theatre risk
- recovery handoff gaps
- room occupancy
- later 15-minute schedule and turnover drift

### 8.5 Mail Ops / Messaging
Must show:
- thread lists
- open thread
- owner
- unresolved status
- linkage to episode/work item
- ageing
- audit

### 8.6 Discharge
Must track:
- owner communication done/not done
- meds ready/not ready
- documents complete/incomplete
- transport / pick-up readiness
- blockers

### 8.7 Imaging / Lab
Must track:
- reports awaiting review
- results attached/unattached
- escalation to clinician
- downstream route into episode/work item

### 8.8 Pharmacy / Stock
Must track:
- shortages
- orders
- approvals
- restricted workflows
- audit / compliance

### 8.9 Staffing / LucyRota
Must track:
- shifts
- skills matrix
- safe staffing rules
- on-call logic
- clash detection
- approvals
- operational load by section/time

---

## 9. Golden workflow spine

The first true system path is:

**input -> classification -> routing -> owner -> visible in correct board/queue -> action taken -> audit recorded -> command/pulse updated**

The mature system path becomes:

**input -> linked patient/episode -> routed by rules -> timed and dependency-aware -> visible in section board + command -> acted on by role -> downstream effects update automatically -> audit + compliance trail preserved**

---

## 10. Known major missing pieces

### Missing from current build
- real auth
- server-side permission enforcement
- patient entity and owner/client entity in live app flow
- episode/visit lifecycle in live app flow
- consult board
- mail ops / messaging
- discharge system
- imaging/lab operational boards
- pharmacy/stock workflows
- staffing / LucyRota
- 15-minute theatre scheduler
- dependency engine
- escalation engine
- notification/live update layer
- user management
- proper signed-in app shell/navigation
- tests

### Missing from cross-chat continuity
Some earlier LucyWorks thinking may not be fully embodied in repo code/docs yet. This file is intended to stop further loss.

---

## 11. Build order from here

1. Finish Consult Rooms board
2. Build shared signed-in app shell
3. Add patient + episode model
4. Add Mail Ops / Messaging
5. Deepen Ward / ICU with due-task/discharge logic
6. Deepen Theatre / Recovery with 15-minute schedule + turnover + drift
7. Build LucyRota
8. Build Discharge
9. Build Imaging / Lab
10. Build Pharmacy / Stock
11. Build Lucy Ethics layer
12. Build full workflow engine / escalation rules

---

## 12. Hard rules

- No Streamlit
- No dead buttons
- No placeholder nav to useless pages
- No module drift without updating this file
- No building sideways before linking new work back to command, audit, roles, and topology
- Every new area must connect back to the command layer

---

## 13. Definition of usable

LucyWorks OS is only truly usable when:
- a user can sign in under a real role
- they see the right hospital areas
- inputs become owned work automatically or semi-automatically
- work is linked to patient/episode/location
- ward, theatre, consult, and comms surfaces all function together
- timing, blockers, and handoffs are visible
- audit is reliable
- command board reflects reality rather than isolated counters
