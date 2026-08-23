# LucyWorks System Contract

This file is the build contract for LucyWorks OS. Future work must follow this contract before adding pages, components, routes, domain models or features.

## Product target

LucyWorks OS is a connected referral-hospital operating system. It must show the day in one place, reduce typing, expose blockers early, protect staff and resource capacity, preserve clinical/operational authority, and turn updates into structured accountable work.

## Canonical implementation

```text
apps/web = canonical staff-facing web application
apps/api = canonical backend/API, persisted state, auth, governance and operating services
```

Do not create or restore another top-level frontend/backend implementation.

## Non-negotiable architecture

### 1. One persisted source of truth

LucyWorks must not be built as separate disconnected pages, boards, databases or schedules.

The connected operating model combines:

```text
patients / episodes
+ procedure templates / planned work
+ staff / skills / shifts
+ rooms / resources / capacity
+ blockers / decisions / handovers
+ 15-minute time control
= shared scheduled operational state
```

Where state is persisted, the canonical backend in `apps/api` is authoritative. `apps/web` may derive, filter, group and render that state but must not create a second persistent hospital reality.

The existing generated day-control model remains a useful operational/view model during convergence. It must progressively consume canonical backend state rather than compete with it.

### 2. Fifteen-minute time control

The base operational scheduling unit is a 15-minute slot where appropriate.

Every operational item must expose enough information to answer:

```text
time
lane / area
patient or subject
episode
what
who
where
how
status
blocker
next action
staff/resource ownership
evidence/audit consequence
```

### 3. Procedure templates generate connected work

A procedure is not just a label. It must generate or require the connected work chain appropriate to that procedure, for example:

```text
prep
room/resource use
staff role/skill requirements
anaesthesia where required
procedure / diagnostic slot
recovery or handover
cleaning / turnover where required
client/contact update
decision / result review
```

Durations and dependencies must be explicit enough for schedule and capacity calculations.

### 4. Every screen is a view/action surface over the same hospital model

Hospital, department, patient, shift, rota, theatre, imaging, care/ward, pharmacy, intake, flow and governance surfaces may present different views, but they must not invent separate work or patient models.

A departmental view must be a filter, projection or specialised workflow over canonical entities and shared state.

### 5. The hospital board is command overview, not a toy dashboard

The primary hospital operating view must expose at referral-hospital scale:

```text
Now
Next
Blocked / exception work
15-minute time control
active case/procedure chains
staff/resource pressure
missing ownership/location
client/contact update needs
safety/governance pressure
```

It must stay compact and useful at the scale defined in `PRODUCT_CONTRACT.md`.

### 6. Actions update shared state

Actions such as:

```text
assign
hold
block
resolve
handover
request review
complete
move / reschedule
emergency override
```

must operate on canonical entities/shared state, respect permission and authority boundaries, and create the required evidence/audit record.

A button that only changes local visual state is not a completed operational feature unless that local state is explicitly temporary and cannot be mistaken for hospital truth.

### 7. Contact updates are generated from facts

Staff should not need to rewrite known operational facts manually.

Updates may be generated from canonical facts such as:

```text
patient / subject
current stage
blocker
next action
owner
expected update point
material decision / consent state
```

Staff review remains part of the workflow where required. AI-generated text is not authoritative evidence until validated/accepted by the relevant workflow.

### 8. Voice capture becomes structured work

Voice input must not become a dead note.

Where voice capture is provided it should resolve into structured canonical work, for example:

```text
speech
→ transcript
→ validated extraction
→ patient / episode
→ blocker / state change / work item
→ owner
→ next action
→ area / time
→ evidence / audit
```

### 9. Staff welfare is operational

The rota/workload system must expose operational safety signals such as:

```text
missed/protected breaks
overload
thin cover
unsafe reassignment
role/skill pressure
rest constraints
available support
```

These signals must connect to real staff, shifts and work rather than decorative scores.

### 10. No new surface without a source-of-truth check

Before adding any page/module/action, check:

```text
Which canonical entity/state does this read?
Which canonical entity/state does this change?
How do other dependent views see the change?
Who is allowed to perform it?
What conflict/safety rules apply?
What evidence/audit is produced?
Does it expose who/what/where/when/how/blocker/next?
```

If those answers are missing, do not build a standalone substitute.

## Current web operating-model files

Day-control model / compatibility layer:

```text
apps/web/lib/day-control-work.ts
```

View adapter:

```text
apps/web/lib/day-control-views.ts
```

Hospital overview includes:

```text
apps/web/components/day-control-grid.tsx
apps/web/app/hospital-board/page.tsx
```

These files remain important, but their persisted data must converge on canonical backend state where the API now supplies it.

## Current backend authority

The active backend entrypoint is:

```text
apps/api/app/main.py
```

Domain services/routes under `apps/api/app` provide the canonical path for persisted hospital state, authentication/access, operational actions, evidence/audit and safety/governance.

## Build order from here

1. Keep `apps/web` + `apps/api` as the only implementation and prevent legacy trees from returning.
2. Complete frontend/backend source-of-truth convergence for day-control and department surfaces.
3. Ensure every live action changes canonical state and produces audit/evidence.
4. Strengthen procedure/resource/staff/skill/dependency conflict and capacity detection.
5. Complete connected domain workflows without falling back to generic disconnected pages.
6. Add/strengthen live update propagation between staff surfaces.
7. Add voice-to-work and other AI assistance only through validated structured boundaries.
8. Keep patient/episode timeline and all role views on the same operating spine.

## AI boundary

AI may assist with extraction, classification, summarisation, retrieval, drafting and explanation.

AI must not bypass:

```text
authentication
role / professional authority
hard safety rules
canonical persistence
validation
human approval where required
evidence / audit
```

The LLM is never the source of hospital truth.

## Hard rule

If a feature creates another disconnected board, patient workflow, schedule, database or source of truth, it is wrong.

LucyWorks OS must remain one connected hospital operating model with multiple specialised views and actions.
