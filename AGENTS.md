# AGENTS.md — LucyWorksOS Agent Instructions

## Product rule

LucyWorksOS is one professional-grade specialist referral-hospital operating system.

Do not treat it as separate apps, a demo, a SaaS launchpad, a chatbot wrapper, a toy intake form, or a loose dashboard.

Canonical names:

- LucyWorksOS = whole hospital operating system
- LucyFlow = intake, triage, routing, handoff
- LucyPulse = pressure, risk, workload, alerts
- LucyRota = rota, staffing, skills, availability, load
- LucyWorksAI = optional AI assistance inside workflow, never source of truth
- LucySafe = safety, ethics, escalation, safeguarding, override layer

Do not rename the system or invent replacement module names.

## Canonical repository topology

There is one active implementation:

```text
apps/web  = canonical staff-facing web application
apps/api  = canonical backend/API, domain logic and persistence layer
```

The root scripts, tests and deployment work must target these canonical directories.

The following top-level directories are legacy migration sources only:

```text
frontend/
backend/
```

Hard rules for legacy directories:

- Do not implement new product work in `frontend/` or `backend/`.
- Do not fix a feature in a legacy directory instead of the canonical implementation.
- Do not add imports, runtime dependencies, scripts or deployment paths from `apps/*` to legacy code.
- Legacy code may be read to identify useful behaviour that has not yet reached the canonical system.
- If useful legacy behaviour is required, migrate/rebuild it inside `apps/web` or `apps/api`, add canonical tests, then leave the legacy copy untouched until retirement/removal is explicitly justified.

## Mandatory reading before coding

At the start of every LucyWorksOS coding session, read the relevant parts of these files before making changes:

1. `PRODUCT_CONTRACT.md`
2. `docs/LUCYWORKS_SYSTEM_CONTRACT.md`
3. `docs/LUCYWORKS_SPECIFICATION_V1.md`
4. `docs/LUCYWORKS_ENGINEERING_CONSTRUCTION_STANDARD.md`
5. `docs/LUCYWORKS_BUILD_PLAN_V1.md`
6. `docs/LUCYWORKS_OPS_DAYFLOW_BASELINE.md`
7. `docs/LUCYWORKS_INTERACTION_SEARCH_SPEC.md`
8. `docs/LUCYWORKS_CONTINUE_HERE.md`
9. `apps/web/lib/day-control-work.ts`
10. `apps/web/lib/day-control-views.ts`
11. `apps/web/components/day-control-grid.tsx`

If the requested package concerns a specific domain, inspect all existing models, routes, services, tests and UI surfaces for that domain before creating new code.

## Source-of-truth rule

LucyWorks has one persisted hospital state.

The generated day-control schedule in:

```text
apps/web/lib/day-control-work.ts
```

is a compatibility/view model during convergence, not the long-term persisted source of truth.

Department views may use:

```text
apps/web/lib/day-control-views.ts
```

but they must progressively consume canonical backend state. Do not build any new module that invents a separate work, patient, schedule, authority, pricing, medicine or evidence model.

## Professional-grade standard

A change is not good enough if it only makes the UI look better or adds a route/model in isolation.

LucyWorksOS must behave like a real referral-hospital operating system.

Minimum professional system properties:

1. **One canonical state**
   - one backend write path
   - one canonical database
   - one operational state model
   - one authority model
   - one evidence/governance spine
   - multiple projections/views, never multiple hospital realities

2. **Real operational entities**
   Visible work must map to canonical concepts such as:
   - Patient / Owner
   - Referral / Episode / Admission / Encounter
   - ProcedureTemplate / ScheduledCase / WorkItem / WorkBlock
   - StaffMember / Shift / Competency / Authorisation
   - Room / Resource / ResourceState
   - Blocker / Dependency / Readiness
   - Estimate / Consent / ClientAuthorisation
   - Medication / Result / Communication
   - Complaint / SafetyFlag / CorrectiveAction
   - EvidenceEvent / Approval / Override / AI verification

