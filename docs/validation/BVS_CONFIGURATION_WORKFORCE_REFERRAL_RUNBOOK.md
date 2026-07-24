# BVS configuration, workforce and referral validation runbook

## Purpose

This runbook governs the conversion of the LucyWorks BVS draft model into an approved local hospital configuration. It does not permit public website content, informal recollection or synthetic test data to become operational truth without authorised review.

## 1. Configuration evidence

For each premises, service, area and facility:

1. Review every linked claim separately.
2. Record the source type, date and evidence reference.
3. Retain conflicting claims as `disputed` until authoritative hospital evidence is supplied.
4. Reject or supersede incorrect claims; never delete the history.
5. Mark the configuration record `verified` only after the accountable hospital role approves the authoritative value.

The public claim of five BVS operating theatres and the earlier internal report of eleven remain separate until the approved room register or equivalent evidence resolves the difference.

## 2. Verification queue

Red tasks must be resolved before shadow eligibility. The response must include:

- the hospital answer;
- the accountable respondent and role;
- an approved evidence reference;
- the date reviewed;
- any expiry or required re-review date.

A provisional answer may guide design but must not remove a red gate.

## 3. Workforce records

Use stable internal staff references rather than names as identifiers. Confirm:

- employment status;
- primary role and department;
- professional registration where relevant;
- grade or training level;
- named supervisor when supervision is required;
- contracted hours and locally approved workload thresholds;
- on-call eligibility.

A job title does not grant clinical privilege or system authority.

## 4. Competencies

Competencies are recorded separately from roles. Verification requires evidence and must define:

- competency reference;
- scope, such as hospital, service or area;
- supervised or independent level;
- valid-from and valid-until dates where applicable;
- verifier identity.

Expired, provisional or missing competencies do not satisfy safe-coverage requirements.

## 5. Rota and availability

Import or enter shifts using stable shift references. Record leave, sickness, training and temporary restrictions as availability exceptions.

LucyWorks rejects overlapping shifts unless an authorised user records a governed override reason. The rota assessment excludes staff who are absent, unqualified for the required scope or above a configured red workload threshold.

Rest and maximum-hours thresholds are local governance inputs. A signal is a prompt for human review and does not by itself determine fitness to work.

## 6. Referral intake

The referral pathway is:

`received → information requested or ready for clinical review → accepted, declined or redirected → booked or emergency transfer → arrived`

Before clinical review, confirm:

- patient and owner details;
- referring practice;
- presenting problem;
- clinical history;
- requested service;
- required attachments and results.

Only authorised clinical decision roles may accept, decline or redirect a referral. Every decision requires a reason and verified actor attribution.

## 7. Historical replay

Use anonymised data only. A replay event should include:

- stable event reference;
- timestamp;
- event type;
- anonymised episode reference where needed;
- area and staff references where needed;
- whether an alert was expected;
- whether LucyWorks detected it;
- decision latency where available.

Review missed alerts, false positives, capacity breaches, resource conflicts and unacknowledged handovers. A passing replay is necessary but not sufficient for shadow mode.

## 8. Shadow eligibility

The BVS v6 workspace remains blocked until:

- disputed configuration claims are resolved;
- all red verification tasks are evidenced;
- at least one authoritative configuration record is verified;
- at least one anonymised historical replay passes.

Production readiness, identity, vendor integration, DPIA, security testing and hospital pilot controls remain separate additional gates.

## 9. Stop and rollback

Stop the validation exercise immediately when:

- real patient data has been entered without an approved lawful process;
- a public or synthetic claim is presented as verified local truth;
- a referral decision is attributed to the wrong person;
- rota coverage depends on an absent, expired or unverified competency;
- red replay findings are concealed or closed without evidence.

Preserve the evidence trail, record the incident, revert to the hospital's approved existing operating process and investigate before resuming.
