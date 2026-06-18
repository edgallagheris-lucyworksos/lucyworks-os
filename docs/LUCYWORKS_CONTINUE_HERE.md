# LucyWorks Continue Here

Use this at the start of every LucyWorks build session.

## Core rule

LucyWorks OS is one operating model with many views. Do not create disconnected pages.

The base model is:

```text
templates
scheduled cases
resources
staff cover
15-minute slots
scheduled work blocks
```

## Mandatory reading order

1. `docs/LUCYWORKS_SYSTEM_CONTRACT.md`
2. `docs/LUCYWORKS_CONTINUE_HERE.md`
3. `apps/web/lib/day-control-work.ts`
4. `apps/web/lib/day-control-views.ts`
5. `apps/web/components/day-control-grid.tsx`

## Current source of truth

Primary file:

```text
apps/web/lib/day-control-work.ts
```

View adapter:

```text
apps/web/lib/day-control-views.ts
```

All screens must use these until backend storage replaces them.

## What the full system must show

```text
arrivals
consults
owner/contact updates
insurance/admin blockers
reception/admin queue
planned work
rooms/resources
staff assignments
staff skills
breaks/welfare
handover
records/audit
next actions
```

Every row must answer:

```text
who
what
where
when
how
blocker
next action
```

## Current committed state

```text
/hospital-board uses DayControlGrid
DayControlGrid uses generated 15-minute blocks
Templates generate prep/main/recovery/update/check rows
Action drawer includes generated contact update
/my-shift includes timed work and queue work
/rota includes day-grid pressure and rota grid
```

## Next build sequence

### 1. Convert area pages

Convert these to `day-control-views.ts`:

```text
/theatre
/imaging
/icu-wards
/lucy-pharm
/lucy-intake
/flow
```

### 2. Add live state updates

Drawer actions must update the selected scheduled block:

```text
assign
hold
block
resolve
handover
review
complete
```

### 3. Add persistence

Add storage for scheduled blocks and actions:

```text
list blocks
create block
update block
record action
```

### 4. Add conflict detection

Detect:

```text
resource clash
missing staff role
late update
admin blocker
thin cover
missed break
work running over
```

### 5. Improve overview layout

The main board needs:

```text
command strip
now / next / blocked / overload summaries
generated schedule lanes
resource panel
staff pressure panel
update-needed panel
```

## New chat prompt

```text
Continue LucyWorks OS from docs/LUCYWORKS_SYSTEM_CONTRACT.md and docs/LUCYWORKS_CONTINUE_HERE.md. Use the generated 15-minute day-control schedule as the single source of truth. Do not build disconnected pages. Convert the next page/module to use day-control-work.ts or day-control-views.ts, then add persistence/actions.
```
