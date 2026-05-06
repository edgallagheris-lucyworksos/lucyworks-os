# LucyVet OS Department Detail Pack

This document defines the operational department layer for a BVS/CVS-style specialist veterinary hospital system. It feeds Lucy Command, Lucy Pulse, Lucy Flow, Lucy Care, LucyRota, Lucy Theatre, Lucy Ward, Lucy Diagnostics, Lucy Pharmacy, Lucy Comms and LucyTrace.

## Reception / Intake

### Purpose
Creates and coordinates incoming operational flow.

### Specialists / staff involved
- Reception staff
- Referral coordinators
- Duty clinician for urgent escalation

### Key entities
- Incoming contact
- Referral
- Appointment
- Case intake
- Owner communication
- Consult room
- Queue position

### Workflow states
- Contact received
- Referral captured
- Case created
- Awaiting triage
- Booked
- Arrived
- Waiting
- Handed to clinical team

### Conflicts
- Wrong urgency
- Duplicate case
- Wrong owner details
- Delayed intake
- Consult room unavailable
- Unclear handover

### Dashboard needs
- Arrivals
- Consult room usage
- Waiting times
- Urgent arrivals
- Owner updates due

## Triage / Consult

### Purpose
Converts intake into clinical ownership and next-step direction.

### Specialists / staff involved
- Specialist Vet
- Consulting Nurse
- Duty / triage clinician

### Key entities
- Triage queue item
- Consult room
- Specialist
- Nurse support
- Case urgency
- Next required action

### Workflow states
- Awaiting triage
- In consult
- Awaiting diagnostics
- Awaiting treatment decision
- Sent to next stage

### Conflicts
- Triage backlog
- Room pressure
- Specialist unavailable
- No clear owner
- No next action

### Dashboard needs
- Queue by urgency
- Current consults
- Blocked consults
- Time in state

## Imaging

### Purpose
Provides MRI, CT, X-ray, ultrasound and related throughput.

### Specialists / staff involved
- Diagnostic Imaging Specialist
- Imaging Nurse
- Anaesthetist if sedation / anaesthesia required

### Key entities
- MRI suite
- CT suite
- Imaging room
- Imaging queue
- Result
- Reviewer

### Workflow states
- Requested
- Booked
- Waiting
- In scan
- Reporting
- Result returned
- Reviewed
- Actioned

### Conflicts
- Queue overflow
- Sedation delay
- Anaesthesia dependency
- Reviewer not assigned
- Unreviewed result
- Emergency scan jumps queue

### Dashboard needs
- Queue by urgency
- Slot utilisation
- Delayed scans
- Review SLA
- Downstream ownership

## Surgery / Theatre

### Purpose
Delivers scheduled and emergency procedures using theatres, anaesthesia, prep, recovery and specialist teams.

### Specialists / staff involved
- Specialist Surgeon
- Anaesthetist
- Theatre Nurse
- Recovery Nurse
- ICU clinician downstream

### Key entities
- Theatre
- Procedure room
- Prep area
- CaseProcedure
- ScheduleBlock
- CleaningBlock
- Equipment / implants

### Workflow states
- Waiting for theatre
- In prep
- Anaesthesia start
- Procedure in progress
- Recovery
- Cleaning
- Ready again

### Conflicts
- Anaesthetist double-booked
- Theatre not cleaned in time
- Procedure overruns
- Kit missing
- ICU bed not available
- Emergency add-on disrupts list

### Dashboard needs
- Live theatre board
- Start / expected end / actual end
- Overrun risk
- Cleaning state
- ICU destination pressure

## ICU

### Purpose
Handles highest-acuity inpatients requiring close monitoring, stabilisation and rapid escalation.

### Specialists / staff involved
- ICU / ECC clinician
- ICU nurse
- Anaesthetist downstream / upstream
- Referring specialist

### Key entities
- ICU bed group
- PatientStay
- Monitoring task
- Drug task
- Transfer task

### Workflow states
- Admitted
- Stable
- Unstable
- Escalated
- Transfer pending
- Discharged to ward
- Discharged from hospital

### Conflicts
- Bed full
- Monitoring overdue
- Transfer blocked
- Unsafe ratio
- Emergency admission with no capacity
- Recovery arrival with no ready bed

### Dashboard needs
- Census
- Bed occupancy
- Next observations due
- Critical alerts
- Transfer flow
- Staffing visibility
