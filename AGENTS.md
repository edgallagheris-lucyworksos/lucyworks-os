# AGENTS.md — LucyWorksOS Agent Instructions

## Product rule

LucyWorksOS is one hospital operating system.

Do not treat it as separate apps, a demo, a SaaS launchpad, a chatbot wrapper, or a loose dashboard.

Canonical names:

- LucyWorksOS = whole hospital operating system
- LucyFlow = intake, triage, routing, handoff
- LucyPulse = pressure, risk, workload, alerts
- LucyRota = rota, staffing, skills, availability, load
- LucyWorksAI = optional AI assistance inside the workflow, not source of truth
- LucySafe = safety, ethics, escalation, safeguarding, override layer

Do not rename the system or invent replacement module names.

## Build priority order

Always work in this order:

1. Make the repo run.
2. Make tests/checks pass.
3. Fix backend imports/models.
4. Connect data to actual operational objects.
5. Improve `/hospital-board` as the primary system surface.
6. Only then polish styling.

Do not start with visual polish while startup, imports, tests, or backend routes are broken.

## Required commands

Primary run command:

```bash
bash RUN_LUCYWORKSOS.sh
```

Proof command:

```bash
npm run check
```

Development fallback:

```bash
npm run dev
```

## Runtime rules

- Use Python 3.12.x.
- Prefer 3.12.13 when configuring Codespaces.
- Do not leave the repo depending on Python 3.14 behaviour.
- If branch has no upstream tracking branch, runner must warn and continue safely rather than dying.
- Runner must print backend/frontend links clearly.

## Backend rules

Before changing frontend, ensure backend imports cleanly.

Must not leave:

- `ModuleNotFoundError`
- route imports to missing files
- SQLModel/Pydantic import crashes
- missing smoke tests for new route modules

All user-facing operations must create/update real system objects:

- Patient
- Episode
- TriageAssessment
- WorkItem
- StaffMember
- Shift
- ScheduleBlock
- RoomState
- PharmacyRequest
- ResultReview
- OwnerCommsRequirement
- Blocker / EthicsFlag
- AuditEvent

No decorative-only actions.

## Hospital-board rules

`/` must redirect to `/hospital-board`.

`/hospital-board` is the primary operating surface.

It must answer:

- What is happening now?
- Where is it happening?
- Who owns it?
- What is blocked?
- What is next?
- What is unsafe?
- What rooms/staff are under pressure?
- What will be delayed?

Use a control-room layout:

- 15-minute time axis
- department / room lanes
- patient / episode identity
- owner role
- urgency
- blocker / dependency / handoff state
- red/amber/green pressure
- staff and pharmacy/imaging/ICU pressure

Avoid primary UI made of launch cards, marketing panels, empty module tiles, or vague labels.

## Testing rules

When making changes, run the most relevant available checks.

Minimum before declaring done:

```bash
npm run check
```

If unable to run because of environment/network restriction, state the exact blocker and what was validated instead.

## Output rule

Final PR/commit summary must include:

- files changed
- commands run
- pass/fail for `bash RUN_LUCYWORKSOS.sh`
- pass/fail for `npm run check`
- remaining blockers

Do not claim the system works unless the relevant command actually passed.
