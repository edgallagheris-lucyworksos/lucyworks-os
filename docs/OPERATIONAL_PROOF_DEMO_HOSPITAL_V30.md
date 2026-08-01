# LucyWorks Operational Proof and Demo Hospital v30

## Purpose

V30 stops treating a completed module test as proof that LucyWorks behaves as one hospital operating system. It binds one canonical referral to a persistent proof run and evaluates the same episode across:

- referral intake and clinical acceptance;
- canonical patient and episode identity;
- triage and consult;
- owner authority and consent;
- placement on Hospital Today or explicit unplaced visibility;
- accountable handover and role queues;
- discharge readiness and communications;
- completed closure;
- board-change events;
- verified evidence attribution.

## Start the system in Codespaces

```bash
npm run codespace:run
```

Open the forwarded web port and use:

```text
/system-control
/operational-proof
```

The existing development runner remains:

```bash
npm run dev
```

## Run the complete automated proof

```bash
npm run proof:v30
```

This command runs:

1. the v30 static architecture audit;
2. the established canonical v9 referral-to-closure test;
3. the v30 board, queue and evidence propagation test;
4. the v30 authority and failure-boundary test;
5. the complete production web build.

## Connected journey contract

The proof records twelve named checks:

1. referral received and clinically accepted;
2. canonical patient and episode identity linked;
3. triage transition recorded;
4. clinical acceptance and consult recorded;
5. owner authority and consent gate satisfied;
6. operational block or explicit unplaced status visible;
7. accountable handover visible and acknowledged;
8. discharge readiness and communication gates satisfied;
9. episode closure completed;
10. canonical episode and changes visible on Hospital Today;
11. canonical work visible to the accountable role queue;
12. verified actor evidence exists across the journey.

A failed step records the observed state, root cause and corrective action. It is not suppressed or converted into a warning.

## Stress scenarios

Every run contains all eight Issue #65 failures:

- emergency insertion into a full schedule;
- theatre or imaging overrun;
- assigned staff member becomes unavailable;
- unacknowledged handover;
- overdue critical result review;
- discharge blocked by medication or owner communication;
- stale concurrent update;
- duplicate patient identity candidate.

A scenario passes only when all of the following are recorded:

- the failure was detected;
- an accountable owner was visible;
- the next action was visible;
- evidence or audit state was visible;
- urgent patient access remained available.

## Mobile acceptance

The browser can measure:

- secure context;
- online state;
- viewport size;
- touch capability;
- microphone availability and permission;
- horizontal overflow.

Those checks cannot prove physical keyboard overlap, touch comfort or actual Android behaviour. The operator console therefore has a separate named confirmation for the physical journey:

```text
Login
→ Quick Input
→ create patient-linked work
→ find it in Patient Command or Workspace
→ perform an action
→ refresh
→ confirm persistence
→ confirm named audit attribution
```

Without that confirmation a successful run is recorded as:

```text
passed_with_manual_boundary
```

It is not recorded as fully passed.

## Evidence status

The operator report uses:

- `pass` — the check was observed and evidenced;
- `partial` — reserved for an explicitly incomplete but usable result;
- `blocked` — the required connected behaviour was not observed;
- `passed_with_manual_boundary` — automated proof passed but physical Android confirmation remains outstanding.

## Safety and deployment boundary

V30 does not:

- prescribe or authorise medication doses;
- sign clinical records autonomously;
- write to external vendor systems;
- treat synthetic identity data as a canonical patient;
- mark the hospital ready merely because automated proof passes.

Real deployment still requires hospital-specific OIDC, PIMS/PACS/laboratory schemas, vendor sandboxes, DPIA, penetration testing, governance approval, physical-device acceptance and bounded hospital UAT.
