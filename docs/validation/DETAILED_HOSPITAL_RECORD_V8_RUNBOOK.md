# LucyWorks v8 detailed hospital record validation

## Purpose

This release creates a governed longitudinal referral-hospital record. It joins patient and owner identity, clinical history, medication safety, anaesthesia, inpatient care, procedures, estimates, insurance, financial transactions, communications and generated documents to one canonical episode.

The release does not replace hospital approval, a licensed veterinary formulary, an accredited PIMS, a payment provider or a regulated controlled-drug process. All local policies and vendor integrations must be configured and validated before live use.

## Main surface

- `/patient-record`
- API prefix: `/api/v8`
- Migration head: `0009_detailed_hospital`

## Patient identity and ownership

1. Create or import the patient with a stable patient reference.
2. Confirm species, breed, sex, neuter status, date of birth and microchip.
3. Create the owner account separately.
4. Verify owner identity according to local policy.
5. Record whether the owner has clinical decision authority and financial responsibility.
6. Do not use a patient name or owner name as a stable identifier.
7. Test transfer of ownership, joint ownership and disputed authority before production use.

## Clinical record

1. Record a current weight before any weight-based medication review.
2. Record active problems separately from consultation prose.
3. Record allergies with substance, reaction, severity and confirmation state.
4. Create encounters for consultation, ward round, emergency review and procedure review.
5. Sign clinical notes rather than silently editing them.
6. Correct signed notes by creating a superseding note and preserving the original.
7. Test chronological rendering with multiple episodes and long admissions.

## Medication and formulary safety

1. Load only locally approved formulary medicines and dose rules.
2. Every dose rule must identify species, indication, route, source and approval state.
3. Confirm that no-current-weight blocks the safety review.
4. Confirm active allergy matches create a red block.
5. Confirm no approved species/route/indication rule creates a red block.
6. Test lower and upper mg/kg limits, maximum single dose and minimum interval.
7. Map local renal and hepatic adjustment procedures.
8. Validate interactions and contraindications using an approved veterinary medicines source.
9. Do not treat a passed automated review as a prescription or clinical decision.

## Anaesthesia

1. Complete pre-anaesthetic assessment and machine/equipment checks.
2. Record ASA status, airway, analgesia and ventilation plans.
3. Validate local alert thresholds for blood pressure, SpO2, ETCO2 and temperature.
4. Record observations at the hospital-defined interval.
5. Confirm red observations appear in durable live control.
6. Confirm high-risk or controlled medicines require a witness.
7. Validate induction, maintenance, ventilation, recovery and complication workflows against local protocols.
8. Confirm the printed/exported anaesthetic chart is clinically legible before pilot use.

## Inpatient care and fluid balance

1. Create a care plan for every admitted patient.
2. Set area, acuity, observation interval, nutrition and mobility requirements.
3. Record inputs, boluses, outputs and abnormal losses separately.
4. Confirm net balance calculations across handovers and midnight boundaries.
5. Test red and amber chart entries and escalation behaviour.
6. Validate urine-output, drain, feeding and body-weight trend requirements locally.

## Procedures and implants

1. Link the procedure to the canonical episode and, where available, the operating block.
2. Completed procedures require findings and technique.
3. Record team members, diagnoses, complications and specimens.
4. Every implant must carry a lot number or serial number.
5. Validate catalogue, manufacturer, expiry, implantation and explantation fields.
6. Test device recall searches across all patients.

## Estimates, insurance and payments

1. Store all amounts in integer pence and present them as GBP.
2. Create a new estimate version when scope or price changes.
3. Issued and approved estimates require owner-authorisation evidence.
4. Confirm lower and upper totals from individual line items.
5. Record insurer, masked policy number, excess, cover limit and preauthorisation.
6. Confirm potential shortfall against the current upper estimate.
7. Financial transactions are a ledger; never edit a posted payment in place.
8. Integrate with the hospital accounting/payment provider before live use.
9. Reconcile invoices, deposits, refunds, insurer payments and write-offs.

## Communications and documents

1. Record audience, channel, direction, subject, summary, outcome and time.
2. Record estimate consent and other owner authority as structured evidence.
3. Generate discharge summaries and referring-vet reports from the canonical record.
4. A clinician must review and approve generated content before sending.
5. Validate document layout, attachments, email delivery and failed-delivery handling.
6. Test owner communication preferences and reasonable-adjustment requirements.

## Required automated proof

Run:

```bash
cd apps/api
python detailed_hospital_v8_smoke_test.py
DATABASE_URL=sqlite:////tmp/lucyworks-v8.db AUTO_CREATE_SCHEMA=false alembic upgrade head
```

The GitHub v8 gate additionally verifies PostgreSQL migration and the production Next.js build.

## Historical and shadow validation

Before any live workflow:

1. Import anonymised past episodes containing consultations, anaesthesia, inpatient care, estimates and communications.
2. Reconstruct the expected chronological record.
3. Compare generated alerts with the actual hospital decisions.
4. Record false medication blocks and missed medication risks.
5. Record false anaesthetic alarms and missed physiological deterioration.
6. Compare fluid balance, implant trace and estimate versions with source records.
7. Run shadow mode with staff using the existing system as the legal record.

## External approval still required

- confirmed BVS patient and owner identity policy;
- approved local formulary and dose rules;
- local anaesthesia and inpatient protocols;
- controlled-drug process approval;
- PIMS, PACS, laboratory, pharmacy, insurer and payment integrations;
- document templates and communication standards;
- data-protection and retention approval;
- clinical safety case and hazard log;
- penetration testing;
- usability and accessibility testing;
- historical replay, shadow mode and bounded pilot approval.
