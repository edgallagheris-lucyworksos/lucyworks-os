# LucyWorks System Contract

This file is the build contract for LucyWorks OS. Future work must follow this contract before adding pages, components, routes or features.

## Product target

LucyWorks OS is a hospital operating system. It must show the day in one place, reduce typing, expose blockers early, protect staff capacity, and turn updates into structured work.

## Non-negotiable architecture

### 1. One source of truth

The system must not be built as separate disconnected pages.

The single operating source is the generated schedule:

```text
procedure templates
+ scheduled cases
+ staff capacity
+ resource capacity
+ 15-minute slots
= scheduled work blocks
```

Every view must be a filtered or summarised view of the same schedule source.

### 2. Fifteen-minute time grid

The base unit is a 15-minute slot.

Every operational item must have:

```text
time
lane
subject
what
who
where
how
status
blocker
next action
route
```

### 3. Procedure templates generate work

A procedure is not just a label. It must generate a chain of work:

```text
prep
room/resource use
staff assignment
procedure slot
recovery or handover
client/contact update
decision check
```

Procedure templates must include expected durations so the board can calculate work automatically.

### 4. Every screen is a view of the same schedule

The following screens must not invent their own disconnected work model:

```text
/hospital-board
/my-shift
/rota
/theatre
/imaging
/icu-wards
/lucy-pharm
/lucy-intake
/flow
```

They must consume the generated schedule, either directly or through approved view adapters.

### 5. The board must be an overview, not a toy dashboard

The hospital overview must show:

```text
Now
Next
Blocked
15-minute grid
procedure-generated blocks
staff/resource pressure
client/contact update needs
```

It must be compact, professional and usable all day.

### 6. Drawer actions must update the same work block

Clicking a block opens the action drawer.

Actions must operate on the selected scheduled work block:

```text
assign
hold
block
resolve
handover
request review
create update
complete
```

Temporary local persistence is acceptable during prototype work, but the target is backend persistence and audit.

### 7. Contact updates are generated from facts

Staff should not write long updates manually.

The system must generate short updates from:

```text
subject
current stage
blocker
next action
owner
expected update point
```

Staff review and send/copy/save the generated text.

### 8. Voice capture becomes structured work

Voice input must not become a dead note.

It must produce or update a scheduled work block:

```text
speech
→ transcript
→ blocker
→ owner
→ next action
→ lane
→ time slot
→ audit
```

### 9. Staff welfare is operational, not decorative

The rota must expose:

```text
missed breaks
overload
thin cover
unsafe reassignment
role pressure
available support
```

Staff welfare must sit on the same time grid as clinical/operational work.

### 10. No new page without a source-of-truth check

Before adding any page or module, check:

```text
Does this use the generated schedule source?
Does this update the same block model?
Does this expose who/what/where/how/blocker/next?
Does this reduce typing or reveal risk?
```

If not, do not build it.

## Current source files

Primary model:

```text
apps/web/lib/day-control-work.ts
```

View adapter:

```text
apps/web/lib/day-control-views.ts
```

Main overview:

```text
apps/web/components/day-control-grid.tsx
apps/web/app/hospital-board/page.tsx
```

Shared action drawer:

```text
apps/web/components/queue-detail-drawer.tsx
```

Generated update component:

```text
apps/web/components/contact-update-draft.tsx
```

## Build order from here

1. Make department pages use `day-control-views.ts`.
2. Add local state updates for scheduled work blocks.
3. Add backend persistence for scheduled work blocks.
4. Add audit events for every action.
5. Add procedure/resource/staff capacity conflict detection.
6. Add voice-to-work capture.
7. Add patient/subject timeline view.
8. Add drag/move/reschedule with dependent block recalculation.

## Hard rule

If a feature creates another disconnected board, it is wrong.

LucyWorks OS must remain one generated hospital operating model with multiple filtered views.
