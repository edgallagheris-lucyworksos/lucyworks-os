# LucyWorksOS Engineering Construction Standard

This document defines **how LucyWorks is built**. Product requirements come from the LucyWorks specifications; this standard prevents those requirements being implemented as another collection of partial, duplicated or fragile features.

## 1. Construction rule

LucyWorks is built as a sequence of bounded **vertical construction packages** over one canonical hospital state.

Every package must either:

- strengthen an existing canonical domain;
- migrate useful legacy behaviour into a canonical domain; or
- add a genuinely missing capability required by the specification.

A package must not create a second hospital state, second patient/workflow model, duplicate board, duplicate authority system or feature-local persistence that can disagree with the canonical backend.

## 2. Package contract

Before code is changed, each package must state:

```text
package id
problem being solved
specification requirements satisfied
existing code being reused
canonical entities read
canonical entities changed
commands introduced/changed
authority rules
evidence generated
read models/UI affected
migration/compatibility plan
test plan
performance impact
rollback path
out-of-scope items
```

If these cannot be stated clearly, the package is not ready to build.

## 3. Build small, integrate completely

Prefer the smallest complete vertical slice over a wide partial implementation.

A complete slice follows:

```text
real user action
→ API/command
→ authentication
→ authority/policy
→ current-state and conflict validation
→ canonical mutation
→ EvidenceEvent
→ outbox/domain event where required
→ read-model/realtime update
→ staff-facing UI reflects backend truth
```

Do not call a feature complete because a model, route or screen exists in isolation.

## 4. Canonical ownership and dependency boundaries

Each domain owns its core rules and write path.

Target domains include:

```text
patients / episodes
operations / scheduling
workforce / authority
resources / readiness
commercial / consent
medicines
diagnostics
communications
safety / complaints
evidence
AI
integrations
```

Rules:

1. UI components do not implement independent hospital business rules.
2. API routers translate HTTP to domain commands/queries; they do not become the domain layer.
3. Cross-domain writes occur through explicit services/commands rather than direct table manipulation from unrelated modules.
4. Shared primitives such as identity, time, evidence, refs, idempotency and errors live in common/core infrastructure.
5. Numbered patch modules are transitional. New capability must not extend the patch-chain pattern unless needed only as a short-lived compatibility adapter.

## 5. Database migration discipline

Schema work must be reversible or have a documented recovery path.

Use staged migrations:

```text
1. add new schema compatibly
2. deploy/read old + new where required
3. backfill deterministically
4. switch canonical writes
5. switch canonical reads
6. prove parity
7. retire compatibility code in a later package
```

Never combine destructive schema removal with the first introduction of its replacement.

Production PostgreSQL uses Alembic. Runtime schema mutation and SQLite compatibility maps are development-transition aids only.

For data backfills:

- make them idempotent;
- log counts/failures;
- preserve source identifiers/provenance;
- provide a dry-run or validation mode where practical;
- test on realistic synthetic data first.

## 6. Safe replacement of existing LucyWorks code

Existing code is classified:

```text
KEEP
EXTEND
MERGE
MIGRATE
RETIRE
REMOVE
MISSING
```

Removal is the final step, not the first.

A legacy path may be removed only when:

- canonical replacement is working;
- dependent callers have migrated;
- functional tests prove the replacement;
- data migration/parity is verified;
- no current route/UI/integration still depends on it;
- rollback risk is understood.

## 7. Realistic deterministic test hospital

LucyWorks development must include a deterministic synthetic referral-hospital dataset, not only toy fixtures.

Minimum baseline:

- 40+ rooms/areas/lanes;
- 100+ named staff;
- multiple professional roles and competencies;
- overlapping work;
- admissions and referrals;
- variable procedure durations;
- overruns;
- emergencies and displacement;
- missing consent/financial authority;
- stock/readiness blockers;
- recovery/turnover constraints;
- staffing/coverage gaps;
- communication-due work;
- complaints/governance objects;
- enough historical evidence to exercise timelines/audit.

Seed generation must be reproducible so performance and regression results can be compared across builds.

## 8. Test gates

Each package runs only the relevant layers during development, but cannot be accepted without the required full gates.

### Domain tests

Test state transitions, policy, authority, conflicts, versioning, idempotency and evidence consequences.

### API tests

Test authentication, permission denial, validation, concurrency/retry behaviour and stable response contracts.

### Browser tests

Test real navigation and state change, not screenshots alone.

### Architecture tests

Add automated checks where practical for:

- forbidden legacy imports;
- duplicate canonical entity ownership;
- frontend direct persistence/fake state patterns;
- missing EvidenceEvent for required command classes;
- unregistered routers or dead operational controls.

### Migration tests

A fresh database and an upgraded representative database must both start successfully.

## 9. Definition of done

A construction package is DONE only when:

```text
spec requirement mapped
existing code classification recorded
canonical ownership clear
real state change works end-to-end
authority enforced server-side where relevant
EvidenceEvent produced where required
failure/blocker reason is structured
UI reads backend truth
no decorative/dead control introduced
tests pass or pre-existing failures are explicitly documented
realistic dataset exercised
git diff reviewed
migration/rollback understood
documentation updated
```

“Screen exists”, “API returns 200” and “AI says complete” are not definitions of done.

## 10. Performance budgets

The hospital operating surface must be measured continuously against the realistic baseline.

Initial engineering targets on the local development laptop are **budgets to test and refine**, not clinical SLAs:

- high-density board remains interactive with 40+ lanes and 100+ active staff;
- search suggestions should normally appear within roughly 150 ms once local data/indexes are warm;
- ordinary local command responses should normally complete within roughly 500 ms when no external integration is required;
- grid pan/scroll/selection must remain visually responsive;
- board data endpoints must avoid N+1 query behaviour and unbounded payload growth;
- large read models should use pagination/windowing/virtualisation or incremental loading where appropriate.

Record benchmark dataset size, machine and build so regressions are comparable.

Do not optimise by hiding required operational information or by creating stale secondary state.

## 11. Reliability and concurrency

Consequential commands must define transaction boundaries.

Use where relevant:

```text
entity revision/version
idempotency key
request id
correlation id
causation id
unique constraints
optimistic concurrency
transactional outbox
```

A retry must not duplicate medication administrations, consent records, financial approvals, assignments or EvidenceEvents.

Lost-update conflicts must return a structured response that tells the UI to refresh/reconcile rather than silently overwrite newer hospital state.

## 12. Realtime behaviour

Realtime updates are delivery, not authority.

Canonical transaction commits first. Then websocket/SSE/read-model propagation may notify other staff surfaces.

If realtime delivery fails:

- canonical state remains correct;
- clients can refresh/reconcile;
- queued/outbox work remains visible/retryable;
- the UI must not claim success for an uncommitted action.

## 13. Observability

Every consequential command should be traceable through:

```text
request/correlation id
actor
command type
canonical entity refs
outcome
latency
EvidenceEvent ref
outbox/integration consequence
error code/reason where failed
```

Operational health should expose at minimum:

- API/database health;
- failed commands;
- outbox/integration backlog;
- dead-letter/retry counts;
- realtime delivery health;
- migration/schema version;
- background worker health where used.

Logs must minimise sensitive patient/client data.

## 14. Security and privacy gates

For every new staff-facing capability ask:

```text
who can see it?
who can change it?
what professional authority is required?
what minimum patient/client data must be displayed?
what is logged?
what requires evidence/audit?
```

Security rules are server-side.

Do not commit secrets, tokens, real patient/client data or production credentials into source control or synthetic fixtures.

Use role/context-aware responses so the API itself does not overexpose information that the frontend merely hides.

## 15. Feature flags and compatibility

Use flags/adapters when a risky replacement must coexist temporarily with existing behaviour.

Flags must have:

- owner/purpose;
- default state;
- removal condition;
- tests for both paths while both remain supported.

A compatibility adapter must not become a permanent second implementation.

## 16. Search and suggestions

Search is infrastructure shared by domains, not a separate truth database.

Indexes/projections may accelerate search, but selection must resolve back to canonical refs and consequential actions must revalidate current authority/readiness on the server.

Never trust a suggestion merely because it was valid when displayed.

## 17. AI-assisted construction

A local or cloud coding agent is a tool, not the architect or source of truth.

Before editing it must read the relevant contracts/specifications and inspect existing code.

Coding-agent constraints:

```text
one construction package at a time
no parallel patient/workflow/database
no broad rewrite unless package explicitly authorises it
no automatic destructive migration
no automatic commit/push
run relevant tests
show changed files/diff
report assumptions and unresolved conflicts
```

Generated code is accepted only by the same tests, architecture rules and review used for human-written code.

## 18. Git and change control

Prefer one branch/PR per coherent construction package or tightly related package group.

Each change should make it possible to answer:

- what hospital capability changed;
- what canonical state changed;
- what was migrated/retired;
- what tests prove it;
- how to roll it back.

Avoid giant commits that mix architecture migration, UI redesign, unrelated cleanup and new features.

## 19. Build gates before deeper expansion

Before broad feature expansion, LucyWorks must prove:

### Gate A — Core spine

One patient/episode/work action passes command → authority → mutation → evidence → UI.

### Gate B — Hospital-scale read model

40+ lanes / 100+ staff are usable with realistic overlapping work.

### Gate C — Authority/readiness

Ineligible staff/resources and blocked work return structured, explainable reasons.

### Gate D — Operational command

At least one move/assign/hold/resolve action changes canonical state and propagates to all relevant views.

### Gate E — Migration safety

Canonical migrations work from fresh and representative existing databases without runtime patch dependence.

Only after these gates are demonstrated should the build accelerate into the full commercial, medicines, diagnostics, communication, governance, AI and integration programme.
