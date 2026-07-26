# LucyWorks OS veterinary clinical and operational safety case v10

**Safety-case reference:** generated at bootstrap  
**Release:** v10  
**Baseline date:** 26 July 2026  
**Current engineering claim:** suitable for synthetic testing and controlled historical replay when the automated release gate passes  
**Live claim:** none

## 1. Executive safety statement

LucyWorks OS is designed to support referral-hospital operations without replacing veterinary professional judgement. The implemented controls reduce identified software-related clinical, operational, medicines, privacy and consumer risks for synthetic validation and historical replay.

The system does not autonomously diagnose, prescribe, consent, approve treatment, waive structural safeguards or declare a patient safe for discharge. Qualified professionals remain responsible for clinical decisions. A deploying organisation remains responsible for local configuration, staffing, information governance, vendor integration, training and actual use.

## 2. Intended use

LucyWorks coordinates and evidences:

- referral intake and acceptance;
- patient and owner identity;
- decision authority and consent;
- estimates, insurance and communication;
- staffing and competency coverage;
- theatre, imaging, ward and ICU flow;
- prescribing, medicine administration and controlled-drug records;
- anaesthesia, procedure, inpatient and diagnostic records;
- accountable handovers;
- discharge and closure;
- integration reconciliation;
- audit, governance, incident and release evidence.

## 3. Explicit exclusions

LucyWorks v10 is not intended to:

- make autonomous clinical decisions;
- replace examination, diagnosis or professional judgement;
- infer lawful consent without a recorded authorised decision maker;
- grant clinical permission from job title alone;
- store payment-card data;
- act as the primary image archive instead of PACS;
- silently overwrite newer canonical state with vendor data;
- certify BVS or any other hospital as ready;
- represent a developer review as a deployment-organisation safety approval;
- claim NHS DCB0129/DCB0160 certification or legal applicability to veterinary care.

## 4. Assurance basis

The safety method adapts the useful documentation structure of DCB0129 and DCB0160 as engineering best practice. It uses:

- defined intended use and boundaries;
- systematic hazard identification;
- severity and likelihood scoring from 1 to 5;
- design and operational controls;
- verification evidence;
- residual-risk assessment;
- target-specific release decisions;
- post-release monitoring and corrective action.

Current veterinary obligations, RCVS professional duties, privacy requirements, medicines rules, future CMA controls and government reform proposals are separately classified in `config/compliance/uk-veterinary-compliance-safety-v10.json`.

## 5. Risk acceptance criteria

Risk score is severity multiplied by likelihood.

| Score | Required treatment |
|---|---|
| 1–4 | Controlled; retain evidence and monitor. |
| 5–9 | Review required; owner and verification must be explicit. |
| 10–15 | Senior risk acceptance and additional verification required. |
| 16–25 | Release blocked. The hazard cannot be marked controlled or accepted. |

A hazard with status `open`, `uncontrolled` or `rejected` blocks the release gate regardless of score.

## 6. Hazard summary

The persisted v10 log contains 19 baseline hazards:

1. wrong patient or owner selection;
2. stale or duplicate command;
3. unauthorised clinical action;
4. invalid or withdrawn consent;
5. medicine, dose, weight or unit error;
6. controlled-drug discrepancy;
7. critical result not acknowledged;
8. information loss during handover;
9. unsafe staffing or competency coverage;
10. incomplete anaesthesia state or monitoring;
11. unsafe or incomplete discharge;
12. system outage and loss of current care information;
13. duplicate, late or mismatched vendor messages;
14. improper client or staff disclosure;
15. AI output accepted as clinical fact;
16. misleading or late cost and treatment information;
17. audit history deleted or altered;
18. emergency override misused or left active;
19. clock or timezone error.

Each hazard records the hazardous situation, potential harm, initial risk, controls, verification method, evidence references, residual risk, owner role, status and version.

## 7. Core safety controls

### Identity and authority

