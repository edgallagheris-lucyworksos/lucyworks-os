# Deployment assurance v10

## Decision model

LucyWorks does not treat a true/false configuration field as deployment evidence.

A shadow, pilot or live release requires four separate stages:

1. **Readiness evidence is recorded** against a named control.
2. **The readiness control is formally passed** by an authorised governance role.
3. **The deployment profile binds the current evidence record** to a named deploying legal organisation.
4. **A target-specific safety review approves the release target** after all control gates pass.

The release gate remains blocked if any stage is absent.

## Evidence references

Deployment confirmations accept only the latest `ReadinessEvidence` record belonging to a `ReadinessControl` whose current status is `passed`.

This prevents:

- arbitrary reference strings;
- stale evidence superseded by a newer assessment;
- evidence attached to a control that remains failed or incomplete;
- a plain tick-box confirmation bypassing governance.

## Target requirements

### Shadow

- named deploying organisation;
- real identity-group mapping evidence;
- data-controller and governance evidence;
- vendor-connection and reconciliation evidence;
- named safety-owner evidence;
- approved DPIA evidence;
- target-specific shadow safety review.

### Bounded pilot and live

All shadow requirements, plus:

- penetration-test closure evidence;
- representative staff UAT evidence;
- target-specific pilot or live safety review.

## Synthetic validation

Synthetic and historical-replay work use the seeded developer safety baseline review. That review explicitly covers non-live engineering validation only and cannot satisfy shadow, pilot or live approval.

## Negative proof

`compliance_safety_v10_deployment_smoke_test.py` verifies that:

- bare confirmation booleans remain blocked;
- an invented evidence reference is rejected;
- passed evidence without a target review remains blocked;
- a target review cannot approve while control evidence is incomplete;
- a release gate passes only after the full evidence and review chain is present.

The synthetic test exercises the decision logic. Its synthetic organisation and test evidence are not represented as real hospital approval.
