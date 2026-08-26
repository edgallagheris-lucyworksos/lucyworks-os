# LucyWorksOS Operational Day-Flow Baseline

This document captures the practical baseline that LucyWorks must improve on when replacing or augmenting the current hospital day-flow/appointments view. It is a product constraint, not a request to copy the existing interface.

## 1. What the current operational view proves

The current hospital view demonstrates that real referral-hospital coordination requires very high information density.

Observed useful characteristics:

- 15-minute vertical time control;
- dozens of simultaneous resource/area lanes visible in one day view;
- compact coloured work/appointment blocks;
- quick day navigation;
- dense use of screen space rather than oversized cards;
- hover/detail access without leaving the schedule;
- all-day operational notes and staffing/coverage messages;
- enough concurrency to show many overlapping cases and staff/resource commitments at once.

LucyWorks must preserve this operational density while making the state easier to understand, search and act on.

## 2. Problems LucyWorks must solve

The current style of grid exposes several limitations that LucyWorks must explicitly improve.

### 2.1 Cryptic lane identity

Short codes are space-efficient but difficult to interpret without local knowledge.

LucyWorks should support:

- code + human-readable label;
- search by either;
- grouped lanes by department/capability;
- hover/tooltip explanation;
- user-selectable focus/filter modes.

### 2.2 Important state hidden in detail popovers

A user should not need to inspect many blocks individually to find operational risk.

The grid itself should surface:

- readiness;
- blockers;
- ownership;
- overrun;
- emergency displacement;
- missing consent/financial authority;
- staffing/resource conflicts;
- communication due state.

### 2.3 Colour cannot carry meaning alone

Use colour only as one channel. Important meaning must also have text/icon/status semantics so that users do not have to memorise colours and accessibility is preserved.

### 2.4 Staffing and rota fragmentation

Where staff rotas, department cover or operational staffing are managed in separate spreadsheets/tabs, LucyWorks should converge the operational facts into the same canonical state.

The system must understand structured concepts such as:

- flow coordinator assignment;
- senior cover requirement;
- actual cover available;
- staffing shortfall;
- affected cases/work;
- escalation/mitigation;
- shift/competency/authority.

Free-text all-day notes may still exist for genuine narrative context but must not be the only representation of known operational facts.

### 2.5 Appointment is not enough

LucyWorks must represent each visible block as part of an episode/work chain, not an isolated calendar event.

A visible block can derive from:

```text
patient / episode
+ work/procedure
+ exact time/duration
+ location/resource
+ responsible owner
+ supporting staff
+ authority
+ readiness
+ dependencies
+ blocker
+ next action
+ evidence
```

### 2.6 Privacy and information minimisation

Quick details should not indiscriminately expose all client/contact/clinical information.

Use:

- minimum necessary information in the grid;
- role-aware quick detail;
- deeper detail on deliberate open/click;
- server-side access control;
- audit for sensitive access where required.

## 3. Two operating views, one state

LucyWorks should provide two complementary views over the same canonical hospital state.

### A. Hospital command view

Optimised for attention management:

```text
NOW
NEXT
BLOCKED
OVERRUNNING
UNASSIGNED
STAFFING GAPS
CAPACITY PRESSURE
EMERGENCIES
COMMUNICATION DUE
```

This answers: **where does the hospital need attention?**

### B. Full day-control grid

Optimised for exact day organisation:

```text
15-minute display/control rows
×
rooms/resources/operational lanes
```

This answers: **exactly how is the day laid out and where can work move?**

Neither view owns its own hospital state. Both are projections of canonical backend state.

## 4. Interaction hierarchy

### Grid block

Must show the minimum useful operational identity at a glance, such as:

```text
patient / case shorthand
work/procedure
status/readiness
owner or responsible role
```

### Hover / focus preview

Fast, transient summary for orientation. It should not become the only place important risk is visible.

### Click / keyboard open

Open a persistent detail/control panel with structured sections:

```text
NOW
BLOCKER
NEXT ACTION
PEOPLE
READINESS
LOCATION/RESOURCE
COMMUNICATION
EVIDENCE
```

This avoids forcing the user to navigate away for routine operational decisions.

## 5. Density and navigation requirements

LucyWorks must remain usable at referral-hospital scale.

Required behaviours:

- sticky time axis;
- sticky/grouped lane headers;
- horizontal and vertical navigation without losing orientation;
- compact lane widths;
- density/zoom controls where useful;
- department and capability grouping;
- search-to-lane and search-to-case;
- keyboard navigation;
- touch-compatible interactions;
- filtering that never creates a second source of truth;
- fast switch between hospital-wide and department focus.

The board should not become a spacious card dashboard that can only show a handful of cases at once.

## 6. Structured coverage and operational messages

Known operational facts should be first-class objects rather than free text when possible.

Examples:

```text
CoverageRequirement
CoverageAssignment
CoverageGap
OperationalNotice
Escalation
```

A senior-cover gap should be able to derive:

```text
required senior role
- available authorised staff
= coverage shortfall
```

and then link to affected scheduled work.

## 7. Readiness on the board

The board should display backend-computed readiness, not recalculate it independently.

Example:

```text
patient present              yes
consent valid                yes
estimate authority           yes
required clinician           yes
required nurse               yes
room/resource capability     yes
anaesthesia readiness        yes
stock/medication readiness   yes
recovery capacity            no

READY = false
BLOCKER = recovery capacity
```

## 8. Early build acceptance

Do not wait until the end of the project to test the architecture against a realistic board.

An early synthetic hospital dataset should include at least:

- 40+ lanes/rooms/areas;
- 100+ named staff in the operational dataset;
- overlapping scheduled work;
- variable durations and overruns;
- blocked work;
- unassigned work;
- coverage gaps;
- emergency displacement;
- readiness failures;
- communication-due items.

The system should be exercised using the same canonical command/state/evidence path intended for production, not a separate UI mock data engine.

## 9. Product rule

LucyWorks wins only if it is both:

1. **more intelligent and safer than the current operational view**, and
2. **at least as fast and information-dense for experienced hospital staff**.

A cleaner-looking interface that requires more clicks, hides concurrency, or reduces situational awareness is a regression.
