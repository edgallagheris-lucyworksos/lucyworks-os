# LucyWorksOS — Canonical Naming Register

## Rule

LucyWorksOS is one hospital operating system.

The names below are not separate products. They are canonical system-family names, modules, layers or capabilities inside the one LucyWorksOS hospital system.

## Canonical system-family names

These names are locked as supplied in-thread:

- LucyWorks
- LucyOS
- LucyVet
- LucyFlow
- LucyPulse
- LucyRota
- LucyWorksAI

Additional named layer referenced in-thread:

- LucySafe

## Meaning

### LucyWorks
Parent family / operating-system concept.

### LucyOS
System-level OS wording. Use only when referring to the overall operating layer.

### LucyVet
Vet-hospital domain layer inside LucyWorksOS. Do not use as a replacement product name if LucyWorksOS is the parent context.

### LucyFlow
Intake, triage, routing, handoff and case-flow layer.

### LucyPulse
Operational pressure, monitoring, alerts, stress, load, capacity and live risk layer.

### LucyRota
Staffing, rota, skill match, assignment, shifts, on-call, load and availability layer.

### LucyWorksAI
AI assistance inside LucyWorksOS. It may assist with parsing, summarising, extraction and recommendations, but it is not the source of truth.

### LucySafe
Safety / escalation / ethical override layer. Authority to close escalations remains an unresolved blocker until specified.

## Naming restrictions

Do not invent or substitute names such as:

- Lucy SFX
- DC rep
- separate Lucy app names
- generic labels that replace canonical names without mapping

Do not describe these as disconnected systems.

Correct phrasing:

```text
LucyWorksOS uses LucyFlow, LucyPulse, LucyRota, LucyWorksAI and LucySafe as internal layers of one hospital operating system.
```

Incorrect phrasing:

```text
These are separate systems.
```

## Build mapping

Every module must attach to the one shared backend and database.

Core objects:

- Episode / Case
- Patient
- WorkItem / Task
- StaffMember / Shift
- ScheduleBlock / 15-minute event
- RoomState
- ResultReview
- PharmacyRequest
- OwnerCommsRequirement
- Blocker / EthicsFlag
- AuditEvent

## Authority notes

Still unresolved and must not be guessed:

1. Who has authority to close LucySafe escalations?
2. Is LucyPulse advisory or blocking for LucyRota decisions?
3. What is the precedence chain when LucyFlow and LucyWorksAI disagree?

These are blockers, not optional comments.
