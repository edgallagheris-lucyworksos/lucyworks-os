# Operational UX and Real-UAT Preparation v31

## Objective

Complete Issue #71 without adding a new clinical module. The staff workflow remains:

`Patient Command -> Care Brief -> Hospital Today`

## Acceptance contract

1. Episode context is read from the URL, retained during related navigation and never requires routine reference copy/paste.
2. Operational components use the shared authenticated API client. Live-data failures are explicit; no seed snapshot is silently substituted.
3. Operational browser prompts and alerts are replaced by labelled, reviewable forms with reason, confirmation and resulting-state evidence.
4. Referral intake is a six-stage guided flow: patient/duplicate, owner/authority, source, clinical need/urgency, documents/review, confirmation/next action.
5. Generic, duplicate and raw-JSON staff surfaces are retired, redirected or explicitly marked as technical diagnostics.
6. Local operating dates use the local-date helper.
7. Android and desktop UAT evidence remains a real-device boundary and is not fabricated by automated tests.

## Delivery evidence

The v31 CI gate runs the operational UX inventory, static safety validation, existing connected proof, mobile input proof and the complete production web build. Any remaining warning is treated as a named defect unless it belongs to an explicitly isolated technical diagnostic route.
