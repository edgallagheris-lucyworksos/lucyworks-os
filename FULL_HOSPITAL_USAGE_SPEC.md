# LucyWorks OS — Full Hospital Usage Specification

LucyWorks OS is a specialist veterinary hospital operating system. It is not a checklist app and not a generic dashboard. The purpose is to make complex hospital flow visible, owned, auditable and safer under pressure.

This specification is the working product backbone. The current build should be judged against this document.

---

## 1. Core operating principle

Every operational object must connect into this spine:

```text
Patient → Owner → Episode → Location → Team → Decision → Action → Escalation → Audit
```

No module should exist in isolation. Triage, rooms, rota, pharmacy, stock, discharge, comms and theatre all need to connect back to the live episode and accountable owner.

---

## 2. Hospital context

LucyWorks OS is designed for a high-throughput specialist referral hospital with:

- Emergency and critical care
- Multiple theatres
- ICU and wards
- Diagnostic imaging
- Specialist medicine
- Neurology
- Orthopaedics
- Soft tissue surgery
- Dentistry / oral surgery
- Pharmacy and stock control
- Reception / client care / admin
- Discharge and owner communication flow
- Out-of-hours and on-call pressure

The system must support hundreds of staff, multiple concurrent cases and high-risk handoffs.

---

## 3. User roles

### Clinical Director / Ops Manager

Needs:

- Whole-hospital pressure view
- Red alerts
- Unowned work
- Section pressure
- Room/staff conflicts
- Escalation ownership
- Audit trail
- Throughput bottlenecks
- Ability to trigger cross-domain automation

### Specialist / Clinician

Needs:

- Assigned cases
- Decisions requiring clinician signoff
- Results requiring review
- Owner updates needing clinical accuracy
- Pharmacy and controlled/cascade medication flags
- Procedure readiness and risk
- Episode command view

### Nurse / Technician

Needs:

- Case task list
- Care tasks
- Prep/recovery handoffs
- Medication tasks
- Room state
- Stock blockers
- Discharge readiness tasks
- Escalation route if blocked

### Reception / Admin / Client Care

Needs:

- Owner communication state
- Estimate/insurance/admin readiness
- Written prescription/admin requests
- Discharge appointment/admin blockers
- Message threads linked to episode

### Pharmacy / Stock Lead

Needs:

- Medication requests
- Controlled/legal/cascade status
- Low-stock alerts
- Cold-chain visibility
- Authorised supplier notes
- Discharge medication blockers
- Audit of completion

---

## 4. Main modules

### Lucy Pulse

Whole-hospital pressure layer.

Must show:

- System risk level
- Dominant pressure source
- Case pressure
- Resource pressure
- Staff pressure
- Capacity pressure
- Execution pressure
- Ethics pressure
- Triage pressure
- Owner-comms pressure
- Next action route

Pulse should not just count things. It should interpret what pressure means and where the operator should go next.

### Command

Whole-hospital command surface.

Must show:

- Hospital control state
- Priority board
- Lead item
- Highest-pressure section
- Unowned work
- Red work
- Section pressure
- Domain pressure
- Cross-domain automation controls
- Next action link

Command should turn noise into accountable action.

### Episode Command

Case-level command surface.

Must show:

- Patient
- Owner
- Episode reference
- Current phase
- Current section/room
- Flow readiness
- Hard blockers
- Warnings
- Next action
- Next owner role
- Triage signals
- Ethics flags
- Decisions
- Blockers
- Escalations
- Care tasks
- Owner comms requirements
- Discharge readiness
- Pharmacy requests
- Stock orders
- Results
- Messages
- Timeline controls
- Staff allocation
- Audit-relevant state

Episode Command is the case brain.

### LucyFlow

Triage/intake layer.

Must capture:

- Species
- Presenting signs
- Red flags
- Urgency
- Route
- Confidence
- Handoff requirement
- Ethics trigger
- Owner communication requirement
- Decision requirement
- Assigned role

It should create work/decision/ethics signals where needed.

### Lucy Ethics

Welfare, consent and risk layer.

Must capture:

- Flag type
- Severity
- Clinical reasoning
- Owner state
- Financial constraint
- Consent problem
- Safeguarding/welfare concern
- Decision required
- Escalation path
- Resolution note

### Lucy Care

Care continuity layer.

Must capture:

- Care area
- Task type
- Detail
- Owner role
- Status
- Escalation requirement
- Completion time

Examples:

- Pain scoring
- Fluid checks
- Feeding
- Toileting
- Mobility
- Medication
- Observation
- Recovery monitoring

### Schedule / Theatre Chain

Must model procedure as linked blocks:

```text
Prep → Anaesthesia → Procedure → Recovery → Cleaning
```

Each block should have:

- Episode
- Case procedure
- Room
- Owner role
- Assigned staff
- Start time
- End time
- Status
- Conflicts

