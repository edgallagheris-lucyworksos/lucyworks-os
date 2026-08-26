# LucyWorksOS Build Plan v1

This plan converts `LUCYWORKS_SPECIFICATION_V1.md` into an implementation programme. The existing repository is treated as reusable material, not product authority.

The build must also satisfy `LUCYWORKS_OPS_DAYFLOW_BASELINE.md`. LucyWorks must improve the current hospital day-flow operation without losing its information density, speed or ability to show many concurrent rooms/resources at once.

## Construction principles

1. Build from canonical hospital state outward, not page-by-page inward.
2. Preserve and extend good existing code; do not rewrite working domains without a reason.
3. Deliver vertical slices that run end-to-end through backend state, authority, evidence and UI.
4. Test a realistic high-density operating board early so architecture and UX cannot drift apart.
5. Use one persisted hospital state. Command view, day grid and department views are projections of that state.
6. Important operational facts must become structured data where possible; do not leave staffing gaps, readiness or blockers only in free-text notes.
7. Do not optimise for a visually spacious SaaS dashboard. Referral-hospital situational awareness requires density.

## Status labels

Every existing feature is classified as:

- KEEP — conforms and is usable as-is
- EXTEND — correct direction but incomplete
- MERGE — duplicate good work should converge into one canonical implementation
- MIGRATE — useful behaviour exists in the wrong architectural location
- RETIRE — retain temporarily for compatibility while canonical replacement lands
- REMOVE — delete only after replacement and tests prove it is no longer required
- MISSING — not yet implemented

## Phase 0 — Audit and baseline

1. Inventory canonical models, routes, services and frontend surfaces.
2. Map each item to the v1 specification domains.
3. Identify duplicate state models, numbered patch chains and parallel workflows.
4. Record KEEP / EXTEND / MERGE / MIGRATE / RETIRE / REMOVE / MISSING.
5. Run the existing canonical checks before structural work.
6. Capture a baseline functional path through referral → episode → scheduled work → evidence.
7. Capture the current operational day-flow behaviours that LucyWorks must beat, using `LUCYWORKS_OPS_DAYFLOW_BASELINE.md`.
8. Build a realistic synthetic hospital dataset for repeatable development/testing.

Synthetic baseline must include at least:
- 40+ lanes/rooms/areas;
- 100+ named staff;
- overlapping work;
- variable durations and overruns;
- blockers;
- unassigned work;
- staffing/coverage gaps;
- emergency displacement;
- readiness failures;
- communication-due work.

Exit criteria:
- no destructive cleanup yet;
- complete architecture gap matrix;
- known baseline tests and current failures;
- realistic operational dataset available through canonical APIs or compatibility adapters;
- one agreed first migration package.

## Phase 1 — Core hospital spine

Build or consolidate the canonical spine:

```text
Patient
→ Referral
→ Episode
→ WorkItem / ScheduledCase
→ Assignment / Resource
→ Readiness / Blocker
→ Domain Command
→ EvidenceEvent
```

Required foundations:
- stable opaque refs;
- canonical versions/revisions;
- shared command result/error model;
- authority-policy hook;
- evidence hook;
- idempotency/correlation IDs;
- exact timestamps;
- no page-local persistent hospital truth.

Exit criteria:
- at least one real patient/episode/work flow uses the canonical command path end-to-end;
- consequential changes generate EvidenceEvent;
- frontend reads resulting backend truth.

## Phase 1B — Early operational shell

Before waiting for every domain to be complete, prove that the core architecture can drive a hospital-scale operational surface.

Build a thin operational shell using canonical/compatibility data with:

- sticky 15-minute time axis;
- compact room/resource lanes;
- grouped/sticky headers;
- patient/work identity;
- basic state/readiness marker;
- blocker/exception marker;
- owner/responsible staff;
- quick preview on hover/focus;
- persistent detail panel on click/keyboard open;
- search-to-case and search-to-lane;
- hospital-wide and department focus modes.

This shell is not the finished UI. It is an architectural proving ground.

Exit criteria:
- synthetic 40+ lane dataset remains navigable;
- one canonical backend state change is reflected in the grid without page-local fake state;
- board density is at least comparable to the current operational baseline;
- important blockers are visible without individually opening every appointment.

## Phase 2 — Authority and workforce

Consolidate:
- StaffMember;
- registration/status;
- competency;
- local authorisation;
- supervision;
- shifts/breaks;
- assignments;
- coverage requirements;
- coverage assignments/gaps.

Implement `effective authority` as a reusable backend policy service.

Structured staffing/coverage facts must replace known free-text-only operational messages where possible.

Exit criteria:
- assignment and regulated actions are server-side authorised;
- unavailable/ineligible staff return structured reasons for UI suggestions;
- expired competency/authorisation is detectable;
- senior/critical cover gaps can identify affected work and escalation requirements.

## Phase 3 — Resource, conflict and readiness engine

Unify resource, staffing and workflow prerequisite checks.

Readiness must include, where applicable:
- patient presence/prep;
- consent;
- financial authority;
- required staff/skills;
- room/resource capability;
- medicines/stock;
- anaesthesia;
- recovery/turnover capacity;
- results/decision dependencies.

