# LucyWorks OS v28 — Real Hospital Connection and Speech Hardening

## Purpose

v28 is the governed bridge between LucyWorks' tested internal hospital workflows and real devices or external hospital systems. It does not grant external write-back authority.

## Speech flow

```text
approved site speech provider
→ real-device diagnostics
→ canonical patient episode
→ resumable transcript session
→ ordered final segments with confidence/timestamps/speaker labels where available
→ interrupted session can resume without replacing saved segments
→ completed transcript creates a v19 proposed draft
→ responsible user reviews and edits
→ explicit v19 confirmation
→ signed note and/or accepted owned work
```

LucyWorks does not retain raw audio in this deployment profile. Browser speech remains available as one provider type; cloud and hospital-hosted providers can be configured without coupling clinical workflow to a single vendor.

## Integration flow

```text
disabled connector
→ configuration and secret-presence test
→ shadow/read-only promotion request
→ independent second-person approval
→ inbound event recording
→ verified canonical patient/episode match
→ processing or explicit reconciliation queue
→ evidenced replay when required
```

The v28 API supports identity, patient-management, laboratory, imaging, pharmacy, insurance and communications connector types.

## Safety boundaries

- No v28 route writes to an external hospital system.
- Only `shadow` and `read_only` connector modes can be promoted.
- Promotion requires a different senior approver from the requester.
- Duplicate external event IDs are idempotent only when their content hash matches.
- Unmatched patient or episode data becomes visible reconciliation work.
- Critical-result, medication and patient-update mismatches are elevated.
- Connector replay operates on LucyWorks' recorded event only.
- Speech completion creates a proposed v19 draft, never an automatic signed note.
- Medication expressions remain proposals and continue through Medication Foundation v18.
- Raw-audio retention remains disabled.

## Data model

Migration `0022_real_hospital_connection_v28` adds:

- `speechproviderv28`
- `speechsessionv28`
- `speechsegmentv28`
- `integrationconnectorv28`
- `integrationpromotionv28`
- `integrationeventv28`
- `reconciliationitemv28`

These records form clinical, deployment and information-governance evidence. Automatic downgrade is deliberately non-destructive.

## Main endpoints

- `GET /api/v28/deployment/control-centre?siteRef=...`
- `POST /api/v28/deployment/speech/providers`
- `POST /api/v28/deployment/speech/providers/{providerRef}/test`
- `POST /api/v28/deployment/speech/providers/{providerRef}/approve`
- `POST /api/v28/deployment/speech/sessions`
- `POST /api/v28/deployment/speech/sessions/{sessionRef}/segments`
- `POST /api/v28/deployment/speech/sessions/{sessionRef}/interrupt`
- `POST /api/v28/deployment/speech/sessions/{sessionRef}/resume`
- `POST /api/v28/deployment/speech/sessions/{sessionRef}/complete`
- `POST /api/v28/deployment/connectors`
- `POST /api/v28/deployment/connectors/{connectorRef}/test`
- `POST /api/v28/deployment/connectors/{connectorRef}/promotions`
- `POST /api/v28/deployment/promotions/{promotionRef}/approve`
- `POST /api/v28/deployment/connectors/{connectorRef}/events`
- `POST /api/v28/deployment/reconciliation/{itemRef}/resolve`
- `POST /api/v28/deployment/events/{eventRef}/replay`

## Web surface

`/deployment-control` provides:

- organisation and site context entry;
- speech-provider creation, testing and approval;
- real browser microphone and permission diagnostics;
- governed real-device speech sessions;
- interruption/resume controls;
- connector registration and testing;
- shadow-promotion requests;
- live connector and reconciliation status.

## Production requirements

Production readiness requires:

- `V27_CONFIGURATION_REQUIRED=true`
- `V28_CONNECTION_CONTROL_REQUIRED=true`
- migration head `0022_real_hospital_connection_v28`
- all v28 evidence tables present
- no active connector outside shadow/read-only mode
- passed tests for every active connector
- configured connector secrets loaded
- passed tests for every approved speech provider
- no approved provider retaining raw audio
- configured external speech-provider secrets loaded

## What remains deployment-specific

The code does not invent hospital credentials, vendor contracts or patient data. A real deployment still requires:

- the hospital's approved identity provider and claim mapping;
- vendor API documentation and sandbox credentials;
- data-processing and retention decisions;
- device/browser testing in the hospital network;
- veterinary vocabulary and service phrase packs;
- historical replay and reconciliation acceptance criteria;
- bounded pilot approval before any operational reliance;
- a later separately governed release before external write-back can even be considered.