Timing changes should cascade through later blocks.

### Rooms

Must show current state of rooms across:

- Consults
- Emergency
- Wards
- ICU
- Theatre
- Recovery
- Imaging
- Pharmacy / stock locations

Room states:

- available
- occupied
- cleaning
- blocked
- offline

### Staff / Rota

Must support:

- Staff role
- Skills
- Shift state
- Active blocks
- Assignment conflicts
- On-shift availability
- Role pressure
- No-overlap enforcement
- On-call / out-of-hours handling later

### Pharmacy

Must support:

- Medication name
- Quantity
- Episode link
- Urgency
- Status
- Owner role
- Controlled/legal status
- Compliance note
- Discharge medication readiness
- Audit completion

### Stock

Must support:

- Stock item
- Category
- Location
- Quantity
- Reorder threshold
- Supplier
- Compliance note
- Low-stock pressure
- Stock orders
- Episode-linked blockers

### Discharge

Must support:

- Clinician signoff
- Medication ready
- Owner updated
- Admin ready
- Results reviewed
- Care instructions ready
- Blocker summary
- Readiness state
- Urgency
- Owner role

Patient should not be marked ready until these are aligned.

### Mail Ops / Owner Comms

Must support:

- Thread per owner/case issue
- Message entries
- Inbound/outbound direction
- Material decision flag
- Owner comms requirement
- Audit trail

Owner communication that affects consent, cost, discharge, euthanasia, risk, medication or treatment direction is material.

### Conflicts

Must detect:

- Room overlaps
- Staff overlaps
- Role overlaps
- Cleaning chain conflicts
- Pending result review
- Unacknowledged handover
- Red work
- Blocked discharge
- Ethics flags
- Triage pressure

Conflicts should convert into work.

### Audit

Must record material events:

- Work created
- Work assigned
- Work status change
- Room state change
- Message created
- Triage created/resolved
- Ethics created/resolved
- Pharmacy request completed
- Stock order completed
- Discharge readiness updated
- Schedule generated/shifted
- Staff allocated

---

## 5. Department and room model

Departments and rooms should be loaded from the operating catalogue and eventually made editable in admin.

Current required departments:

- Emergency and Critical Care
- Surgery / Soft Tissue
- Orthopaedics
- Neurology
- Internal Medicine
- Diagnostic Imaging
- Dentistry / Oral Surgery
- Pharmacy and Stock Control

Each department must define:

- Purpose
- Rooms
- Roles
- Specialisms
- Common blockers

---

## 6. Procedure timing model

Procedure templates must define:

- Name
- Department
- Prep minutes
- Anaesthesia minutes
- Procedure minutes
- Recovery minutes
- Cleaning minutes
- Risk/guardrail note

These are operational planning timings, not clinical guarantees.

Timing templates should drive schedule generation and help detect capacity problems.

---

## 7. Pharmacy and medicines governance

LucyWorks must surface guardrails for:

- Prescribing authority
- Cascade prescribing
- Controlled drugs
- Antimicrobial stewardship
- Cold chain
- Written prescriptions
- Discharge medication

The system must not replace veterinary judgement. It should route, flag, record and escalate.

---

## 8. Compliance guardrails

The system should surface operational guardrails. Final compliance wording must be checked against current:

- RCVS guidance
- VMD rules
- practice SOPs
- corporate governance
- controlled drug procedures
- data protection policy

Minimum product rule:

```text
If it affects treatment, owner consent, cost, discharge, medication, welfare or risk, it must be visible and auditable.
```

---

## 9. Full patient journey

### Entry

- Intake / triage
- Owner details
- Presenting signs
- Urgency
- Route
- Red flags

### Admission / assessment

- Episode created
- Location assigned
- Owner role assigned
- Decisions created
- Results/tasks triggered

### Diagnostics / treatment

- Imaging/labs/procedure scheduled
- Room and staff assigned
- Conflicts checked
- Pharmacy/stock blockers checked

### Procedure / ward / ICU

- Prep
- Anaesthesia
- Procedure
- Recovery
- Monitoring
- Care tasks
- Handover

### Discharge

- Clinician signoff
- Meds ready
- Owner updated
- Admin ready
- Results reviewed
- Instructions ready

### Closure

- Episode state updated
- Audit trail complete
- Remaining tasks closed or escalated

---

## 10. Build priorities from here

1. Catalogue must feed scheduling, not only display.
2. Pharmacy catalogue/drug governance must feed medication requests.
3. Flow-readiness must include operating catalogue guardrails.
4. Roles/specialisms must drive staff assignment.
5. Rooms must be linked to department capacity.
6. Procedure template selection must drive schedule block generation.
7. Episode Command must show the full patient journey state.
8. Audit must continue expanding.
9. Replace seeded examples with configurable hospital data.
10. Build admin/config surfaces for hospital-specific setup.
