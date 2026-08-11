# LucyWorks hospital operating model

LucyWorks is one hospital operating system, not a collection of versioned feature screens.

## Operating objective

Every operational change must improve or protect four linked outcomes:

1. **Patient** — safe, timely, clinically appropriate care with explicit blockers and accountable ownership.
2. **Client** — clear authority, estimates, updates, choices and complaint handling with evidence of what was communicated.
3. **Staff** — one source of truth, clear ownership, realistic capacity, fewer duplicate updates and fewer hidden tasks.
4. **Commercial** — use expensive clinical capacity well, capture legitimate charges accurately, reduce rework/leakage and make margin pressure visible without overriding clinical safety or informed client choice.

The order matters: commercial optimisation is constrained by patient safety, lawful client treatment and safe staffing. It is not a separate objective that may bypass them.

## Canonical operating loop

Referral -> triage -> accepted episode -> consent/authority -> estimate -> scheduled care -> clinical execution -> client updates -> charge reconciliation -> discharge/closure -> outcome/evidence review.

The canonical episode is the common key. Scheduling, clinical records, client communication, estimates, charges, complaints, prescriptions, AI provenance and closure evidence must point back to the same episode/patient identity.

## Command principles

- **One live board per hospital/site.** Different views may exist, but they are projections of the same state.
- **One accountable owner for every active item.** Unassigned work is an exception state, never a normal state.
- **One next action.** Every active episode/work item must expose what happens next and who owns it.
- **No silent safety bypass.** Conflicts, missing authority, missing evidence and stale writes block or explicitly escalate.
- **Human clinical authority remains human.** AI may draft, extract and propose; accountable clinicians confirm clinical records and decisions.
- **Client money is part of care flow.** Estimate changes, authority and actual charges are reconciled against the episode rather than handled as detached admin.
- **Commercial metrics must be explainable.** Capacity utilisation, charge capture, estimate variance, delay/rework and complaint signals may be optimised. LucyWorks must not invent a margin figure when cost data is absent.
- **Internal implementation versions are not product language.** Normal staff surfaces should say what a thing does, not which historical development version created it.

## Decision hierarchy

When objectives conflict, LucyWorks should resolve them in this order:

1. immediate patient safety and welfare;
2. legal/professional/clinical authority;
3. client informed choice and financial clarity;
4. safe staff workload and operational continuity;
5. throughput, utilisation, revenue capture and margin optimisation.

This does not make commercial performance optional. It makes it sustainable: fewer cancelled procedures, fewer duplicated tasks, fewer missed charges, fewer avoidable complaints, clearer estimates and better use of theatres/imaging/staff all improve financial performance while supporting care.

## Board-level signals

A hospital command surface should distinguish rather than blend:

- **clinical risk:** red/amber conflicts, blocked care, overdue safety actions;
- **flow:** active episodes with/without a scheduled next block, delay propagation and bottlenecks;
- **staff:** named ownership, unassigned work, fatigue/pressure and resource collisions;
- **client:** estimate/authority/update/complaint blockers;
- **commercial:** utilised clinical minutes, idle/blocked capacity, recorded charges, estimate variance and identifiable leakage/rework.

A green commercial signal never cancels a red clinical or authority signal.

## Definition of system-ready

A normal receptionist, nurse, clinician, coordinator or manager must be able to move a real patient through their permitted part of the journey without knowing API paths, database identifiers or historical LucyWorks version numbers. Every material state change must be attributable, reviewable and recoverable.