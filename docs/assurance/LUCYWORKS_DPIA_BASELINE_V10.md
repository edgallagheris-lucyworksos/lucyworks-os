# LucyWorks OS data protection impact assessment baseline v10

**Assessment type:** controller-ready baseline  
**Baseline date:** 26 July 2026  
**Current status:** draft; requires completion and approval by the deploying data controller  
**Engineering environment:** synthetic data by default

## 1. Why a DPIA is required

LucyWorks is designed to integrate client, owner, workforce, operational, financial and audit information across a referral hospital. Likely deployment features include systematic monitoring, workforce availability or fatigue indicators, integration of large datasets and processing that could affect access to time-critical veterinary care.

Those characteristics can create a high risk to individuals if data is inaccurate, unavailable, excessive, misdirected or used outside its intended purpose. The DPIA must therefore be completed before high-risk live processing begins.

## 2. Processing purpose

LucyWorks supports:

- referral intake and hospital episode management;
- communication with owners, clients and referring practices;
- clinical and medicines documentation;
- consent, estimates, insurance and billing administration;
- staffing, competencies, availability and service coverage;
- operational scheduling and incident response;
- vendor integration and reconciliation;
- governance, complaints, audit and regulatory evidence;
- system security, resilience and investigation.

Personal information must not be reused for unrelated profiling, marketing, employee surveillance or automated disciplinary decisions without a separately assessed purpose and lawful basis.

## 3. Data subjects

- animal owners and clients;
- referring veterinary professionals and practice contacts;
- hospital employees, workers, students, agency workers and contractors;
- supplier and insurer contacts;
- application administrators and reviewers;
- complainants, witnesses and incident participants.

Animals are not data subjects under UK GDPR, but animal clinical records commonly identify or relate to an owner or client and should be treated as confidential linked information.

## 4. Data classes

### Owner and client identity

Names, addresses, contact details, communication preferences, decision authority, financial responsibility, insurance references, estimates, invoices, complaints and consent evidence.

**Minimisation:** store only information required for care, communication, finance, legal duties and governance. Do not store payment-card data.

### Animal clinical information linked to an owner

Identity, history, diagnosis, treatment, medicines, imaging and laboratory references, anaesthesia, procedure, inpatient and discharge records.

**Minimisation:** retain clinical detail necessary for safe care and professional records; restrict owner contact and finance fields separately from clinical access where practical.

### Workforce identity and professional status

Name, role, team, registration status, competency evidence, supervision requirements, availability, shifts and assigned work.

**Minimisation:** job title alone must not grant clinical authority. Retain only evidence required for lawful assignment, safety, payroll-independent operations and governance.

### Workforce health and adjustments

Fitness restrictions, adjustments, absence and operational limitations may reveal health information.

**Minimisation:** where possible store the operational restriction or adjustment rather than diagnosis. Use separate access controls and retention.

### Financial and insurance information

Estimate lines, authorisation limits, invoice lines, payment status, claim status, insurer reference and reconciliation.

**Minimisation:** use integer pence, provider tokens and transaction references. Do not store full card data.

### Audit, security and incident information

Authentication events, actor identity, actions, reasons, approvals, access events, errors, incidents, overrides and evidence links.

**Minimisation:** retain what is necessary for accountability, security, investigation, professional duties and legal defence. Prevent use as an ungoverned productivity-monitoring dataset.

## 5. Lawful-basis decisions required from the controller

LucyWorks cannot select the controller's lawful basis on its behalf. The deploying organisation must document, by purpose:

- contract or steps at the client's request;
- legal obligation;
- legitimate interests and the balancing assessment;
- vital interests where genuinely applicable;
- employment-law and health-and-safety grounds for workforce processing;
- any consent used for optional processing, ensuring it is freely given and withdrawable.

For special-category workforce information, the controller must record an Article 9 condition and any required appropriate policy document.

## 6. Information flows

Expected flows include:

- referring practice to referral intake;
- owner/client to reception, finance and clinical teams;
- PIMS to canonical episode and patient record;
- PACS to imaging status and report reference;
- LIS to sample and result records;
- workforce/HR system to role, registration, competence and availability;
- insurer to claim and pre-authorisation status;
- payment provider to tokenised transaction status;
- LucyWorks to owner and referring-vet communications;
- LucyWorks to audit, backup, monitoring and incident systems.

Each interface requires a processor/controller analysis, minimum-field contract, security requirements, retention, failure behaviour and reconciliation plan.

## 7. Necessity and proportionality controls

- purpose-specific fields and vendor contracts;
- least-privilege identity groups;
- separation of clinical, finance, governance and system administration;
- registration and competency checks separate from job title;
- synthetic-first development and testing;
- no live data in synthetic environments;
- no payment-card storage;
- role-limited exports;
- reason and recipient logging for disclosures;
- data correction without erasing material clinical history;
- retention and legal-hold controls;
- subject access, rectification, restriction and objection workflows;
- human review of AI-assisted records;
- no wholly automated clinical decision-making;
- incident and breach response.