3. **Hospital-scale operation**
   The system must account for reception/intake, consults, imaging, theatres, anaesthesia, recovery, wards/ICU, pharmacy, diagnostics, discharge, insurance, owner/referrer communication, rota/staffing, safety/governance and hospital capacity.

4. **Dense time/resource control**
   The operational day must remain usable with 40+ lanes/areas and 100+ staff. Preserve high information density, 15-minute display/control, compact work blocks, sticky orientation and fast search/focus.

5. **Executable procedure/workflow templates**
   Procedure templates generate requirements and dependencies: prep, staff roles/competencies, room/resource capability, anaesthesia where relevant, procedure/diagnostic work, recovery/turnover, result review and communication points.

6. **No decorative actions**
   Every visible operational action must navigate, inspect real state, execute a real backend command, or be disabled with a structured reason.

7. **Clinical-safety posture**
   AI may extract, summarise, classify, retrieve, draft and recommend within policy. Hard rules, canonical state, professional authority and required human verification remain decisive.

## Construction package rule

Build one bounded construction package at a time.

Before changing code state:

```text
package id
problem
requirements satisfied
existing code reused
canonical entities read/changed
commands
permissions/authority
evidence produced
UI/read-model impact
migration/compatibility plan
tests
performance impact
rollback path
out of scope
```

The package is not ready if these are unclear.

A complete vertical slice follows:

```text
user action
→ API/domain command
→ authentication
→ authority/policy
→ current-state/conflict validation
→ canonical mutation
→ EvidenceEvent
→ outbox/realtime consequence where required
→ UI reads the committed backend truth
```

Do not call a feature complete because a model, route, card or screen exists.

## Coding-agent constraints

When acting as a coding agent:

- analyse existing code first;
- reuse/extend correct implementations;
- classify duplicates before replacing them;
- do not perform a broad rewrite unless the construction package explicitly requires it;
- do not create a second source of truth;
- do not perform destructive migration and replacement in the same first step;
- do not auto-commit or auto-push unless explicitly instructed;
- run relevant tests;
- report changed files, tests, assumptions and unresolved risks;
- show/inspect the diff before a package is accepted.

Generated code is held to the same standard as human-written code.

## Build gates

Do not accelerate into broad feature work until these gates are demonstrated.

### Gate A — Core spine

At least one real patient/episode/work action passes:

```text
command → authority → mutation → evidence → UI
```

### Gate B — Hospital-scale read model

A deterministic synthetic hospital day with 40+ lanes and 100+ staff remains usable and navigable.

### Gate C — Authority/readiness

Ineligible staff/resources and blocked work return structured, explainable reasons.

### Gate D — Operational command

At least one move/assign/hold/resolve action changes canonical state and propagates to all relevant views without fake page-local state.

### Gate E — Migration safety

Fresh and representative upgraded databases both migrate/start successfully without relying on production runtime schema patches.

## Current construction order

Unless explicitly reprioritised, work proceeds:

```text
CORE-001     Canonical hospital spine audit/convergence
BASE-001     Deterministic hospital-scale synthetic dataset
GRID-001     Early dense day-control shell
AUTH-001     Workforce/authority/coverage convergence
READY-001    Conflict + readiness engine
OPS-001      Command view + mature day-control interaction
SEARCH-001   Context-aware search and assisted entry
FIN-001      Price/estimate/consent chain
MED-001      Medicines/stock/administration
DIAG-001     Diagnostics/results/review
COMM-001     Owner/referrer/discharge communication
GOV-001      Complaints/safety/corrective action
AI-001       Voice/AI assistance and verification
INT-001      External adapters and reconciliation
PROD-001     Production hardening/deployment
```

Each package must comply with `docs/LUCYWORKS_ENGINEERING_CONSTRUCTION_STANDARD.md` and finish with tests plus an inspectable diff.

## Hard rule

If a change creates another disconnected board, dashboard, fake module, separate patient/workflow model, duplicate persistent state or hidden operational truth, it is wrong.

LucyWorksOS must remain one connected hospital operating model with multiple specialised views and actions.