- verified authentication;
- least-privilege role gates;
- separate registration, competency and supervision evidence;
- owner decision-authority links;
- financial responsibility separate from clinical authority;
- read-only inspection role;
- synthetic-test identities prohibited from production use.

### Clinical workflow

- one canonical episode phase authority;
- versioned and idempotent commands;
- structural gates that cannot be waived;
- time-bounded senior waivers for eligible controls;
- current patient identity and owner authority checks;
- scoped consent with withdrawal history;
- structured acknowledged handovers;
- discharge and closure evidence gates.

### Medicines

- durable medicine records;
- weight, unit, allergy and formulary checks;
- prescriber authority;
- controlled-drug running balance;
- witness and discrepancy handling;
- append-only audit evidence.

### Diagnostics and integrations

- source provenance;
- patient and episode cross-checks;
- idempotency and event ordering;
- no silent overwrite;
- critical-result acknowledgement and escalation;
- mismatch reconciliation and dead-letter recovery.

### Resilience and security

- migration-controlled schema;
- stale-write and durable-event concurrency tests;
- production image builds;
- production Compose validation;
- backup integrity and restore rehearsal;
- secure-by-default production configuration;
- incident and escalation controls.

### AI

- advisory-only use;
- manual verification of generated clinical text;
- model registration and provenance;
- no autonomous clinical transition or approval;
- human review and accountability retained.

## 8. Evidence and review model

A live confirmation cannot be supplied as a Boolean alone.

The required chain is:

1. evidence is recorded against a readiness control;
2. the readiness control is formally passed;
3. the deployment profile binds the latest evidence record to a named legal organisation;
4. all hazard and deployment controls pass;
5. an authorised role completes a target-specific safety review;
6. the release gate is recalculated and recorded.

Invented references, stale evidence, evidence belonging to an unpassed control and evidence without a target review remain blocked.

## 9. Current evidence status

The automated suite proves:

- current/future legal-status separation;
- complete hazard seeding;
- residual-risk release blocking;
- stale-write rejection;
- authenticated access;
- synthetic and historical release path;
- live blocking without deployment evidence;
- rejection of arbitrary evidence references;
- separation of evidence and safety approval;
- SQLite and PostgreSQL migrations;
- full API regression;
- web build;
- production container builds;
- production Compose rendering;
- restore-table integrity.

Passing automated tests demonstrates software behaviour in the tested environment. It does not prove local clinical adoption, human competence, vendor correctness or hospital governance.

## 10. Known limitations and residual dependencies

Before shadow, pilot or live use, the deploying organisation must provide and approve:

- legal-entity and accountable-owner identity;
- real OIDC groups and person-to-role mapping;
- professional registration and competency evidence;
- data-controller decisions and DPIA;
- processor and vendor contracts;
- tested PIMS, PACS, LIS, workforce, insurance and payment mappings;
- local staffing, service and escalation rules;
- local consent, emergency, discharge and closure policy;
- penetration-test closure;
- representative staff training and UAT;
- downtime and recovery procedures;
- named safety ownership;
- target-specific safety review and release decision.

## 11. Post-release monitoring requirements

A bounded deployment must monitor:

- wrong-patient near misses;
- medication and controlled-drug discrepancies;
- critical-result acknowledgement delays;
- handover failures;
- staffing and service-availability gaps;
- vendor mismatch and retry rates;
- stale-write conflicts;
- discharge blockers and readmission signals;
- privacy and security incidents;
- override frequency and expiry;
- user-reported workflow hazards;
- AI corrections and rejected outputs.

Material incidents must create an evidence event, named owner, containment action, investigation, corrective/preventive action and safety-case review.

## 12. Approval record

The persisted `SafetyReviewV10` ledger is the authoritative approval record.

A developer baseline review may approve only synthetic and historical engineering validation. Shadow, bounded pilot and live use each require a separate target-specific review after all deployment controls pass.

Unsigned text in this document is not an approval.
