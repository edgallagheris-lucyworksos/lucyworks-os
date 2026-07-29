# LucyWorks v26 — Operational Convergence and Real Hospital Context

## Purpose

v26 removes the assumption that a verified staff identity is sufficient authority for every hospital record. Each governed action is now bound to an authorised organisation, site and premises, and duplicate legacy write routes are converged into one canonical command and evidence model.

The operating rule is:

> Verified person + authorised role + authorised hospital context + named human decision + immutable evidence.

LucyWorks may detect, hold, alert, assign, restrict, reconcile, route and evidence. It does not diagnose, prescribe, alter a dose, administer medication, complete consent, acknowledge a diagnostic result, admit, discharge or decide a clinical phase autonomously.

## Weaknesses identified

### 1. Verified identity without verified location

Authentication established who the user was and their role, but organisation, site and premises were not part of the active authority. Several records could therefore fall back to `default-premises`, and a multi-site user had no explicit, versioned site-selection state.

**v26 control:** an active operating context contains organisation, site and premises. Site access comes from an active membership or configured identity claim. Switching is versioned, evidenced and rejected when stale. Writes naming another site or `default-premises` are rejected.

### 2. Duplicate write paths

Patient blockers, accountable handovers and critical results were strengthened by v25 bridge routes, but the repository still presented multiple conceptual command surfaces. Consent, estimate and discharge controls were also split across modules.

**v26 control:** one `CanonicalCommandV26` model records command type, active context, source route, source record, authenticated actor, safety record, outcome and idempotency key. Existing patient-care and control-plane URLs are registered through v26 first so current clients are canonicalised rather than forced onto another duplicate screen.

### 3. Partial-write risk during convergence

Calling an older handler and then recording a canonical command in a second transaction could leave a valid legacy event without the v26 command if the second operation failed.

**v26 control:** reused v25 domain handlers run through a deferred-commit session. Nested commits become flushes and v26 owns the outer transaction. The legacy outcome, safety link, command, impact and evidence commit together or roll back together.

### 4. Operational consequences hidden inside specialist modules

A staffing, equipment, medication-supply or confidential staff concern can affect several patients even when the restricted detail must not appear on a general board.

**v26 control:** `OperationalImpactV26` exposes only a board-safe summary, affected-patient count, service, severity and named owner. Restricted staff detail remains in the linked safety record. The active hospital bar and operating-context page show the current site's live impacts and open commands.

### 5. Weak protection against accidental cross-site access

A multi-site staff member could otherwise create or decide a record while mentally operating a different hospital.

**v26 control:** every canonical command and command outcome is checked against the active context. A decision on a command belonging to another site is rejected. Lists and operational views are filtered by organisation, site and premises.

### 6. Browser-supplied attribution

Legacy payloads still contain fields such as `fromActor`, `createdBy`, `acknowledgedBy` and `actor` for compatibility.

**v26 control:** the v25 verified-attribution layer remains in force, while v26 removes actor fields from canonical request evidence. Canonical actor subject, name, role and authentication source come from the verified session only.

## Canonical command classes

| Command | Protection created | Human authority retained |
|---|---|---|
| Patient blocker | Safety hold, clinical review action, board impact | Clinician decides whether and how the blocker is cleared |
| Handover request | Responsibility remains with current owner until acceptance | Named recipient accepts, rejects or escalates |
| Critical result received | Red safety record and named acknowledgement action | Assigned clinician reviews and records action |
| Consent review request | Progression hold and evidence-review task | Authorised clinician verifies valid consent |
| Estimate review request | Named owner and communication task | Human confirms estimate discussion and authority |
| Discharge review request | Discharge hold and clinical review task | Authorised clinician decides discharge readiness |
| Service restriction | Site-specific operational impact | Named operational owner decides capacity and restoration |
| Equipment downtime | Multi-patient impact and service restriction task | Human assesses alternatives and patient plans |
| Medication supply delay | Clinical/pharmacy safety task | Prescriber and pharmacy staff agree a safe plan |
| Safety escalation | Named senior response and evidence | Senior human accepts and manages escalation |

## Daily operating behaviour

1. The global context bar states the active organisation, site and premises.
2. A user with more than one authorised site may switch explicitly.
3. The context version prevents stale browser tabs from silently switching authority.
4. Patient Command, Hospital Today and other authenticated pages inherit the same visible context.
5. Existing patient blocker, handover and critical-result URLs create one linked canonical command.
6. Hospital Context shows active impacts, affected patients, open commands and legacy-route convergence.
7. Confidential staff allegations never appear on general boards; only the necessary protective consequence is displayed.

## Crossover controls

### Staff sickness or fatigue affecting a theatre list

The restricted workforce record remains confidential. A separate service or patient impact states that cover is constrained, identifies affected patients and requires a named safe-cover review. The system does not discipline staff or decide clinical substitutions.

### Critical result during handover

The handover does not transfer responsibility before acceptance. The critical result remains an independent open command until a named clinician acknowledges it and records action. Both commands are tied to the same site and episode.

### Missing consent or estimate before a procedure

The command creates a hold and review task. It cannot fabricate consent, mark consent complete or authorise the estimate.

### Equipment failure affecting several patients

One downtime command can enumerate all known affected patients, expose an accurate board count and assign restoration/capacity review. Individual clinical plans remain human decisions.

### Confidential conduct concern affecting operations

The allegation stays in strict v25 safety access. v26 exposes only the safe operational restriction, affected service/patient count and named independent owner.

## Legacy retirement approach

The convergence register gives each route a state:

- `observe`: canonical evidence is collected while compatibility is retained;
- `warn`: callers receive deprecation information and telemetry identifies remaining clients;
- `block`: ambiguous writes are rejected with the canonical replacement;
- `retired`: route is removed after UAT and historical reads remain available where required.

Removal must not occur until shadow comparison, user acceptance, rollback rehearsal and retained workflow tests are green.

## Remaining deployment work

v26 is repository code, not a live hospital deployment. Before bounded live use, LucyWorks still requires:

- real OIDC organisation/site claims and staff-directory reconciliation;
- verified hospital, department, room and service configuration;
- actual PMS, laboratory, imaging, pharmacy, billing, insurance and rota integrations;
- organisation-approved consent, estimate, discharge, medication, safeguarding and whistleblowing policies;
- device, accessibility and role-based UAT in the hospital;
- DPIA, data-processing agreements, penetration testing, safety case and named approvals;
- load, failover, downtime and restore testing with production-scale data;
- automatic affected-patient reconciliation against the live scheduling and patient systems;
- retirement of compatibility routes only after real-client telemetry and signed acceptance.

## Acceptance evidence

The v26 proof must demonstrate:

- non-default active premises;
- additive authorised memberships;
- successful and evidenced site switching;
- stale and unauthorised switching rejected;
- cross-site and `default-premises` writes rejected;
- idempotent canonical commands;
- spoofed actor fields excluded;
- patient blocker, handover and critical-result legacy URLs canonicalised;
- consent and discharge controls remain human decisions;
- multi-patient operational impacts are board-safe;
- no medication order, administration, clinical transition or closure is autonomously created;
- one valid evidence chain;
- migration `0020_operational_convergence_v26` and restore coverage;
- all retained repository checks green before merge.
