# LucyWorks threat model

## Security objectives

1. Only verified hospital identities may access protected data or perform operational commands.
2. A user cannot claim another identity, role or professional status in a request payload.
3. Concurrent users cannot silently overwrite newer hospital state.
4. Vendor messages cannot be forged, replayed or duplicated without detection.
5. Evidence and governance records preserve provenance and cannot be silently rewritten.
6. Loss of LucyWorks must not remove the hospital's ability to revert to its agreed operating process.

## Trust boundaries

- User device ↔ TLS reverse proxy
- Reverse proxy ↔ web/API containers
- API ↔ OIDC provider
- API ↔ PostgreSQL
- Vendor system ↔ signed webhook gateway
- PostgreSQL ↔ backup storage
- API ↔ monitoring and alerting
- Administrators ↔ deployment and secret-management systems

## Assets

- patient and referral identifiers;
- client/owner contact and authorisation;
- clinical plans, results and procedure timing;
- staff identity, competencies, shifts and workload indicators;
- consent and estimate versions;
- operational commands, handovers and critical-result acknowledgements;
- integration payload hashes and external identity links;
- evidence-chain hashes and approval decisions;
- OIDC, database, monitoring and webhook credentials.

## Primary threat scenarios

### Identity and access

| Threat | Existing control | Required validation |
|---|---|---|
| Forged browser role | server-derived token role | actor-spoof test and real OIDC role test |
| Stolen session token | expiry, issuer/audience checks, TLS | session lifetime review and identity-provider conditional access |
| Leaver retains access | hospital identity lifecycle | disabled-account test and access review |
| Excessive role mapping | allowlisted LucyWorks roles | group-to-role approval and least-privilege test |

### Operational integrity

| Threat | Existing control | Required validation |
|---|---|---|
| Lost update | expected versions and PostgreSQL row locks | simultaneous write contention test |
| Duplicate command | unique idempotency keys | retry and duplicate-submission tests |
| Unsafe schedule assignment | explained constraints | realistic simulation and shadow comparison |
| Malicious override | named reason and senior evidence | approval workflow and audit review |
| Whole-board replacement | retired outside explicit legacy fixtures | production endpoint denial |

### Integration integrity

| Threat | Existing control | Required validation |
|---|---|---|
| Forged webhook | timestamped HMAC signature | invalid signature test |
| Replay | five-minute window and deduplication | old timestamp and repeated event test |
| Wrong patient match | external identity links and reconciliation queue | unmatched and conflicting identity tests |
| Corrected result overwrites prior result | append version and provenance | corrected-result test |
| Over-broad HR import | allowlisted fields | prohibited-field rejection test |

### Availability and resilience

| Threat | Existing control | Required validation |
|---|---|---|
| API/container failure | health checks and restart policy | failure injection and alert delivery |
| Database loss | checksummed backups | isolated restore rehearsal |
| Scanner/vendor outage | service-state controls | degraded-service simulation |
| Network partition | server-authoritative state and read-only cache principle | offline/reconnect UAT |
| Monitoring failure | independent Prometheus scrape | monitoring-down alert or external availability check |

### Privacy and audit

| Threat | Existing control | Required validation |
|---|---|---|
| Sensitive payload copied unnecessarily | raw payload retention off by default | integration configuration review |
| Audit actor spoofing | request context attribution | actor-spoof smoke test |
| Evidence tampering | chained hashes | scheduled evidence-integrity check |
| Sensitive data in logs | structured operational logs and minimal metrics labels | log sampling and redaction test |
| Excessive staff surveillance | bounded HR schema and DPIA | staff consultation and purpose limitation |

## Residual risks requiring organisational controls

- clinical users may act on incorrect source data even when LucyWorks faithfully displays it;
- role groups may be incorrectly administered by hospital IT;
- workflow alerts can create fatigue if thresholds are poorly tuned;
- shadow-mode agreement can be overstated without structured observation sampling;
- backup files can be copied outside approved storage by privileged administrators;
- vendor schemas may change without notice;
- the system cannot independently authorise its own clinical use.

## Mandatory security evidence before bounded pilot

- completed automated security assessment;
- OIDC role matrix test;
- dependency and container vulnerability scan;
- external penetration-test report;
- high/critical finding closure evidence;
- backup and restore report;
- incident-response exercise;
- access review;
- signed DPIA;
- red-observation count of zero.
