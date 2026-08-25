# LucyWorksOS Build Plan v1

This plan converts `LUCYWORKS_SPECIFICATION_V1.md` into an implementation programme. The existing repository is treated as reusable material, not product authority.

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

Exit criteria:
- no destructive cleanup yet;
- complete architecture gap matrix;
- known baseline tests and current failures;
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

## Phase 2 — Authority and workforce

Consolidate:
- StaffMember;
- registration/status;
- competency;
- local authorisation;
- supervision;
- shifts/breaks;
- assignments.

Implement `effective authority` as a reusable backend policy service.

Exit criteria:
- assignment and regulated actions are server-side authorised;
- unavailable/ineligible staff return structured reasons for UI suggestions;
- expired competency/authorisation is detectable.

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
- one backend readiness result feeds board and department views;
- conflicts include severity, cause and resolution paths;
- board does not independently invent readiness state.

## Phase 4 — Commercial / estimate / consent chain

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
- publishable price data is separate from internal economics.

## Phase 5 — Master hospital command view

Replace generated-only assumptions progressively with canonical backend state.

The view must expose:
- now / next;
- active work;
- blockers/exceptions;
- owner and supporting staff;
- place/resource;
- readiness;
- overruns;
- workload/capacity pressure;
- client/referrer updates;
- evidence/authority consequence.

Department views remain projections of the same state.

Exit criteria:
- 40+ room / 100+ staff scale acceptance remains usable;
- real actions change shared state;
- dependent views reflect changes.

## Phase 6 — Search, assisted entry and command palette

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
- server revalidates all consequential selections;
- core search works locally/offline.

## Phase 7 — Medicines, diagnostics and patient timeline

Consolidate medicines governance, stock, diagnostic orders/results and review workflow onto the same episode/work/evidence spine.

Exit criteria:
- medication events and critical-result workflows are canonical and evidenced;
- patient timeline is a projection of the same operational state and evidence.

## Phase 8 — Communications, discharge, insurance and complaints

Connect owner/referrer communications, discharge, insurance and complaints to canonical patient/episode/commercial/evidence objects.

Exit criteria:
- communication requirements can be generated from state;
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

## Local build workflow

Normal construction on the laptop:

```text
specification
→ inspect existing code
→ implement one bounded package
→ domain/API/browser tests
→ run local system
→ inspect git diff
→ commit
→ push/PR when useful
```

Normal offline startup must not install packages or perform network calls.

## First implementation package

Do not begin with another UI redesign.

First package: `CORE-001 Canonical hospital spine audit and convergence`.

Deliverables:
1. Map current Patient/Referral/Episode/Work/Schedule/Evidence models and routes.
2. Identify duplicates and generated-only state.
3. Define canonical refs and relationships without breaking existing endpoints.
4. Route one real operational state change through command → authority hook → mutation → EvidenceEvent.
5. Add tests proving the state and evidence stay connected.
6. Leave compatibility adapters where existing UI still depends on them.

Only after CORE-001 is stable should the next package be selected from authority/readiness/commercial based on the audit findings.
