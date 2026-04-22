# LucyWorks OS — Platform Spine

## What the platform is

LucyWorks OS is a hospital operations OS.
It is designed to ingest fragmented hospital inputs and convert them into visible, owned, timed, auditable operational work.

## The spine

### 1. Input layer
This is the unified intake surface for all operational events.
Inputs include:
- phone / reception intake
- triage intake
- email
- internal message
- inpatient update
- lab or imaging result
- procedure booking or change
- staffing issue
- discharge blocker
- stock / pharmacy issue
- safeguarding or ethics concern

### 2. Workflow and routing engine
The workflow engine decides:
- what the item is
- its urgency
- its service line
- its owner
- its due window
- its dependencies
- its escalation path
- what downstream systems it affects

### 3. Operational object model
Core objects are not just cases.
The system must support:
- patient
- episode / visit
- work item
- task
- alert
- thread
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

### 4. Time and dependency engine
LucyWorks OS must understand:
- queue age
- due times
- dependency chains
- schedule drift
- theatre overruns
- turnover windows
- handoff timing
- staffing fit by time and skill

### 5. Role-based command surfaces
The same underlying state is presented differently by role:
- ops manager
- clinician
- nurse
- reception / admin
- theatre / anaesthesia / imaging
- pharmacy / stock

### 6. Audit and compliance
Every meaningful action should be visible as:
- actor
- action
- target
- timestamp
- old state
- new state
- operational consequence if relevant

## Golden path for first working build

Unified input -> classified work item -> owner assigned -> appears in correct queue -> action changes state -> audit event recorded -> dashboard / pulse updates

If this path is not working, the system is not yet a usable LucyWorks build.
