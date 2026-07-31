# Hospital pilot and integration simulator v29

## Purpose

V29 converts LucyWorks from a system that can stage real connections into a system that can prove a hospital pilot before live vendor access is supplied. It adds device diagnostics, streaming speech adapter contracts, governed veterinary terminology, isolated external-system simulators, deterministic failure injection, readiness assessments, bounded pilot controls, measurable outcomes and exportable deployment evidence.

## Operator surface

Open `/pilot-lab` from System Control.

The screen supports:

1. browser, microphone, network and secure-context diagnostics;
2. browser, cloud or hospital-hosted speech adapter configuration and testing;
3. independently approved veterinary terminology releases;
4. identity, PMS, laboratory, imaging, pharmacy, insurance and communications simulators;
5. delay, outage, duplicate, conflict, missing-field, incorrect-identifier and out-of-order fault scenarios;
6. hospital readiness assessments;
7. independent operations and clinical pilot approvals;
8. bounded case limits and automatic stop thresholds;
9. accuracy, review-time and incident measurements;
10. vendor integration specification and hospital deployment-pack export.

## Speech boundary

V29 does not replace v28 speech sessions. It defines and tests the streaming adapter that supplies them.

Every adapter records:

- provider and processing location;
- streaming protocol;
- reconnect policy and backoff;
- fallback provider reference;
- minimum confidence and maximum latency;
- network requirements;
- device, browser and privacy test evidence.

Raw-audio retention remains prohibited. Terminology correction returns a proposed transcript only. Medicine, dose, route and frequency wording remains subject to explicit authorised human review.

## Veterinary terminology

The default UK referral pack includes representative:

- species;
- anatomy;
- procedures;
- diagnostics;
- medicine and product names;
- units and administration wording;
- record phrases and abbreviations.

Site terms and local correction rules can be added in a versioned release. The creator cannot approve their own release.

## Integration simulators

Each simulator creates an in-process v28 connector with:

- `environment=simulator`;
- `mode=shadow`;
- no endpoint;
- no secret;
- `writeBack=false`;
- a permanent synthetic-data banner.

Synthetic events use `direction=simulated_inbound`, have no patient or episode reference and always enter reconciliation. They cannot silently attach to a canonical patient record.

## Fault injection

Supported deterministic faults are:

- delay;
- outage;
- duplicate;
- conflict;
- missing fields;
- incorrect identifiers;
- out-of-order delivery.

Every run records injected event references, affected synthetic references, detection result and immutable evidence. Outages prove visible unavailability rather than silent substitution. Duplicate tests prove detection without a second canonical event. All data remains synthetic.

## Readiness result

A readiness assessment returns one of:

- `READY`;
- `READY_WITH_RESTRICTIONS`;
- `NOT_READY`.

It checks:

- approved site configuration;
- active site membership;
- database connectivity;
- migration `0023_hospital_pilot_v29`;
- approved v28 speech provider;
- tested v29 speech adapter;
- approved terminology release;
- tested simulator coverage;
- microphone, secure context and network state;
- safe connector modes and loaded secrets;
- backup and restore evidence;
- evidence-chain integrity.

## Pilot authority

A pilot can only use `synthetic` or `shadow` mode. It records:

- site, department and service line;
- allowed devices, speech providers and simulators;
- case limit and date window;
- success criteria;
- stop criteria;
- rollback plan;
- accountable and clinical owners.

Operations and clinical approval must be supplied by different authorised people. Activation requires both approvals and a `READY` or acknowledged `READY_WITH_RESTRICTIONS` assessment.

## Stop controls and urgent access

New pilot activity is blocked when:

- the pilot is not active;
- its date window is closed;
- the case limit is reached;
- a red-incident threshold is exceeded;
- reviewed transcription accuracy falls below threshold;
- open reconciliation exceeds threshold.

A stopped pilot does not block urgent care. The case-start route returns an explicit instruction to continue through the existing non-pilot hospital workflow.

## Measurement

The pilot dashboard aggregates:

- cases started versus limit;
- transcription accuracy;
- review or dictation time versus baseline;
- average seconds saved;
- open and red incidents;
- simulator run outcomes;
- current stop reasons.

Measurements are evidence records, not autonomous clinical conclusions.

## Exports

### Vendor integration specification

Contains connector contracts, required event envelope, patient-matching boundary, health and stale-data rules, no-write operations, simulator coverage, speech adapter details, error behaviour and acceptance tests.

### Hospital deployment pack

Contains site identity, latest readiness evidence, pilot scope, pre-start and daily checklists, stop procedure, urgent-access preservation, rollback, staff training, data-protection controls and success/stop measures.

## Migration and recovery

Migration head: `0023_hospital_pilot_v29`.

The restore rehearsal verifies all v29 tables:

- `speechadapterv29`;
- `veterinaryterminologypackv29`;
- `integrationsimulatorv29`;
- `simulatorscenariov29`;
- `simulatorrunv29`;
- `readinessassessmentv29`;
- `hospitalpilotv29`;
- `pilotapprovalv29`;
- `pilotincidentv29`;
- `pilotmeasurementv29`;
- `exportartifactv29`.

## Non-negotiable exclusions

V29 does not provide:

- external-system write-back;
- autonomous clinical signing;
- prescribing;
- autonomous dose authorisation;
- unmarked synthetic data;
- automatic patient attachment when identity is uncertain;
- commercial or licensing controls that disable urgent patient access.
