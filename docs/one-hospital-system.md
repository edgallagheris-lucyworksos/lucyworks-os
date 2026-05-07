# LucyWorksOS — One Hospital System

## Rule

LucyWorksOS is one hospital operating system.

Do not describe the build as separate systems. Do not split the product into disconnected apps. Do not treat OpenAI Platform, GitHub, Codespaces, LucyFlow, LucyPulse, LucyRota or LucyWorksAI as separate products.

They are tools, layers, modules or capabilities inside one system.

## Correct wording

Use:

```text
LucyWorksOS
LucyWorksOS v3 Vet Version
one hospital operating system
one backend
one database
one operational board
one workflow engine
```

Avoid:

```text
separate system
another app
different product
DCVet unless supplied by user
LucyVet as replacement name unless supplied by user
```

## Mental model

LucyWorksOS is:

```text
one live hospital database
+ one workflow engine
+ one 15-minute hospital board
+ one case/timeline/audit layer
+ one staff/rota/load layer
+ one pharmacy/governance layer
+ optional AI assistance inside the same workflow
```

## OpenAI Platform role

OpenAI Platform is not a separate Lucy system.

It is an optional developer/service layer used inside LucyWorksOS for:

- intake parsing
- triage assistance
- handover summaries
- owner-comms drafting
- delay/ripple explanations
- structured extraction from messy text

Backend rules still decide.
Audit still records.
The hospital workflow engine remains the source of truth.

## Build rule

Every feature must attach to one of these core operational objects:

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

If it does not attach to the core system, it is not part of the build.

## Frontend rule

The frontend is not the system.

The frontend is the control surface for the one system.

Primary views:

- Hospital Board
- My Work
- Case Timeline
- Department View
- Exceptions
- Input / Capture
- System Admin

## User benefit rule

Every page must reduce one of these:

- asking the clinical director
- duplicated handovers
- missed owner updates
- missed results
- unsafe transitions
- unclear ownership
- room/person conflicts
- pharmacy/governance mistakes
- delay ripple confusion

If it does not reduce one of those, it should not be built.
