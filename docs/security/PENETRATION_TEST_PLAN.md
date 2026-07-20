# LucyWorks penetration-test plan

## Scope

Test the deployed staging environment and its real identity integration. Do not test production patient data without a separately approved plan.

In scope:

- web application and API;
- OIDC login, callback and role mapping;
- production-readiness, board, episodes, evidence, approvals and integrations APIs;
- signed vendor webhook endpoints;
- reverse proxy and TLS configuration;
- container and dependency configuration;
- backup/restore access controls;
- administrative and monitoring endpoints.

Out of scope unless expressly approved:

- denial-of-service load testing;
- hospital identity-provider infrastructure not owned by the project;
- vendor production systems;
- social engineering;
- physical access testing;
- extraction of real patient or employee data.

## Required test identities

- hospital director;
- governance lead;
- operations manager;
- clinical director;
- clinician;
- nurse;
- administrator;
- authenticated user with no LucyWorks role;
- disabled account;
- expired/revoked session.

## Test areas

### Authentication and authorisation

- token issuer, audience, expiry and signature validation;
- PKCE and callback state handling;
- role escalation and group mapping;
- object-level authorisation;
- actor-field spoofing;
- disabled/leaver account behaviour;
- session fixation, replay and logout expectations.

### Input and application security

- injection across JSON, query, CSV/JSON import and free-text fields;
- stored and reflected cross-site scripting;
- server-side request forgery;
- path traversal and unsafe file handling;
- mass assignment and over-posting;
- malformed content types and oversized bodies;
- duplicate/idempotency abuse;
- stale-version and race-condition attempts;
- sensitive error messages and stack traces.

### Integration gateway

- invalid HMAC signatures;
- old/future timestamps;
- repeated event IDs and payload hashes;
- connection-reference confusion;
- canonical identity collision;
- prohibited HR fields;
- corrected laboratory results;
- raw-payload retention boundary.

### Audit and evidence

- attempt to change actor identity;
- attempt to mutate immutable events;
- evidence-chain break detection;
- approval by an unauthorised role;
- override without reason;
- duplicate command and evidence references.

### Infrastructure

- TLS configuration;
- security headers and CORS;
- exposed ports and services;
- container privilege, filesystem and capabilities;
- secrets in images, environment output or logs;
- PostgreSQL network exposure;
- backup file permissions;
- monitoring endpoint protection;
- dependency and image vulnerabilities.

## Automated baseline

Run before and after independent testing:

```bash
python scripts/security-probe.py https://STAGING-DOMAIN
```

Also run software-composition analysis, secret scanning, container-image scanning and the repository CI suite. Tool selection must follow the deploying organisation's approved security tooling.

## Finding requirements

Every finding must include:

- severity and rationale;
- affected component and version;
- reproducible evidence;
- realistic hospital impact;
- recommended remediation;
- retest result;
- residual risk and named owner if not fully remediated.

High and critical findings block bounded pilot. Medium findings require a documented remediation date and accountable risk acceptance. Upload the final report and closure evidence against `security.pen_test`.
