# LucyWorks role-based training

## Shared principles for every user

LucyWorks coordinates work, responsibility, evidence and operational constraints. It does not replace professional clinical judgement and must not be treated as an autonomous diagnosis, prescription or treatment system.

Every user must understand:

- the canonical hospital board is server-controlled;
- an action is not saved until the server confirms it;
- stale updates are rejected rather than silently overwriting newer work;
- owner, location, time and next action must remain explicit;
- red constraints and critical results require active human resolution;
- overrides require a reason and may require senior approval;
- every material action is attributed to the verified identity;
- patient identity must be checked before acting;
- during a serious fault, operational authority returns to the documented hospital process.

## Operations managers

Training outcomes:

- control the 15-minute hospital grid without creating a parallel schedule;
- review room, staffing, competence, equipment and governance constraints;
- preview propagated delays before applying them;
- distinguish a warning from a hard block;
- run simulation, historical replay and shadow-mode reviews;
- record pilot observations objectively;
- block a pilot when safety or integrity is uncertain;
- activate the incident-response and rollback process.

Practical assessment:

1. Resolve a room collision without hiding either case.
2. Delay an MRI procedure and explain all affected work.
3. Demonstrate a stale-write rejection on two devices.
4. Record and resolve a red shadow-mode observation.
5. Identify who may approve DPIA, security and pilot controls.

## Clinical directors and senior clinicians

Training outcomes:

- review clinical and operational gates without delegating judgement to the system;
- approve or reject governed overrides;
- review critical-result acknowledgement and handover evidence;
- understand how competence and supervision constraints are represented;
- recognise when LucyWorks data conflicts with the clinical record;
- stop the workflow and initiate reconciliation.

Practical assessment:

1. Review an episode blocked by consent/estimate state.
2. Reject an unsupported override.
3. Acknowledge a critical result and verify attribution.
4. Compare LucyWorks against the source clinical record.
5. Lead rollback from an unsafe pilot condition.

## Clinicians

Training outcomes:

- find assigned episodes and next actions;
- confirm patient/episode identity;
- record factual gates and progress through permitted phases;
- distinguish system suggestions from professional decisions;
- escalate incomplete information, consent, estimates or results;
- preserve evidence when correcting an earlier record.

Practical assessment:

1. Advance a complete episode through a permitted transition.
2. Demonstrate that an incomplete episode is blocked or warned appropriately.
3. Record a correction without overwriting prior evidence.
4. Attempt a senior-only action and confirm denial.

## Nurses and patient-care teams

Training outcomes:

- use prep, recovery, ward and ICU views;
- confirm competence, supervision, location and handover ownership;
- accept handovers rather than assuming receipt;
- identify overdue tasks and unacknowledged results;
- distinguish confirmed server state from an offline display.

Practical assessment:

1. Accept a named handover.
2. Identify a missing owner/location/next action.
3. Test temporary network loss and reconnect.
4. Escalate a recovery-capacity conflict.

## Reception and administration

Training outcomes:

- create referral episodes accurately;
- record owner communication, estimate, consent and insurance states within role permissions;
- import approved exports;
- resolve unmatched rows through reconciliation;
- avoid joining the wrong patient or episode;
- understand which fields must remain in the source PIMS.

Practical assessment:

1. Create and validate a referral.
2. Import one valid and one invalid row.
3. Demonstrate that unresolved imports cannot commit.
4. Correct an identity mismatch through reconciliation.

## Imaging and laboratory teams

Training outcomes:

- understand signed integration messages and service-state changes;
- verify unmatched study/result handling;
- preserve corrected result provenance;
- recognise critical-result acknowledgement ownership;
- report vendor or integration degradation.

Practical assessment:

1. Process a valid signed sample event.
2. Demonstrate rejection of an invalid signature and replay.
3. Process a corrected result without deleting the first result.
4. Mark a service degraded and verify downstream constraints.

## Governance, privacy and security roles

Training outcomes:

- use `/production-readiness` as the go/no-go record;
- understand category-specific approval authority;
- review evidence, expiry and waivers;
- run the security assessment and deployed security probe;
- manage DPIA, retention, incident and penetration-test evidence;
- ensure “passed” means reviewed evidence exists, not that a document was uploaded.

Practical assessment:

1. Add evidence to a readiness control.
2. Reject a stale readiness decision.
3. Show that an operations role cannot pass the DPIA or penetration-test control.
4. Demonstrate that open red observations block progression.
5. Review an expired control and return it to blocked status.

## Training evidence

Completion evidence should include:

- user identity and role;
- course/version date;
- practical scenarios attempted;
- assessor;
- outcome and remediation;
- acknowledgement of the clinical-decision boundary;
- acknowledgement of incident and rollback duties.

Upload the approved completion report against `users.training` in `/production-readiness`. Training completion alone does not authorise live use.
