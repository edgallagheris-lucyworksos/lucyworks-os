# LucyWorks data protection impact assessment template

**Status:** Draft template. Completion and approval must be led by the deploying organisation's data protection and information-governance functions.

## 1. Assessment ownership

| Field | Required entry |
|---|---|
| Data controller | |
| Joint controllers or processors | |
| Data Protection Officer | |
| Clinical safety owner | |
| Information asset owner | |
| Assessment author | |
| Approval date | |
| Review date | |
| Processing locations | |

## 2. Processing description

Describe the deployed scope, including:

- referral intake and patient episodes;
- operational scheduling and staff assignment;
- estimates, consent and owner communication;
- laboratory, imaging, PIMS and workforce integrations;
- evidence events, approvals, handovers and critical-result acknowledgement;
- synthetic, historical-replay, shadow-mode and pilot processing;
- monitoring, backups and incident records.

State clearly which existing hospital systems remain systems of record and which decisions LucyWorks may or may not control.

## 3. People and data classes

Assess each class separately:

| Data class | Data subjects | Example fields | Source | Retention | Access roles |
|---|---|---|---|---|---|
| Client/owner | Animal owners and contacts | identity, contact, authorisation, communication | PIMS/intake | | |
| Patient | Animals | identity, species, episode, procedure, location | PIMS/clinical | | |
| Clinical workforce | Employees/contractors | name, role, competencies, shift, workload | HR/rota | | |
| Referring professionals | Vets/practices | identity, contact, report status | PIMS/referral | | |
| Audit and security | Users and administrators | actor, timestamp, source, action, IP/request ID | LucyWorks | | |

LucyWorks HR mapping expressly excludes salary, bank details, home address, diagnosis and free-text disciplinary narrative unless a separately approved design changes that boundary.

## 4. Purpose and lawful basis

For every processing purpose, record:

- purpose;
- necessity;
- lawful basis;
- special-category condition if applicable;
- whether the processing is expected by the affected person;
- consequences of not processing;
- whether automated decision-making is involved.

LucyWorks is designed to support workflow and evidence. It must not be described as an autonomous clinical decision-maker.

## 5. Data flow and recipients

Attach a diagram showing:

1. browser to web/API;
2. identity provider to LucyWorks;
3. PIMS/PACS/LIS/HR to signed webhook gateway;
4. API to PostgreSQL;
5. API and reverse proxy to monitoring;
6. PostgreSQL to encrypted off-host backups;
7. approved administrative exports.

List every recipient, subprocessor, support party and international transfer. Record the transfer mechanism and supplementary measures where relevant.

## 6. Necessity and proportionality

For each data element answer:

- Is it required for the stated operational purpose?
- Can it be replaced with a stable reference?
- Can it be viewed only when needed?
- Can it be excluded from logs and monitoring?
- Does the retention period match the operational/legal need?
- Is the source authoritative and correctable?

## 7. Rights and correction

Document the process for:

- access requests;
- correction of inaccurate owner or staff data;
- restriction and objection where applicable;
- deletion where lawful and technically compatible with immutable audit duties;
- export and portability where applicable;
- notifying downstream systems of corrections;
- preserving lawful evidence without retaining unnecessary source payloads.

## 8. Risk assessment

Score likelihood and impact before and after controls.

| Risk | Example cause | Potential harm | Existing controls | Further action | Owner | Residual score |
|---|---|---|---|---|---|---|
| Wrong patient or episode match | weak external identifiers | incorrect workflow or disclosure | reconciliation queue, external links, deduplication | | | |
| Excessive workforce monitoring | over-broad HR feed | unfair treatment, loss of trust | allowlisted fields, role restrictions | | | |
| Unauthorised clinical access | role-map error | confidentiality breach | OIDC, server roles, audit | | | |
| Lost operational update | simultaneous edits | patient delay or missed work | row locks, version checks | | | |
| Unavailable system | infrastructure failure | operational disruption | health checks, rollback, backups | | | |
| Incomplete deletion | copied payloads/backups | prolonged exposure | payload retention off by default, retention policy | | | |
| AI over-reliance | unclear interface or training | unsafe decision or deskilling | human review, AI governance, no autonomous authority | | | |

## 9. Security controls

Record evidence for:

- OIDC configuration and role tests;
- managed PostgreSQL and encrypted connections;
- secrets management;
- TLS and security headers;
- rate limiting;
- append-only evidence-chain verification;
- signed webhooks and replay protection;
- backup encryption and restore rehearsal;
- monitoring and incident response;
- vulnerability scanning and penetration testing;
- user access reviews and leaver removal.

## 10. Consultation

Consult representative:

- clinicians;
- nurses;
- operations managers;
- reception/admin;
- imaging and laboratory teams;
- pharmacy/stock roles;
- HR and information governance;
- IT/security;
- staff representatives where workforce monitoring is relevant.

Record objections and design changes rather than treating consultation as approval by attendance.

## 11. Decision

Choose one:

- Approved for synthetic testing only
- Approved for historical replay
- Approved for shadow mode
- Approved for bounded pilot
- Approved for defined live scope
- Rejected pending risk reduction

Approval must identify the exact premises, service line, users, integrations, review date and rollback authority. Upload the signed decision as evidence for `privacy.dpia` in `/production-readiness`.