Exit criteria:
- one backend readiness result feeds command view, day grid and department views;
- conflicts include severity, cause and resolution paths;
- board does not independently invent readiness state;
- blocked work exposes a clear reason and next resolution action.

## Phase 4 — Operational command and day-control views

Develop the two complementary operating surfaces defined in `LUCYWORKS_OPS_DAYFLOW_BASELINE.md`.

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

### B. Full day-control grid

Optimised for precise day organisation:

```text
15-minute display/control rows
×
rooms/resources/operational lanes
```

Both views read the same canonical state.

Core interaction hierarchy:

```text
grid block
→ quick hover/focus preview
→ persistent detail/control panel
→ explicit domain command
→ canonical state change
→ EvidenceEvent
→ realtime/read-model update
```

Exit criteria:
- 40+ room / 100+ staff scale remains usable;
- department views are filters/projections, not separate schedules;
- important status does not depend on colour alone;
- cryptic codes have discoverable human-readable labels;
- detailed client/clinical information is role-aware and not indiscriminately exposed;
- real actions change shared state and dependent views reflect them.

## Phase 5 — Search, assisted entry and command palette

Implement `LUCYWORKS_INTERACTION_SEARCH_SPEC.md`.

Core indexes/suggestion providers:
- patient / owner / episode;
- staff;
- room/resource;
- procedure/service;
- medicine/formulary;
- task/work;
- estimate/invoice;
- complaint/governance object.

Ranking considers:
- text relevance;
- current workflow context;
- site/department;
- shift/availability;
- competency/authority;
- resource state;
- recency/frequency where safe.

Exit criteria:
- staff can search/select rather than repeatedly type known data;
- blocked choices explain why;
- search can jump directly to a case/lane/resource on the day grid;
- server revalidates all consequential selections;
- core search works locally/offline.

## Phase 6 — Commercial / estimate / consent chain

Implement:

```text
ClinicalProcedure
→ CommercialService
→ ServiceVariant
→ PriceVersion
→ EstimateVersion
→ ClientAuthorisation / Consent
→ Charge / Invoice
→ Variance
```

Exit criteria:
- historic estimates remain anchored to price versions;
- revised estimates supersede rather than overwrite;
- owner authority and material variation are evidenced;
- publishable price data is separate from internal economics;
- financial/consent readiness feeds the operational board directly.

## Phase 7 — Medicines, diagnostics and patient timeline

Consolidate medicines governance, stock, diagnostic orders/results and review workflow onto the same episode/work/evidence spine.

Exit criteria:
- medication events and critical-result workflows are canonical and evidenced;
- medicine/formulary search feeds assisted entry;
- stock/readiness affects work when relevant;
- patient timeline is a projection of the same operational state and evidence.

## Phase 8 — Communications, discharge, insurance and complaints

Connect owner/referrer communications, discharge, insurance and complaints to canonical patient/episode/commercial/evidence objects.

Exit criteria:
- communication requirements can be generated from state;
- communication-due work appears in command/day views;
- complaint links reconstruct the relevant episode/estimate/invoice/communications;
- corrective actions have owner, due date and effectiveness review.

## Phase 9 — AI / voice assistance

AI remains subordinate to canonical state and authority.

Implement/rework:
- voice → transcript → structured proposed work;
- draft summaries/communications;
- AI output provenance;
- verification/amend/reject states;
- deterministic tools for calculations/conflicts/authority.

Exit criteria:
- original AI output is retained;
- verified final record is separate;
- no autonomous clinical treatment decision or complaint adjudication;
- local Ollama path can be used for supported non-cloud development/assistance.

## Phase 10 — Integrations and production hardening

Consolidate adapters for PMS/PACS/lab/pharmacy/insurance/HR/communications using canonical refs, inbox/outbox, idempotency and reconciliation.

Complete:
- PostgreSQL/Alembic migration history;
- security/permissions review;
- observability;
- backups/recovery;
- realtime propagation;
- deployment configuration.

## Construction package order

The preferred package sequence is:

```text
CORE-001     Canonical hospital spine audit/convergence
BASE-001     Realistic hospital-scale synthetic dataset
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

Each package must preserve existing working behaviour through adapters where necessary and must finish with tests plus an inspectable diff.

## Local build workflow

Normal construction on the laptop:

```text
specification/baseline
→ inspect existing code
→ implement one bounded vertical slice
→ domain/API/browser tests
→ run local system against realistic dataset
→ compare against operational baseline
→ inspect git diff
→ commit
→ push/PR when useful
```

Normal offline startup must not install packages or perform network calls.

## First implementation package

First package: `CORE-001 Canonical hospital spine audit and convergence`.

Deliverables:
1. Map current Patient/Referral/Episode/Work/Schedule/Evidence models and routes.
2. Identify duplicates and generated-only state.
3. Define canonical refs and relationships without breaking existing endpoints.
4. Route one real operational state change through command → authority hook → mutation → EvidenceEvent.
5. Add tests proving the state and evidence stay connected.
6. Leave compatibility adapters where existing UI still depends on them.

Immediately after CORE-001, build `BASE-001` and `GRID-001` so the architecture is tested against a realistic dense hospital day before deeper domain expansion.
