# LucyWorks Continue Here

Use this at the start of every LucyWorks build session.

## Core rule

LucyWorks OS is one connected hospital operating model with many role/department views. Do not create disconnected pages, boards, databases or workflows.

## Canonical codebase

```text
apps/web = active staff-facing application
apps/api = active backend, persistence, auth, governance and operational services
```

Top-level `frontend/` and `backend/` are legacy history and are not build targets.

## Mandatory reading order

1. `PRODUCT_CONTRACT.md`
2. `AGENTS.md`
3. `docs/LUCYWORKS_SYSTEM_CONTRACT.md`
4. `docs/LUCYWORKS_CONTINUE_HERE.md`
5. `docs/CANONICAL_CONSOLIDATION_AUDIT.md`
6. the canonical files relevant to the task under `apps/web` and `apps/api`

For day-control work also read:

```text
apps/web/lib/day-control-work.ts
apps/web/lib/day-control-views.ts
apps/web/components/day-control-grid.tsx
```

## Source-of-truth direction

The operating model is:

```text
patients / episodes
+ procedure templates and planned work
+ staff / skills / shifts
+ rooms / resources / capacity
+ blockers / decisions / handovers
+ 15-minute time control
= connected scheduled operational work
```

Where canonical backend persistence exists, `apps/api` is the authority for persisted hospital state. Frontend-generated day-control data is a compatibility/prototype layer that must converge on the backend; it must not become a second persistent hospital reality.

All views must consume the same canonical operating state directly or through approved view adapters.

## Every operational row/action must answer

```text
who
what
where
when
how
status
blocker
next action
patient / episode
staff / resource ownership
evidence / audit consequence
```

## Connected-system acceptance

A change is only complete when it preserves the operational chain:

```text
hospital
→ area / room
→ patient / episode
→ work / procedure
→ staff / resource
→ state / action
→ evidence / audit
```

Examples:

- moving a procedure must affect the shared schedule/resource state, not only one page;
- assigning staff must update the canonical assignment and be visible to dependent views;
- resolving a blocker must change shared state and produce the required evidence/audit;
- an emergency override must be authorised, explicit and traceable;
- department views may filter the hospital model but may not invent their own work model.

## Current consolidation priority

### 1. Keep one implementation

All active work belongs in:

```text
apps/web
apps/api
```

Do not restore or recreate top-level `frontend/` or `backend/`.

### 2. Finish source-of-truth convergence

Identify any remaining UI surface that still depends on hard-coded/generated-only state when canonical backend state exists. Move it to the shared API/domain model without breaking the 15-minute operational view.

### 3. Strengthen live connected actions

Actions such as:

```text
assign
hold
block
resolve
handover
review
complete
move / reschedule
emergency override
```

must update shared canonical state, respect permissions and produce audit/evidence.

### 4. Strengthen conflict and capacity rules

Detect and expose at minimum:

```text
room/resource clash
staff overlap
missing required skill/role
late update
admin/consent blocker
thin cover
missed/protected break
work overrun
recovery/turnover dependency
emergency displacement impact
```

### 5. Complete connected domain workflows

Clinical/operational areas such as intake, theatre, imaging, wards/ICU, pharmacy, discharge, owner communications, rota and safety/governance must remain domain-specific while sharing the same patient/episode/work/staff/resource/evidence spine.

### 6. Add AI only inside the operating boundary

AI may extract, classify, summarise, retrieve, draft and explain. It must not become the source of truth or bypass permissions, hard safety rules, human authority, validation or audit.

## Validation

Before accepting a change:

```bash
npm run check
```

Also review:

```bash
git diff
```

Staff-facing changes must retain the functional and hospital-scale acceptance requirements in `PRODUCT_CONTRACT.md`.

## Prompt for a coding agent

```text
Continue LucyWorksOS from PRODUCT_CONTRACT.md, AGENTS.md, docs/LUCYWORKS_SYSTEM_CONTRACT.md and docs/LUCYWORKS_CONTINUE_HERE.md. Work only in the canonical apps/web + apps/api system unless the task explicitly concerns current support files. Preserve one connected hospital operating model. Where backend persistence exists, use it as the persisted source of truth; do not create parallel page-level state or a second schedule. Analyse the relevant existing code first, make the minimum scoped change, run the relevant tests and the canonical check, then report the exact diff and any unresolved risks.
```
