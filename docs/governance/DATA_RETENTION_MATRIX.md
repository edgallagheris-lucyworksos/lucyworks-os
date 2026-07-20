# LucyWorks data retention matrix

This is a decision template, not a predetermined legal retention schedule. The deploying organisation must set and approve each period.

| Data class | Default system behaviour | Proposed retention | Legal/operational rationale | Deletion/correction method | Approval owner |
|---|---|---|---|---|---|
| Patient and referral episode | retained in canonical episode records | TO DECIDE | continuity, audit, source-system alignment | correct through versioned command; delete only through approved policy | |
| Operational blocks and commands | append/versioned | TO DECIDE | patient-flow traceability and incident review | archive or approved deletion job preserving required evidence | |
| Consent and estimate versions | immutable versions | TO DECIDE | client authorisation and consumer evidence | correction by new version, not overwrite | |
| Evidence events and approvals | immutable chained evidence | TO DECIDE | accountability and compliance | retain minimum necessary fields; reviewed cryptographic archive | |
| Integration envelopes | payload hash always; raw payload optional/off by default | TO DECIDE | reconciliation and provenance | purge raw payload separately from hash/provenance | |
| Unmatched import rows | retained until resolved plus review period | TO DECIDE | reconciliation evidence | purge source record after approved resolution period | |
| Critical-result acknowledgements | retained | TO DECIDE | patient-safety accountability | correction by linked event | |
| Staff identity, role and shifts | active operational period plus approved history | TO DECIDE | assignment, competence and audit | source-led correction; leaver access removed immediately | |
| Fatigue/workload signals | minimal structured indicators | TO DECIDE | safe staffing, not performance scoring | aggregate or delete after operational review window | |
| Authentication and request logs | minimal request/security metadata | TO DECIDE | security monitoring and incident response | automated log lifecycle | |
| Monitoring metrics | aggregate labels only | 30 days in supplied Prometheus profile | availability and performance analysis | automatic time-series expiry | |
| Backups | encrypted, checksummed copies | 35 days in supplied template | recovery | automatic expiry plus secure storage lifecycle | |
| Pilot observations and readiness evidence | retained through approval/review cycle | TO DECIDE | governance decision evidence | archive after superseded review | |

## Required decisions

- Which system remains the authoritative clinical record?
- Which LucyWorks data must be copied into that system before deletion?
- Which immutable evidence fields are legally/operationally necessary?
- How are corrections linked to earlier inaccurate records?
- How are legal holds applied to active and backup data?
- Who can approve export, restriction, deletion or retention extension?
- How is backup expiry verified?
- How is raw integration payload retention disabled or justified?

## Implementation rule

No automated destructive retention job should be enabled until this matrix is approved, tested against a restored non-production database and recorded as evidence for `data.retention`.
