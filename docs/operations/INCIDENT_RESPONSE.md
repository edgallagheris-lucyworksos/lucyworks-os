# LucyWorks incident response

## Incident classes

- **Clinical-operational:** wrong patient/episode, lost assignment, missed handover, unsafe constraint or critical-result delay.
- **Availability:** API, web, database, identity provider or vendor integration unavailable or materially degraded.
- **Privacy:** unauthorised access, disclosure, wrong-recipient communication or excessive data ingestion.
- **Cybersecurity:** credential theft, malicious request, malware, exploitation, evidence tampering or suspicious administrative activity.
- **Data integrity:** duplicate, stale, missing, corrupted or wrongly reconciled information.

## Immediate priorities

1. Protect patients and restore a safe human-controlled workflow.
2. Stop further harmful processing without deleting evidence.
3. Preserve logs, commands, integration envelopes, evidence hashes and timestamps.
4. Assign one incident commander and one clinical/operational owner.
5. Communicate clearly which system currently has operational authority.

## Severity

| Severity | Example | Initial response target |
|---|---|---|
| SEV-1 | credible patient-safety impact, active breach, widespread outage | immediate escalation |
| SEV-2 | material workflow disruption, contained disclosure, repeated integrity errors | urgent same-shift response |
| SEV-3 | limited defect with workaround and no current harm | planned investigation |
| SEV-4 | observation or improvement | backlog and review |

## Containment actions

### Unsafe operational behaviour

- Stop new LucyWorks operational commands for the affected scope.
- Return authority to the documented existing hospital process.
- Preserve the canonical board as read-only evidence.
- Record a red pilot observation and mark the pilot blocked.
- Do not reset or bulk-replace the board.

### Identity or access concern

- Disable affected identity-provider account or group assignment.
- Revoke sessions through the identity provider.
- Rotate relevant client, metrics or webhook credentials.
- Review access and command evidence for the affected subject and period.

### Vendor integration concern

- Change the connection status to inactive/degraded.
- Rotate that connection's HMAC secret.
- Preserve envelopes and payload hashes.
- Move unmatched messages into reconciliation rather than manually rewriting records.

### Database or infrastructure concern

- Stop writes if integrity is uncertain.
- Preserve a current backup before destructive recovery work where safe.
- Use the isolated restore-rehearsal procedure.
- Never restore over production without a reviewed change and rollback plan.

## Evidence capture

Record:

- start and detection times in UTC;
- reporter and incident commander;
- affected premises, service line, episodes and users;
- relevant request IDs, command refs, evidence refs and integration envelope refs;
- screenshots only when they do not create unnecessary additional copies of sensitive data;
- containment actions and decision owners;
- known and potential impacts;
- notifications and times;
- recovery criteria and verification.

## Communications

Use approved hospital channels. Separate:

- operational instructions to staff;
- client/owner communications;
- referring-vet communications;
- executive and governance updates;
- regulator, insurer or law-enforcement notifications where assessed as required.

Do not speculate about cause or impact. State confirmed facts, current controls and the next decision point.

## Recovery criteria

Recovery requires:

- the unsafe condition is understood or reliably contained;
- affected data has been reconciled;
- security credentials have been rotated where relevant;
- backups or restored data have passed integrity checks;
- the specific failure has been retested;
- monitoring is functioning;
- clinical/operational and incident owners agree the scope can resume;
- the red observation is resolved with evidence.

## Post-incident review

Within the organisation's required timeframe:

- produce a factual timeline;
- identify technical and organisational causes;
- distinguish detection failure from prevention failure;
- add permanent controls and tests;
- review similar records for wider impact;
- update the DPIA, threat model, training and runbooks;
- record residual risk acceptance by a named owner;
- upload the approved report as readiness evidence.
