# AGENTS.md — LucyWorksOS Agent Instructions

## Product rule

LucyWorksOS is one professional-grade hospital operating system.

Do not treat it as separate apps, a demo, a SaaS launchpad, a chatbot wrapper, a toy intake form, or a loose dashboard.

Canonical names:

- LucyWorksOS = whole hospital operating system
- LucyFlow = intake, triage, routing, handoff
- LucyPulse = pressure, risk, workload, alerts
- LucyRota = rota, staffing, skills, availability, load
- LucyWorksAI = optional AI assistance inside the workflow, not source of truth
- LucySafe = safety, ethics, escalation, safeguarding, override layer

Do not rename the system or invent replacement module names.

## Mandatory continuation rule

At the start of every LucyWorksOS coding session, read these files before making changes:

1. `docs/LUCYWORKS_SYSTEM_CONTRACT.md`
2. `docs/LUCYWORKS_CONTINUE_HERE.md`
3. `apps/web/lib/day-control-work.ts`
4. `apps/web/lib/day-control-views.ts`
5. `apps/web/components/day-control-grid.tsx`

The current frontend source of truth is the generated 15-minute day-control schedule in:

```text
apps/web/lib/day-control-work.ts
```

Department views must use:

```text
apps/web/lib/day-control-views.ts
```

Do not build any new module that invents a separate work model.

## Professional-grade standard

A change is not good enough if it only makes the UI look better.

LucyWorksOS must behave like a real hospital operations system for a specialist referral hospital.

Minimum professional system capabilities:

1. **Single source of truth**
   - one backend
   - one database
   - one workflow engine
   - one hospital board
   - one audit/governance trail
   - one generated 15-minute schedule model until backend persistence replaces it

2. **Real operational entities**
   Every visible item must map to real backend or generated schedule objects:
   - Patient / subject
   - Episode / visit
   - Arrival
   - Consult
   - Admission
   - Insurance/admin step
   - Client/owner communication requirement
   - ProcedureTemplate
   - ScheduledCase
   - ScheduledWorkBlock
   - WorkItem
   - StaffMember
   - Shift
   - Staff skill / role requirement
   - Resource / room state
   - Pharmacy/supply request
   - Result review
   - Blocker / ethics flag
   - AuditEvent

3. **Hospital-scale structure**
   The board must account for:
   - Reception / intake
   - Arrival times
   - Consult times
   - Consent / estimates / insurance
   - Client or owner communication
   - Triage / consult / decision ownership
   - Imaging: MRI, CT, X-ray, ultrasound
   - Procedure rooms: prep, anaesthesia, procedure, recovery, cleaning / turnover
   - Ward / ICU / care area
   - Pharmacy / stock / medicines governance
   - Discharge / updates / collection
   - Staff / rota / skills / availability / load
   - Breaks / welfare / thin cover
   - Safety / ethics / escalation / audit

4. **Time-and-resource operating model**
   The primary board must be based on:
   - 15-minute time slots
   - rooms / departments / lanes
   - active cases
   - assigned staff and owner roles
   - blockers and dependencies
   - handoffs and next actions
   - red / amber / green pressure
   - generated blocks from procedure templates

5. **Automation first**
   Procedure templates must generate the required work chain:
   - prep
   - room/resource slot
   - staff role requirements
   - main procedure/workup
   - recovery/handover
   - client/contact update
   - decision check

6. **No decorative-only actions**
   Buttons and screens must create, update or inspect system state.
   No empty feature panels.
   No fake cards that are not attached to the operating model.

7. **Clinical-safety posture**
   AI may assist but must not be the source of truth.
   Hard rules, audit and human authority decide.

## Build direction from here

The next build work must continue in this order unless the user explicitly changes priority:

1. Convert department pages to `day-control-views.ts`.
2. Add local action persistence for `ScheduledWorkBlock` changes.
3. Add backend persistence for scheduled blocks and audit events.
4. Add arrivals, consults, insurance/admin and reception queues to the generated model.
5. Add conflict detection for resources, staff skills, late updates, missed breaks and overrun work.
6. Add voice-to-work capture that creates or updates scheduled blocks.
7. Add patient/subject timeline views from the same block model.

## Hard rule

If a change creates another disconnected board, dashboard, fake module or separate source of truth, it is wrong.

LucyWorksOS must remain one generated hospital operating model with multiple filtered views.
