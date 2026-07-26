# LucyWorks UK veterinary compliance and safety baseline v10

## Purpose

This release converts the legal, professional, privacy, security and safety-engineering baseline into executable assurance controls. It deliberately separates current obligations from future proposals and separates engineering validation from hospital deployment approval.

## Status classes

| Status | Treatment |
|---|---|
| `law_in_force` | Current legislation or regulator guidance describing present legal obligations. |
| `binding_professional_duty` | Current RCVS Code or supporting guidance applying to regulated professionals. |
| `draft_future_requirement` | CMA remedy or draft Order not yet in force on the baseline date. Implemented as future-ready product behaviour. |
| `government_policy_proposal` | Government policy that requires new primary legislation or future regulator rules. |
| `voluntary_standard` | Voluntary accreditation or assurance standard such as the RCVS Practice Standards Scheme. |
| `best_practice_adaptation` | A useful framework adapted from another sector without claiming legal applicability or certification. |

The baseline date is 26 July 2026. Source status must be reviewed whenever law, RCVS guidance, the CMA Order or veterinary reform legislation changes.

## Engineering boundary

LucyWorks can complete the following without access to a live hospital:

- machine-readable UK legal and professional baseline;
- reference identity groups and least-privilege capability model;
- synthetic patient, owner, staff and workflow packs;
- vendor-neutral PIMS, PACS, LIS, workforce, insurance and payment contracts;
- controller-ready DPIA baseline;
- safety plan and 19-hazard clinical and operational hazard log;
- synthetic and historical-replay release decisions;
- negative, concurrency, failure and recovery tests.

LucyWorks cannot truthfully sign on behalf of a deployment organisation. Shadow, pilot and live gates therefore require deployment evidence for identity mapping, data governance, vendor connections, a named safety owner, DPIA approval and—where relevant—penetration testing and user acceptance.

## Safety methodology

The documentation structure adapts useful elements of DCB0129 and DCB0160:

1. define system scope and intended use;
2. identify foreseeable hazardous situations and potential harm;
3. score severity and likelihood from 1 to 5;
4. specify design, process and operational controls;
5. define verification and evidence;
6. assess residual risk;
7. prevent release where residual risk is 16 or above or the hazard is uncontrolled;
8. record an accountable target-specific safety review;
9. continue post-release monitoring, incident investigation and corrective action.

DCB0129 and DCB0160 are health-sector standards. This adaptation does not claim that they legally apply to veterinary practice, that NHS assurance has occurred, or that LucyWorks is certified under them.

## Baseline hazards

The seeded hazard log covers:

- wrong patient or owner;
- stale or duplicate commands;
- unauthorised clinical action;
- invalid consent;
- medicine dose, weight and unit errors;
- controlled-drug discrepancies;
- unacknowledged critical results;
- handover loss;
- unsafe staffing and competence coverage;
- incomplete anaesthesia monitoring;
- unsafe discharge;
- system outage;
- duplicate, late or mismatched vendor messages;
- privacy disclosure;
- unverified AI output;
- misleading cost or treatment information;
- audit-history alteration;
- emergency-override misuse;
- clock and timezone error.

## Reference identity groups

The catalogue provides hospital-neutral groups mapped to the existing platform roles:

- Clinical Director;
- Senior Clinician;
- Clinician;
- Nursing Supervisor;
- Nurse;
- Reception and Referral;
- Insurance and Finance;
- Operations Control;
- Hospital Director;
- Governance and DPO;
- System Administration;
- Read-only Audit;
- Synthetic Test.

Job title alone never grants a clinical capability. A live identity map must additionally verify registration, competence, service assignment and local approval.

## DPIA baseline

The DPIA baseline covers owner/client data, animal clinical data linked to identifiable owners, workforce identity, workforce health restrictions and audit/security data. It identifies systematic monitoring, integrated datasets, special-category workforce information, automated prioritisation and clinical harm from wrong or unavailable records as high-risk processing areas.

Built-in mitigations include least privilege, strong authentication, encryption, attribution, data minimisation, segregation of duties, retention, subject-rights workflows, breach response, human verification of AI and synthetic-first validation.

The deployment controller must still decide and record lawful bases, special-category conditions, retention periods, processors, international transfers, actual vendors, consultation and residual-risk acceptance.

## API

- `POST /api/v10/compliance-safety/bootstrap`
- `GET /api/v10/compliance-safety/baseline`
- `GET /api/v10/compliance-safety/summary`
- `GET /api/v10/compliance-safety/safety-case`
- `PATCH /api/v10/compliance-safety/hazards/{hazard_ref}`
- `GET /api/v10/compliance-safety/deployment-profile`
- `PATCH /api/v10/compliance-safety/deployment-profile/{profile_ref}`
- `POST /api/v10/compliance-safety/reviews`
- `GET /api/v10/compliance-safety/release-gate?target=synthetic`

## Operator surface

Open `/compliance-safety` from `/system-control`.

The workspace exposes:

- baseline classification;
- current and future obligations;
- safety case;
- hazard log and verification evidence;
- reference identity groups;
- vendor contracts;
- DPIA baseline;
- separate release decisions for synthetic, historical replay, shadow, bounded pilot and live use.

## Release targets

### Synthetic

May pass when the baseline safety case and complete controlled hazard log exist. No real identity, patient, staff or vendor data is required.

### Historical replay

May pass against de-identified or synthetic replay datasets under the same safety baseline.

### Shadow

Requires the deployment organisation to confirm real identity mapping, data governance, vendor connections, named safety ownership and DPIA approval.

### Bounded pilot and live

Additionally require penetration-test evidence and representative staff user-acceptance evidence. Local transition policies, emergency arrangements and clinical governance remain deployment responsibilities.

## Automated proof

Run:

```bash
cd apps/api
python compliance_safety_v10_smoke_test.py
```

The test proves:

- source-status separation;
- current medicine law versus future CMA remedy classification;
- 19-hazard seed;
- synthetic and replay release eligibility;
- shadow and live blocking without organisation evidence;
- stale-write rejection;
- rejection of residual risk 16 or above;
- evidence-backed hazard verification;
- synthetic safety review approval;
- prevention of false live approval;
- authenticated access;
- migration persistence.

## Official source register

The machine-readable source register is stored in `config/compliance/uk-veterinary-compliance-safety-v10.json` and includes current RCVS Codes and guidance, veterinary medicine and controlled-drug guidance, ICO DPIA guidance, the 2026 CMA veterinary-market publications, the Defra veterinary-sector White Paper, NCSC secure-software guidance and the DCB0129/DCB0160 documentation frameworks.
