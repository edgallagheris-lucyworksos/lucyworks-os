# DCVet / LucyWorksOS v3 — Source Extraction

This file captures the working system pattern from the pasted single-file DCVet/LucyWorksOS v3 source.

## Why this matters

The pasted system is closer to the original intent than the current fragmented frontend-heavy build.

It is:

- single server first
- database first
- phone first
- zero config
- SQLite persistence
- HTML UI and JSON API in one app
- YAML triage rules
- ethics/audit logging
- staff assignment
- pharmacy governance

The current repo must be corrected toward this pattern: backend machine first, UI as a control surface second.

## Source pattern

```text
python main.py
-> FastAPI server
-> SQLite database
-> Jinja2 HTML dashboard
-> JSON API
-> triage YAML auto-written on first run
-> templates/static auto-written on first run
```

## Key operating objects from DCVet v3

### Staff

Fields:

- staff_key
- name
- role
- skills
- on_shift
- active_cases
- created_at

Purpose:

- represents usable staff capacity
- supports skill matching and case assignment
- keeps active load visible

### Case

Fields:

- case_id
- species
- signalment
- presenting_problem
- symptoms_text
- pain_score
- repeat_sedation_6mo
- consent_obtained
- financial_constraint
- urgency
- confidence
- handoff
- triage_reasons
- triage_actions
- ethics_flags
- assigned_staff_id
- created_at

Purpose:

- the core case/patient intake object
- creation automatically runs triage
- RED cases force handoff
- ethics flags are written immediately

### CaseEvent

Fields:

- case_id
- note
- created_at

Purpose:

- simple timeline/event log for the case
- proves that each case needs an event stream, not just a dashboard row

### AuditEvent

Fields:

- event_id
- trigger
- action
- reason
- case_id
- meta_json
- created_at

Purpose:

- records ethics, handoff, assignment, governance and hard-stop decisions
- must be first-class in the rebuilt system

### PharmaOrder

Fields:

- order_id
- staff_key
- value_gbp
- followed_protocol
- created_at

Purpose:

- proves pharmacy/governance is not decorative
- high-value order without protocol creates audit event

## Key engines from DCVet v3

### YAML triage engine

Uses `config/triage_rules.yaml`.

Rules support:

- species-specific routing
- RED/AMBER/GREEN urgency
- handoff mode
- reason list
- action list
- ethics flags
- low confidence forced vet review
- RED forced handoff

Important default rules:

- collapse/unresponsive -> RED handoff required
- blocked cat -> RED handoff required
- suspected GDV -> RED, theatre hold / emergency consent
- neuro emergency -> RED, MRI slot hold
- vomiting + lethargy -> AMBER vet review / labs

### Ethics engine

Flags:

- REPEAT_SEDATION
- CONSENT_GAP
- FINANCIAL_CONSTRAINT

Important behaviour:

- consent gap becomes hard stop
- financial constraint triggers senior vet review
- repeat sedation triggers review/escalation

### Staff assignment engine

Uses:

- required skills
- staff skills
- active cases
- on-shift status

Behaviour:

- prefers vets
- least loaded
- minimum skill overlap gate
- assignment failure creates audit

### Pharmacy governance engine

Rule:

- if order is £5,000+ and protocol not followed -> MEDICINES_GOVERNANCE_BREACH audit event

## UI pattern from DCVet v3

The UI is simple but functional:

- create case form
- latest active cases
- ethics/audit feed
- pharmacy governance order form
- staff on shift list
- case detail page
- case timeline notes
- assign case by required skills

This is better than a polished empty app because every UI form writes to the database and every important decision creates audit.

## API pattern from DCVet v3

Endpoints:

- GET `/api/cases`
- GET `/api/audit`
- POST `/api/triage`

Minimum required rebuilt equivalents:

- POST `/api/cases`
- GET `/api/cases`
- GET `/api/cases/{case_id}`
- POST `/api/cases/{case_id}/events`
- POST `/api/cases/{case_id}/assign`
- POST `/api/triage/preview`
- GET `/api/audit`
- POST `/api/pharmacy/orders`

## What must be merged into lucyworks-os

### Immediate corrections

1. Bring back the simple working dashboard pattern as a functional fallback.
2. Build case creation around automatic triage.
3. Write audit events for:
   - RED triage
   - consent gap
   - assignment failure
   - assignment success
   - pharmacy governance breach
4. Keep YAML triage rules as editable config.
5. Make staff assignment skill/load based.
6. Make the UI form-first and database-backed, not decorative.

### Relationship to the bigger hospital board

DCVet v3 is not the final BVS/CVS hospital board, but it is the working seed.

It gives the minimum working spine:

```text
case intake
-> triage
-> ethics flags
-> staff assignment
-> timeline/audit
-> pharmacy governance
```

The wider hospital system should extend that into:

```text
15-minute hospital board
-> room/person/team events
-> workflow transitions
-> blockers
-> downstream delay ripple
```

## Build rule from here

No frontend page should be accepted unless it has:

- database object
- create/read/update endpoint
- audit behaviour where relevant
- visible form/list view
- smoke test

DCVet v3 proves a small working system is better than a broad non-working one.
