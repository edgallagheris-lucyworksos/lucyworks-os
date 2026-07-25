# LucyWorks v7 consolidation and clinical execution validation

## Purpose

This release consolidates unsafe prototype paths into verified, versioned and evidenced operating services. It does not authorise LucyWorks for live clinical use. Local policies, vendor contracts, clinical safety review, DPIA approval, penetration testing, UAT and a controlled pilot remain organisational decisions.

## Release surfaces

- `/live-control` — durable event stream, acknowledgement, escalation and integration recovery.
- `/shadow-mode` — canonical source-to-episode/block comparison.
- `/clinical-execution` — medications, anaesthesia, observations, treatment tasks, diagnostics, pharmacy and discharge.

## Identity and session validation

1. Confirm production uses `AUTH_MODE=oidc` and `AUTH_ENFORCEMENT=required`.
2. Confirm `AUTH_RETURN_BEARER_DEV=false`.
3. Confirm the browser receives `lucyworks_session` as HttpOnly, Secure and SameSite=Lax.
4. Confirm unsafe requests without `X-CSRF-Token` fail with 403.
5. Confirm the idle timeout revokes the session.
6. Confirm logout and revoke-all prevent subsequent API use.
7. Test OIDC single logout and role removal with the real identity provider.
8. Test step-up reauthentication for any locally designated high-risk approval.

## Canonical Shadow Mode

1. Import anonymised source rows with stable source references.
2. Verify that unknown episodes/blocks are flagged.
3. Verify that patient, phase, area, owner and time mismatches are explained separately.
4. Open the same comparison in two sessions and prove the stale review receives 409.
5. Confirm each review records the verified reviewer and evidence event.
6. Do not permit pilot progression while open investigations remain.

## Durable realtime

1. Publish a synthetic event and record its sequence.
2. Disconnect the browser, publish more events and reconnect using the last sequence.
3. Confirm all missed events replay in order.
4. Run the PostgreSQL concurrency test and confirm sequence uniqueness.
5. Restart an API container and run `scripts/failure-drill-v7.sh`.
6. Confirm acknowledgement, escalation and resolution are versioned and evidenced.
7. Confirm only senior roles can resolve red operational events.

## Integration reliability

1. Send a valid signed sandbox webhook.
2. Force the adapter to fail and confirm a retry job is created in the same transaction.
3. Confirm retained payloads retry with bounded exponential backoff.
4. Confirm non-retained payload failures enter dead-letter state and require source-system resend.
5. Confirm manual replay records a named operator and evidence event.
6. Validate vendor acknowledgement, schema version and certificate/key rotation using the real vendor sandbox.

## Clinical execution

Use synthetic or fully anonymised cases only until hospital approval.

### Medication

- A nurse cannot create a prescription.
- High-risk and controlled-drug administrations require a witness reference.
- Omitted, withheld and refused doses require a reason.
- Stale administrations receive 409.
- Adverse reactions create red evidence and durable events.

### Anaesthesia

- The responsible clinician is derived from the verified session.
- Induction is blocked until identity, consent, equipment and airway checks are complete.
- Complications are append-only and generate red evidence.
- Recovery is explicitly recorded.

### Inpatient observations and tasks

- Amber/red observations create an unresolved escalation.
- A clinician or senior role must resolve an escalation.
- Treatment tasks are versioned and may require a witness.
- Overdue red tasks remain visible in the control summary.

### Controlled drugs and pharmacy

- Every controlled-drug movement requires a witness.
- Balance mismatches create open discrepancies.
- Only senior authority may resolve a discrepancy, with a second witness reference.
- Inventory changes use an append-only movement ledger.
- Negative stock is rejected.
- Low-stock state is generated from the verified quantity and reorder threshold.

### Diagnostics

- Requests are linked to canonical episodes.
- Specimen chain events preserve receipt/location history.
- Critical reports create a critical-result acknowledgement workflow.
- Imaging/laboratory vendor identifiers must be reconciled before live use.

### Discharge

Approval is blocked until:

- care instructions exist;
- warning signs exist;
- no medication administration remains due;
- owner communication is complete and has an evidence reference;
- the referring-vet report is sent/completed and has an evidence reference;
- a verified clinician approves the plan.

## Load and failure testing

Read-only baseline:

```bash
python scripts/load-test-v7.py --base-url https://staging.example --requests 5000 --concurrency 100
```

Synthetic durable-event test:

```bash
python scripts/load-test-v7.py --base-url https://staging.example --requests 2000 --concurrency 50 --write-events
```

Run API restart drill only in an approved maintenance window:

```bash
export LUCYWORKS_FAILURE_DRILL_CONFIRMATION="RUN CONTROLLED DRILL"
export LUCYWORKS_BASE_URL=https://staging.example
bash scripts/failure-drill-v7.sh deploy/.env.production
```

Hospital acceptance must define stricter latency/error targets based on measured PIMS, imaging, laboratory and identity-provider behaviour.

## Migration and restore

- Expected migration head: `0008_consolidation_clinical`.
- Run a full backup before migration.
- Apply migrations using the one-shot migrate container.
- Run the isolated restore rehearsal and verify clinical, session and event tables.
- Do not downgrade automatically: these tables contain security, clinical and governance evidence.

## Rollback

Application rollback may return to the prior container image while retaining migration `0008`. Do not drop the new tables. If v7 writes must be stopped, disable access through the reverse proxy and preserve the database for investigation. Record the decision in the incident log.

## External work still required

- real BVS configuration and role-group approval;
- identity-provider registration and logout testing;
- actual PIMS/PACS/laboratory/HR sandbox connections;
- medication, controlled-drug, anaesthesia and discharge policy mapping;
- clinical safety case and hazard log;
- independent penetration test;
- accessibility testing with hospital staff and assistive technology;
- sustained load/soak/failover testing on the selected hosting platform;
- historical replay, live shadow mode and bounded pilot approval.
