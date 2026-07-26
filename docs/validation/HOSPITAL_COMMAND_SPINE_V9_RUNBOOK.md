# Hospital Command Spine v9 validation runbook

## Purpose

This runbook validates that `CanonicalEpisodeState` is the single operational phase authority for a referral episode. It does not certify live clinical use. Live use requires approved hospital policy, identity groups, consent wording, emergency-override rules and real integration data.

## Surfaces

- Operator workspace: `/episode-command`
- State-machine specification: `GET /api/v9/episode-state-machine`
- Episode command view: `GET /api/v9/episodes/{episode_ref}/command-view`
- Transition guard: `GET /api/v9/episodes/{episode_ref}/transition-guard/{target_phase}`
- Versioned transition command: `POST /api/v9/episodes/{episode_ref}/transition`

## Invariants

1. A governed referral creates the canonical episode.
2. A referral cannot progress to consultation until accepted.
3. Owner consent must be linked to an active decision-authority relationship.
4. A financial authorisation limit requires an active financial-responsibility relationship.
5. Cross-role clinical transfers require structured handover and receiving-role acknowledgement.
6. Every transition carries the expected canonical episode version and an idempotency key.
7. Blocked transitions are recorded; they are not silently discarded.
8. Structural gates cannot be waived.
9. Waivable gates require a named senior actor, reason and expiry no more than 24 hours ahead.
10. Discharge requires sent discharge documentation and owner communication evidence.
11. Full clinical closure requires an approved closure record with no outstanding actions.
12. Declined, cancelled and not-attended referrals use the early-closure path and are not falsely represented as discharged cases.

## Automated validation

From `apps/api`:

```bash
python hospital_command_v9_smoke_test.py
python hospital_command_v9_hardening_smoke_test.py
```

The tests cover:

- referral creation and clinical acceptance;
- legacy transition retirement;
- graph and role enforcement;
- transition idempotency;
- optimistic stale-write rejection;
- owner authority and consent;
- UTC normalisation on SQLite;
- financial-responsibility enforcement;
- structured handover and acknowledgement;
- inpatient and discharge blockers;
- sent-document and communication gates;
- bounded senior waiver;
- non-waivable structural gates;
- full discharge and closure;
- early declined-referral closure.

## Database validation

SQLite:

```bash
cd apps/api
DATABASE_URL=sqlite:////tmp/lucyworks-command-v9.db AUTO_CREATE_SCHEMA=false alembic upgrade head
alembic current
```

Expected head:

```text
0010_hospital_command_spine
```

Required v9 tables:

- `referralintakev9`
- `consentauthorisationv9`
- `episodehandoverv9`
- `episodecheckpointv9`
- `episodetransitionv9`
- `episodeclosurev9`

The GitHub workflow `Hospital Command Spine v9 Check` repeats the migration against PostgreSQL 16.

## Manual operator validation

1. Open `/episode-command` with an authorised test identity.
2. Load a synthetic canonical episode.
3. Confirm the current phase, owner role and version.
4. Review each available transition and its blockers.
5. Accept the referral using a clinician identity.
6. Record scoped consent from an owner with decision authority.
7. Confirm a financial limit is rejected when financial responsibility is absent.
8. Offer a structured handover and acknowledge it as the receiving role.
9. Confirm canonical ownership changes only after acknowledgement.
10. Execute an allowed phase transition.
11. Repeat the same command idempotency key and confirm the original result is returned.
12. Submit an old expected version and confirm HTTP 409.
13. Attempt to waive `transition_graph` or `decision_authority` and confirm rejection.
14. Create a waivable checkpoint with a future expiry under 24 hours.
15. Confirm the blocker becomes an attributed warning.
16. Prepare and approve a closure only after the required evidence exists.
17. Confirm final transition to `closed` completes the closure record.

## Declined-referral validation

A declined referral must not require discharge documentation. It must have:

- a referral status of `declined` for disposition `referral_declined`;
- no outstanding actions;
- a closure-ready financial status such as `no_charge`;
- outbound owner or referrer communication evidence;
- senior closure approval.

The resulting canonical episode moves directly from an early phase to `closed` and the closure record becomes `completed`.

## Restore rehearsal

Run the standard restore rehearsal against a production-format backup:

```bash
LUCYWORKS_RESTORE_CONFIRMATION="REHEARSE RESTORE" \
  bash scripts/restore-rehearsal.sh deploy/.env.production deploy/backups/<backup-file>
```

The rehearsal requires migration `0010_hospital_command_spine`, verifies every v9 table and reports restored counts for referrals, consent, handovers, transitions and closures.

## Stop conditions

Do not progress a pilot when any of the following is unresolved:

- canonical and external episode state disagree;
- identity or role mapping is unverified;
- consent policy is not approved;
- a structural gate has been bypassed;
- a waiver has no expiry or accountable senior actor;
- a handover is unacknowledged;
- discharge documentation or owner communication is missing;
- restore rehearsal fails;
- PostgreSQL migration, web build or production container build fails.
