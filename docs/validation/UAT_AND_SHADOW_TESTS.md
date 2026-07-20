# LucyWorks UAT and shadow-mode acceptance

## Test rules

- Use synthetic or approved de-identified data until the DPIA permits the next phase.
- Record actual outcomes, not only pass/fail.
- Every red observation blocks progression.
- Do not correct a failure by directly editing the database or resetting the board.
- Test with two or more simultaneous users for multi-user scenarios.

## Role-based UAT

### Operations manager

1. Open `/system-control` and `/hospital-board`.
2. Confirm 11 theatres and all configured diagnostic/support areas appear.
3. Create or import a planned case.
4. Assign staff and a physical area.
5. Introduce a deliberate room conflict and verify the explanation and alternatives.
6. Delay a procedure and review the full propagation preview before applying it.
7. Confirm another user's screen receives the change.
8. Attempt an update from a stale screen and verify it is rejected without data loss.
9. Record a service degradation and confirm affected plans are flagged.
10. Review the command and evidence records for the actions.

### Clinician

1. Open an assigned referral episode.
2. Review patient, procedure, location, gates and next action.
3. Attempt to advance without required consent/estimate gates and confirm blocking or warning behaviour.
4. Record appropriate gates and advance through a permitted phase.
5. Review a critical result and confirm acknowledgement attribution.
6. Attempt a senior-only approval and confirm access is denied.
7. Confirm the interface does not claim to make the clinical decision.

### Nurse

1. Review assigned prep, recovery, ward and ICU work.
2. Confirm required competencies and location are visible.
3. Accept and complete a handover.
4. Identify a missing owner/location/next action.
5. Confirm unresolved work remains visible after refresh and on another device.
6. Test reconnect after temporary loss of network; verify no unconfirmed local write is presented as saved.

### Reception/admin

1. Create a referral episode.
2. Record owner/client communication requirements.
3. Record estimate, consent and insurance states within role permissions.
4. Import a sample file containing one valid and one invalid row.
5. Resolve the invalid row through reconciliation.
6. Confirm import cannot commit while unresolved rows remain.
7. Confirm no clinical-director privilege is available.

### Imaging/laboratory

1. Send a valid signed sample event.
2. Send an invalid-signature event and confirm rejection.
3. Replay the valid event and confirm deduplication.
4. Send a corrected laboratory result and confirm prior provenance remains.
5. Mark imaging degraded and confirm the control plane and constraint engine react.
6. Create a critical result and confirm escalation/acknowledgement ownership.

### Governance/security

1. Run `/production-readiness` automated security assessment.
2. Confirm the development environment fails production-only checks rather than claiming readiness.
3. Add evidence to a control and attempt a stale control update.
4. Verify the stale update is rejected.
5. Confirm a red pilot observation blocks shadow/live eligibility.
6. Resolve it with evidence and confirm the count changes.
7. Review actor attribution and evidence-chain integrity.

## Multi-user concurrency tests

- Two users move the same block from the same starting version.
- Two users assign different staff to the same block.
- One user delays a chain while another edits an affected successor.
- One user advances an episode while another changes its gates.
- A duplicate mobile submission repeats the same idempotency key.

Expected result: exactly one conflicting write commits; the other receives a clear stale/conflict response and reloads current state.

## Shadow-mode sampling

Run LucyWorks beside the existing hospital process without operational authority. For every sampled case compare:

- patient and episode identity;
- planned and actual procedure timing;
- responsible person;
- physical location;
- required competencies;
- consent, estimate, insurance and pharmacy state;
- delays and propagated consequences;
- handover status;
- critical-result acknowledgement;
- owner/referring-vet communication;
- discharge readiness.

Record agreement and disagreement categories, not only an overall percentage.

## Minimum acceptance criteria

Before bounded pilot:

- zero unresolved red observations;
- zero lost or silently overwritten updates;
- 100% correct patient/episode identity in the reviewed sample;
- 100% critical-result acknowledgement traceability;
- all required gates correctly represented for sampled cases;
- at least 95% staff agreement that owner, location and next action are clear;
- successful backup restore rehearsal;
- production security self-test passed;
- independent penetration-test high/critical findings closed;
- signed DPIA and UAT acceptance;
- named rollback owner present during pilot hours.

Upload the signed UAT report against `uat.acceptance` and shadow report against `shadow.mode` in `/production-readiness`.
