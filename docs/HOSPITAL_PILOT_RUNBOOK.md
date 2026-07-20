# LucyWorks OS — Referral Hospital Pilot Runbook

## Deployment boundary

Passing automated tests does not make LucyWorks suitable for live clinical use. A hospital pilot requires verified identity, managed PostgreSQL, reviewed data mappings, operating policies, information-governance approval and trained users.

## Stage 0 — Technical qualification

Required before any hospital data is loaded:

- Alembic is at `0004_hospital_operating_system_v3`.
- `AUTH_MODE=oidc` and `AUTH_ENFORCEMENT=required`.
- Development login and legacy board replacement are disabled.
- Managed PostgreSQL encryption, private networking and least-privilege accounts are confirmed.
- Backup creation and isolated restore rehearsal are evidenced.
- Error reporting, uptime monitoring and integration health alerts are active.
- Retention, incident-response and access-review policies have recorded references.
- DPIA, security review and penetration-test scope are approved.

The senior readiness endpoint is:

```text
GET /api/hospital-ops/readiness
```

No failed check may be treated as complete merely because an environment variable has been populated. The referenced control must be reviewed and evidenced.

## Stage 1 — Synthetic hospital simulation

Use the canonical board simulation in dry-run mode first:

```json
POST /api/hospital-ops/simulation/run
{
  "scenarioName": "eleven-theatre-referral-day",
  "premisesRef": "simulation-premises",
  "operationalDate": "2026-07-20",
  "seed": 42,
  "caseCount": 40,
  "commit": false
}
```

Test at least:

- eleven theatres;
- MRI, CT, radiography and ultrasound;
- 30–50 referral episodes;
- emergency arrival;
- procedure overrun;
- scanner failure;
- absent clinician;
- recovery and ICU pressure;
- delayed laboratory result;
- estimate ceiling reached;
- owner unreachable;
- incomplete handover;
- overnight deterioration.

Record response times, false alerts, missed conflicts, duplicate assignments and operator decisions.

## Stage 2 — Historical replay

Import a de-identified historical operating day through preview mode. Every rejected row must be reconciled before commit.

Required checks:

- patient and episode matching;
- physical area mapping;
- staff identity mapping;
- real timestamps and durations;
- consent, estimate, insurance and pharmacy gate mapping;
- cancellations and emergency insertions;
- final discharge and referring-vet report status.

No vendor export may write directly to canonical operational tables.

## Stage 3 — Live shadow mode

LucyWorks receives live or near-live events but is not the source of operational authority.

Use:

```text
GET /api/hospital-ops/shadow/compare
```

Compare the existing hospital source with the canonical plan throughout the day.

Minimum promotion criteria:

- at least 95% state agreement for five representative operating days;
- no unexplained missing patient or procedure;
- no lost update under concurrent use;
- no unauthorised write or actor spoofing;
- every red alert has a traceable explanation;
- critical-result and handover acknowledgements remain intact;
- users can identify the correct next action without separate spreadsheets;
- alert volume is acceptable to each role.

A percentage alone is insufficient. Every unmatched or clinically significant disagreement must be reviewed.

## Stage 4 — Controlled operational pilot

Start with one bounded service line, area or shift. Do not start with the entire hospital.

Recommended sequence:

1. One consultation/imaging pathway.
2. One theatre group with recovery.
3. One ward/ICU handover pathway.
4. Multi-department day control.
5. Whole-hospital operations.

During the pilot:

- retain the established fallback process;
- prohibit autonomous clinical decisions;
- require named overrides;
- hold daily safety review;
- review every stale-write rejection and integration failure;
- stop the pilot if source-of-truth ambiguity develops.

## Stage 5 — Scale and operational ownership

Required before wider adoption:

- named product owner;
- named clinical safety owner;
- named information-governance owner;
- support rota and incident escalation;
- release and rollback process;
- scheduled restore rehearsal;
- access recertification;
- data-retention jobs;
- documented vendor change management;
- measurable service-level objectives.

## Operational invariants

The following must remain true:

1. The server is authoritative.
2. Every mutation requires a verified identity.
3. Every block update carries an expected version.
4. Stale writes are rejected rather than silently merged.
5. Material decisions create immutable evidence.
6. Emergency overrides never erase the failed constraint.
7. Imports are previewed and reconciled before commit.
8. AI output remains advisory and requires human review.
9. A backup is not accepted until restore has been rehearsed.
10. A dashboard is not accepted unless its actions complete an end-to-end workflow.
