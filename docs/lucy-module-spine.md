# LucyWorks OS — Lucy Module Spine

This is the product spine. Do not rename these into generic sections.

## Core Lucy modules

1. Lucy Command
   - Clinical Director / ops command surface.
   - Pulls from Pulse, Flow, Rota, Care, Ethics, Theatre, Ward, Pharmacy, Finance, Mail Ops and Audit.

2. Lucy Pulse
   - Live operational health layer.
   - Queue pressure, delay pressure, room pressure, staffing pressure, discharge pressure, pharmacy pressure, imaging pressure, ward/ICU pressure, unowned items.

3. Lucy Flow
   - Intake, triage, routing, urgency, escalation and handoff.
   - From first contact to correct owner/section/action.

4. Lucy Ethics
   - Safeguard and decision-risk layer.
   - Welfare, pain, consent, repeat sedation, financial constraint impact, neglect/safeguarding, clinical pressure risk.

5. Lucy Care
   - Admission-to-discharge continuity.
   - Prep, procedure, recovery, ward, ICU, overnight, observations, meds due, owner update, discharge readiness, follow-up.

6. LucyRota
   - Staffing, HR and safe coverage layer.
   - Skills matrix, shift model, on-call, leave, absence, overtime, competency, fatigue/rest risk, assignment fit.

7. Lucy Theatre
   - Theatre and procedure chain.
   - 15-minute grid, prep, anaesthesia, procedure, recovery, cleaning/turnover, sterility windows, overruns, staffing fit.

8. Lucy Ward
   - Ward, ICU and inpatient board.
   - Bed/kennel/bay occupancy, overnight carry-over, q30/q60 obs, meds due, handovers, morning review, discharge blockers.

9. Lucy Diagnostics
   - Imaging/lab/results layer.
   - MRI, CT, X-ray, ultrasound, lab result lifecycle, review owner, overdue result, owner update required.

10. Lucy Pharmacy
   - Formulary, stock, pharmacy and medicine workflow visibility.
   - Restricted/controlled flags, cold-chain, locked storage, stock, ordering, discharge medication readiness.

11. Lucy Comms
   - Owner communication and internal coordination.
   - Owner updates, consent calls, estimate discussions, discharge calls, internal messages, unresolved threads.

12. LucyTrace
   - Audit/governance layer.
   - Actor, action, timestamp, old/new state, override reason, decision history, access logs, hash-linked trace.

## Supporting but product-visible surfaces

- Mail Ops: operational email ingestion and routing.
- Personal Layer / My Workspace: every staff member's own action queue.
- Readiness: internal BVS/CVS system gap checker.
- Catalogues: procedure/formulary/diagnostic source data.

## Current implementation mapping

- Lucy Command -> /command and /dashboard
- Lucy Pulse -> /pulse plus /forecast once built
- Lucy Flow -> /triage and flow-state routes
- Lucy Ethics -> /ethics and ethics flags
- Lucy Care -> /overnight, /discharge, /ward, /actions
- LucyRota -> /hr, /staff, /schedule, workspace staff-risk queues
- Lucy Theatre -> /theatre, /schedule, schedule blocks and live-action starts
- Lucy Ward -> /overnight and ward/inpatient queues
- Lucy Diagnostics -> /catalogues diagnostics, result reviews, pending result queues
- Lucy Pharmacy -> /pharmacy, /stock, formulary catalogue and pharmacy task gates
- Lucy Comms -> /mail, /actions owner comms, message threads
- LucyTrace -> /audit, AuditEvent, future hash-linked trace
