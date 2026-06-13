# LucyVet + LucyWorks amalgamation map

## Decision

`lucyworks-os` is the runnable monorepo and remains the build target.

`lucyvet-os` is the original product intent source for the specialist veterinary hospital operations system.

The merged product must not be a generic dashboard. It must be a real-time operational coordination and conflict-resolution system for specialist veterinary hospitals.

## Verified source overlap

### LucyVet OS source intent

LucyVet OS describes itself as a real-time operational coordination and conflict-resolution system for specialist veterinary hospitals.

Its backend server wires these domains:

- auth
- roles
- departments
- specialists
- staff members
- shifts
- rooms
- cases
- intakes
- tasks
- handovers
- results
- schedule blocks
- admissions
- discharges
- case events
- dashboard
- conflicts

### LucyWorks OS runnable system

LucyWorks OS is the current monorepo and carries the larger running API surface.

Its API wires these domains:

- v3 operational routes
- ops engine
- input routes
- departments
- forecasts
- readiness
- HR
- catalogue
- workspace
- domain routes
- operating routes
- dashboard
- clinical director
- episode state
- flow state
- live actions
- mail ops
- inpatient
- startup
- safety
- core machine
- workflow actions
- scheduler
- conflict engine
- role queues
- shadow mode
- access control
- realtime

## Product spine

Every screen must be built from the same operational spine:

1. patient or episode
2. department or lane
3. current state
4. blocker
5. owner
6. deadline
7. next action
8. resource impact
9. linked staff member
10. audit trail

No card should exist without a linked entity and a next action.

## Module map

| Module | Route | Job |
|---|---|---|
| NOW | /hospital-board | whole-hospital safety, pressure and next action control |
| LucyFlow | /flow | movement across triage, diagnostics, theatre, ward and discharge |
| LucyOps | /resources | staff, room, theatre, imaging, ward, ICU and pharmacy capacity |
| LucyHR / LucyRota | /my-shift and /staff | shift cover, gaps, breaks, fatigue and role work |
| LucyPulse | /interrupts | callbacks, walk-ins, urgent results and capacity shocks |
| LucyCare | /nurse-dashboard | nursing observations, meds, prep, recovery and discharge |
| LucyMove | /pca-dashboard | patient movement, room handoff and support tasks |
| LucyClinical | /lucy-clinical | clinical results, consult decisions and signoff |
| LucyGov | /lucy-gov | audit, governance, safety and risk trail |
| LucyPharm | /lucy-pharm | stock, medication and discharge pharmacy flow |
| System | /system-control | backend health, seed state, users and system controls |

## Backend merge rule

Use LucyWorks API as the executable backend.

Use LucyVet concepts to harden the domain shape:

- dashboard summary
- dashboard risk
- dashboard flow
- dashboard today
- conflict list
- open conflicts
- conflict detection
- acknowledge conflict
- resolve conflict
- case-linked conflicts

Map those onto LucyWorks endpoints already present, especially:

- /api/conflict-engine/conflicts
- /api/conflict-engine/pulse
- /api/conflict-engine/recalculate
- /api/conflict-engine/to-work-items
- /api/product/now
- /api/product/flow
- /api/product/resources
- /api/role-queues/*

## Frontend merge rule

Do not build one shared fake dashboard.

Each module must have its own screen, but all screens must use the same product spine.

Every module screen must show:

- live state
- blockers
- owner
- deadline
- next action
- linked case or episode
- linked role or person
- linked room or resource
- audit trail

## Required immediate code work

1. Stabilise current build.
2. Replace title-based routing with explicit module metadata.
3. Create `apps/web/lib/hospital-modules.ts` as the source of truth for routes, labels, endpoints and roles.
4. Make `HospitalShell` use that module map for navigation.
5. Make each module page render the proper dedicated screen.
6. Pull conflict pulse and work queues from the real API instead of static display-only data.
7. Add drilldowns from cards into episodes, rooms, staff, conflicts and actions.
8. Run `npm run monorepo:check` after every structural pass.

## Non-negotiable product requirement

The finished system must feel like a specialist hospital operating system:

- clinical director sees risk and decisions
- flow lead sees patient movement and blockers
- ops sees rooms, staff and resources
- nurses see their patient tasks
- PCA sees movement and handoff work
- reception sees owner communication pressure
- governance sees audit, safety and conflict history

If a screen does not help a real hospital role make a decision, it is not a finished screen.