## 8. High-risk scenarios and mitigations

| Risk | Potential effect | Core mitigation |
|---|---|---|
| Wrong person or patient linkage | Confidentiality breach and unsafe care | Two identifiers, canonical crosswalk, mismatch reconciliation, prominent identity banner. |
| Excessive role access | Unjustified disclosure or workforce harm | Least privilege, separate finance/governance roles, read-only audit, periodic access review. |
| Workforce health information exposed | Discrimination, distress or confidentiality loss | Separate restricted fields, record operational restriction where possible, short retention. |
| Wrong-recipient communication | Disclosure and loss of trust | Recipient confirmation, audience field, communication history, secure channels. |
| Vendor duplicate or mismatch | Inaccurate records and unsafe decisions | Idempotency, provenance, no silent overwrite, reconciliation queue. |
| System outage | Unavailable time-critical information | Resilience, monitoring, downtime process, backup and restore rehearsal. |
| Audit data repurposed for surveillance | Unfair monitoring or employment decisions | Purpose limitation, governance approval, aggregate reporting, restricted access. |
| AI-generated error | Inaccurate clinical or personal record | Advisory-only use, manual verification, provenance and correction history. |
| Insecure export or backup | Large-scale disclosure | Encryption, access control, expiry, checksum, tested restore and incident response. |
| Excessive retention | Increased breach and fairness risk | Data-class retention schedule, legal hold, reviewed deletion and de-identification. |

## 9. Security measures

- OIDC authentication and role mapping;
- strong session controls;
- encryption in transit and at rest;
- secrets outside source code;
- secure production defaults;
- PostgreSQL migration control;
- append-only evidence and hash linkage;
- optimistic concurrency and row locking;
- backup checksums and isolated restore rehearsal;
- application, database and integration monitoring;
- vulnerability and dependency management;
- independent penetration testing before pilot/live use;
- supplier security assurance;
- incident containment, recovery and notification process.

## 10. Automated decision-making and AI

LucyWorks may prioritise queues, identify conflicts, flag fatigue risk or produce draft text. These functions must remain decision support.

The controller must document:

- logic and intended purpose;
- meaningful human involvement;
- data used;
- accuracy and bias testing;
- override and challenge routes;
- consequences for clients or staff;
- monitoring and review;
- whether Article 22 is engaged for any non-clinical decision.

AI-generated clinical records must be manually verified before being treated as final.

## 11. Data-subject rights

The deployment must provide procedures for:

- transparent privacy information;
- access and secure export;
- rectification and contextual correction;
- restriction and objection;
- erasure where applicable without destroying records that must lawfully be retained;
- complaints and DPO contact;
- explanation and human review of significant automated decisions;
- identity verification before disclosure.

## 12. Retention decisions required

The controller must approve periods for:

- client and owner records;
- clinical and medicines records;
- controlled-drug evidence;
- estimates, invoices, transactions and insurance cases;
- communications and complaints;
- workforce role, competency, shift and health-restriction records;
- audit, security and incident records;
- backups and exports;
- unsuccessful referrals and enquiries;
- synthetic and test data.

Retention must account for professional duties, medicines law, limitation periods, employment obligations, insurance, complaints and regulatory investigation. LucyWorks must not invent one universal period.

## 13. International transfers and suppliers

Before live connection, the controller must record:

- supplier legal name and role;
- hosting and support locations;
- subprocessors;
- transfer mechanism and assessment where data leaves the UK;
- encryption and key control;
- access by support staff;
- deletion and return on termination;
- incident notification terms;
- audit and assurance rights.

## 14. Consultation

The controller should consult:

- veterinary clinical leadership;
- nursing leadership;
- reception and referral staff;
- insurance and finance teams;
- operations and facilities;
- information governance/DPO;
- HR and workforce representatives;
- IT and cyber security;
- representative users;
- vendors and processors;
- clients or client representatives where appropriate.

If residual high risk cannot be reduced, the controller must consider prior consultation with the ICO before processing begins.

## 15. Residual decisions and approval

The machine-readable DPIA baseline records built-in mitigations. The following remain deployment decisions:

- controller and processor roles;
- lawful basis and special-category condition;
- actual purposes and fields enabled;
- identity groups and access review;
- vendors and international transfers;
- retention periods;
- workforce monitoring limits;
- AI use cases;
- incident and rights procedures;
- consultation results;
- residual-risk acceptance.

The persisted deployment profile requires a named organisation and an evidence reference to a passed `privacy.dpia` readiness control. A Boolean alone cannot satisfy the live release gate.

## 16. Sign-off

Approval must be recorded by the deploying controller through the readiness evidence and target-specific safety-review workflow.

This unsigned baseline is not a controller approval and does not claim that BVS or any other hospital has completed a DPIA.
