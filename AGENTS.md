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

## Codex Context Lock Protocol

Codex must lock the repo context before editing.

This means: extract the current repo truth, state what is confirmed, state what is not confirmed, then build against that truth only.

### Step 0 — Read controls first

Before changing files, read:

```text
AGENTS.md
GitHub issue #14
package.json
RUN_LUCYWORKSOS.sh
run_lucyworksos.sh
scripts/run-dev.sh
scripts/check-all.sh
.devcontainer/devcontainer.json
.python-version
backend/requirements.txt
backend/app/models.py
backend/app/database.py
backend/app/main.py
backend/app/main_fixed.py
backend/app/v3_operational_routes.py
backend/app/dashboard_routes.py
frontend/app/page.tsx
frontend/app/hospital-board/page.tsx
frontend/components/hospital-shell.tsx
frontend/app/globals.css
```

### Step 1 — State confirmed reality

Before editing, Codex must output:

```text
CONFIRMED:
- current branch
- upstream state
- Python version
- package scripts
- backend entrypoint
- frontend entrypoint
- current failing command/error
- primary board route

NOT CONFIRMED:
- anything not inspected or tested
```

### Step 2 — No invention rule

Do not invent names, architecture, or modules unless they map to existing LucyWorksOS objects.

Allowed canonical names only:

```text
LucyWorksOS
LucyFlow
LucyPulse
LucyRota
LucyWorksAI
LucySafe
```

### Step 3 — Locked build passes

Work in this order only:

```text
PASS 1: Runtime / runner
PASS 2: Backend imports / SQLModel models
PASS 3: Smoke tests / npm run check
PASS 4: Hospital-board operating-system behaviour
PASS 5: Real seed data / schedule / room / staff state
PASS 6: Styling and polish
```

Do not jump to UI polish while runtime/tests/imports are broken.

### Step 4 — Every claim needs proof

Final claims require command evidence:

```bash
python --version
npm run check
bash RUN_LUCYWORKSOS.sh
```

If a command cannot run due environment/network limits, state the exact blocker.

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

If unable to run because of environment restriction or package-network restriction, state the exact blocker and what was validated instead.

## Output rule

Final PR/commit summary must include:

- files changed
- commands run
- pass/fail for `bash RUN_LUCYWORKSOS.sh`
- pass/fail for `npm run check`
- remaining blockers

Do not claim the system works unless the relevant command actually passed.
