# LucyWorksOS Specification v1

## 1. Purpose

LucyWorksOS is a specialist referral-veterinary hospital operating system. It is not a set of independent dashboards, a replacement PMS built all at once, or an AI wrapper. Its job is to coordinate hospital work, authority, capacity, evidence and communication across one connected operational state.

The system must answer, at any point in the day:

- what is happening;
- to which patient and episode;
- where it is happening;
- who owns it;
- which supporting staff and resources are required;
- whether the work is authorised and ready;
- what is blocking it;
- what happens next;
- what changed, who changed it, why, and what evidence supports that change.

The canonical operational chain is:

```text
hospital
→ area / room
→ patient / episode
→ work / procedure
→ staff / resource
→ authority / readiness
→ state / action
→ evidence
```

## 2. Architectural stance

LucyWorksOS shall be built as a **modular monolith** until scale or regulatory isolation creates a proven reason to split services.

Canonical implementation:

```text
apps/web  = staff-facing web application
apps/api  = backend, domain logic, persistence, authority, evidence and integrations
```

Do not create additional active frontend/backend trees.

### Why modular monolith

A referral hospital requires strongly consistent state across scheduling, staff, consent, resources, medicines and evidence. Splitting these domains into microservices prematurely would increase distributed-state, deployment and reconciliation risk without delivering a current product advantage.

The internal design must still use clear domain boundaries so a future service split is possible without rewriting the product.

## 3. Source of truth

LucyWorksOS has one persisted hospital state.

### Canonical state

The canonical relational database contains the current accepted state of operational entities.

### Evidence ledger

An append-only EvidenceEvent ledger records consequential changes, authority, reasons and provenance.

LucyWorksOS is **not** a pure event-sourced system. The event ledger must not become the only way to reconstruct basic current state. Current operational state remains directly queryable from canonical relational models.

### Read models

The hospital board, department views, staff queues, patient timelines and dashboards are projections/read models over canonical state. They are never independent sources of truth.

## 4. Persistence and offline-first development

### Local/offline development

Default local development may use:

```text
SQLite
local API
local web application
local test data
local Ollama/local coding model
```

Normal local startup must not require internet access or run package-install commands every time.

### Pilot/production

Use PostgreSQL with Alembic migrations. Production schema must never depend on runtime auto-create or SQLite compatibility patches.

### Database rule

Application code must not contain long-lived ad-hoc schema migration maps. SQLite compatibility migration code is transitional only and must be retired as the canonical Alembic migration history becomes complete.

## 5. Canonical domain model

### Organisation and place

```text
Organisation
Site
Department
Area
Room
Resource
ResourceCapability
ResourceState
```

### Patient and client

```text
Patient
Client / Owner
Referral
Episode
Admission
Encounter
ClinicalProblem
```

A Patient is longitudinal identity. An Episode is the connected hospital journey for a referral/admission/workup. Operational work attaches to the Episode, not merely to a display card.

### Work and scheduling

```text
ProcedureTemplate
ProcedureRequirement
ScheduledCase
WorkItem
WorkBlock
Dependency
Handover
Blocker
Decision
```

Procedure templates generate connected work rather than just labels.

Typical chain:

```text
arrival
→ consult
→ decision
→ consent / estimate / insurance readiness
→ prep
→ anaesthesia if required
→ imaging / procedure / treatment
→ recovery
→ result / decision review
→ owner update
→ discharge / transfer / continued care
```

### Workforce and authority

```text
StaffMember
ProfessionalRegistration
ProfessionalStatus
Competency
LocalAuthorisation
SupervisionRequirement
Shift
BreakRequirement
Assignment
```

Job title alone never determines authority.

Authority is evaluated from:

```text
person
+ professional status
+ competency
+ local authorisation
+ task/procedure
+ supervision requirement
+ site/location
+ validity period
= effective authority
```

### Commercial and client authority

```text
ClinicalProcedure
CommercialService
ServiceVariant
PriceVersion
Estimate
EstimateVersion
ClientAuthorisation
Consent
Charge
Invoice
Payment / InsuranceState
Variance
```

Clinical procedure and commercial service are distinct objects.

Historic estimates remain anchored to the exact PriceVersion used when the estimate was produced. Updating the live catalogue must never silently reprice an existing estimate.

### Medicines and results

```text
MedicationProduct
Batch
StockPosition
MedicationOrder
MedicationAdministration
ControlledDrugEvent
DiagnosticOrder
Result
ResultReview
CriticalResultAlert
```

### Communication

```text
CommunicationRequirement
CommunicationEvent
OwnerUpdate
ReferringVetUpdate
DischargeCommunication
```

Communication requirements should be generated from hospital facts and workflow states where possible, not rely on staff remembering to create free-text reminders.

### Safety and governance

```text
SafetyFlag
SafeguardingConcern
Incident
Complaint
CorrectiveAction
Approval
Override
RetentionHold
```

### AI

```text
AIInvocation
AIOutput
AIVerification
```

AI output is never canonical clinical truth until the required human verification step has completed.

## 6. Identity and references

Every externally meaningful entity has a stable opaque reference such as:

```text
patient_ref
episode_ref
staff_ref
work_ref
resource_ref
estimate_ref
event_ref
```

Database integer IDs are internal implementation details and must not be used as durable integration identifiers.

Every imported entity may retain source-system mappings:

```text
source_system
source_entity_type
source_record_ref
canonical_entity_ref
```

## 7. State and command architecture

All consequential writes must go through explicit domain commands.

Examples:

```text
AdmitPatient
AssignStaff
MoveWork
PlaceHold
ResolveBlocker
AuthoriseEstimate
RecordConsent
StartProcedure
CompleteProcedure
RecordMedicationAdministration
RecordOwnerUpdate
ApproveTask
EmergencyOverride
VerifyAIOutput
AcknowledgeComplaint
PublishPriceVersion
```

A command must perform, in one controlled transaction where practical:

1. identity/authentication check;
2. effective-authority check;
3. current-state validation;
4. conflict/safety validation;
5. canonical state mutation;
6. append EvidenceEvent;
7. enqueue any downstream projection/integration work;
8. commit.

UI routes must not directly reproduce domain rules independently.

## 8. Domain events and realtime propagation

Use an internal domain-event/outbox pattern for downstream consequences and live UI updates.

Examples:

```text
WorkAssigned
WorkMoved
PatientAdmitted
EstimateAccepted
ConsentRecorded
ProcedureStarted
ProcedureOverrun
CriticalResultRecorded
ComplaintOpened
AIOutputVerified
```

Domain events are not a second source of truth. They notify read models, realtime clients and integration adapters after a successful canonical transaction.

This removes the need for independent page-level state to pretend that an action succeeded.

## 9. Concurrency and integrity

Hospital state changes can occur simultaneously. Canonical mutable entities must support optimistic concurrency/version checks where lost updates would be unsafe.

Use:

```text
version / revision
idempotency key
request / correlation ID
```

Commands that repeat because of retry, connectivity or integration delivery must be safely idempotent.

## 10. Time model

The user-facing hospital operating grid uses 15-minute control intervals.

The database must store exact timestamps and durations rather than quantising every event to 15-minute boundaries.

This allows:

- a 23-minute procedure;
- a 7-minute delay;
- an 11-minute overrun;
- exact audit timing;

while still rendering the operational board in 15-minute blocks.

Store time in UTC and apply site timezone at the presentation/scheduling boundary.

## 11. Procedure templates and readiness

A ProcedureTemplate defines at minimum:

```text
procedure type
expected duration
prep duration
recovery duration
turnover duration
required room/resource capabilities
required professional roles
required competencies
anaesthesia requirement
medication/stock prerequisites
consent requirement
estimate/financial-authority requirement
result/review requirements
owner/referrer communication points
```

A scheduled case derives a readiness state from its requirements.

Example:

```text
patient present              yes
consent valid                yes
estimate authority           yes
required clinician           yes
required nurse               yes
room capability              yes
anaesthesia readiness        yes
stock/medication readiness   yes
recovery capacity            no

READY = false
BLOCKER = no recovery capacity
```

The board displays the result and reason; it does not independently calculate a different reality.

## 12. Master hospital command view

The primary hospital view is a command surface over canonical state.

It must show at referral-hospital scale:

```text
now
next
blocked / exceptions
active work
location
responsible owner
supporting staff
readiness
overruns
resource pressure
staff pressure
client/referrer update requirements
safety/governance pressure
```

It must not represent every room as a permanently huge horizontal column if that destroys usability at 40+ room scale.

Department views are specialised projections of the same model:

```text
Imaging
Theatre
Anaesthesia
Wards / ICU
Reception / Intake
Pharmacy
Diagnostics
Discharge
Rota
Governance
```

## 13. Conflict and capacity engine

Conflict detection is a shared backend capability.

At minimum detect:

```text
room overlap
resource overlap
staff overlap
missing required role
missing competency
expired authority
missing supervision
consent blocker
estimate/financial-authority blocker
medication/stock blocker
recovery-capacity blocker
turnover dependency
late arrival
work overrun
thin cover
missed/protected break
unsafe reassignment
emergency displacement consequence
```

Conflicts have severity, cause, affected entities, resolution options and evidence consequences.

## 14. Emergency override

Emergency override is an explicit command, not a hidden bypass.

It records:

```text
actor
authority
reason
risk accepted
normal rule overridden
affected work/resources
state before
state after
follow-up/review requirement
```

Hard prohibitions that cannot legally/safely be overridden remain non-overridable.

## 15. Regulatory evidence layer

EvidenceEvent is the common evidence primitive.

Every consequential event can record:

```text
event_ref
event_type
actor
verified identity source
professional role/effective authority
entity
patient/episode links
state before
state after
action
reason / justification
evidence links
client authorisation
approval / supervisor status
override reason
AI provenance and verification
compliance domain
risk level
source system/source record
correlation / causation
occurred_at
created_at
hash/integrity fields
```

The ledger is append-only. Corrections create superseding/corrective events rather than rewriting history.

## 16. Regulatory requirement classification

LucyWorks must distinguish requirement sources:

```text
law / statutory order
professional regulation
professional guidance
regulatory proposal / consultation
hospital policy
local operating rule
LucyWorks safety rule
```

Each rule/requirement carries:

```text
source
status
effective_from
effective_until
jurisdiction
version
supporting reference
```

This prevents proposed rules being presented as current legal obligations.

## 17. Pricing, estimates and billing evidence

PriceCatalogue is structured and versioned.

A service version can include:

```text
service
variant
species / weight band
complexity tier
included components
third-party components
published price/range
currency
effective_from
effective_until
publication status
```

Internal cost and margin data are kept separate from publishable pricing.

EstimateVersion records:

```text
catalogue version(s)
itemised projected lines
assumptions
known uncertainty factors
excluded items
lower/upper amount
approved ceiling
client decision
method/time of communication
change reason
superseded version
```

The final invoice must support estimate-to-actual variance reconstruction.

## 18. Complaint and corrective-action architecture

Complaint is a linked governance object, not an inbox folder.

It may reference:

```text
patient
episode
estimate
invoice
communication
staff/service
incident
workflow failure
EvidenceEvent
```

Complaint state includes configurable clocks, acknowledgement, investigation, outcome, ADR/escalation and retention hold.

Corrective actions have accountable owner, due date, evidence, completion and effectiveness review.

## 19. AI authority model

AI authority varies by task.

### Allowed examples

```text
transcription                 draft
note summarisation            draft + mandatory verification where clinical
classification/extraction     bounded suggestion
scheduling optimisation       recommendation / bounded automation
owner communication           template/draft under policy
```

### Deterministic engines preferred

Use deterministic logic for:

```text
price calculation
capacity calculation
conflict detection
dose arithmetic where clinically approved formulas apply
retention clocks
authority checks
workflow dependency checks
```

### Never autonomous

```text
final clinical treatment decision
complaint adjudication
professional disciplinary judgement
suppression of deterioration/safety alerts
```

Store original AI output, model/version/provenance and final verified record separately.

## 20. Integration architecture

LucyWorks should orchestrate existing systems rather than duplicate every specialist product.

Adapters map external systems to canonical entities.

Examples:

```text
PMS
PACS / imaging
laboratory
pharmacy / wholesaler
insurance
payments
communications
identity / HR
```

Integration adapters may ingest, publish, reconcile and retry, but may not bypass canonical validation/authority rules when changing LucyWorks state.

Use an integration inbox/outbox with idempotency, retry state and dead-letter visibility.

## 21. Security and professional authority

Authentication, platform roles and professional authority are separate concepts.

Use layered access control:

```text
identity
+ organisation/site access
+ application role
+ professional status
+ competency/authorisation
+ object/context constraints
```

Sensitive operations require server-side enforcement. Frontend hiding is never a security control.

## 22. Proposed backend package architecture

The current backend has accumulated many versioned route modules and runtime patches. The target structure is clearer domain ownership, without an immediate destructive rewrite.

```text
apps/api/app/
  core/
    config.py
    database.py
    identity.py
    errors.py
    time.py

  domains/
    patients/
    episodes/
    workforce/
    authority/
    operations/
    scheduling/
    resources/
    commercial/
    medicines/
    diagnostics/
    communications/
    safety/
    complaints/
    evidence/
    ai/
    integrations/

  api/
    routers/

  infrastructure/
    persistence/
    realtime/
    integrations/
    outbox/

  main.py
```

Each domain should contain its models, schemas, commands/services, policies and tests rather than spreading one workflow across multiple numbered patch files.

Do not reorganise everything in one commit. Migrate domain-by-domain while preserving working behaviour.

## 23. Proposed frontend architecture

```text
apps/web/
  app/
    hospital-board/
    patients/
    imaging/
    theatres/
    wards/
    pharmacy/
    intake/
    rota/
    governance/

  features/
    hospital-command/
    patient-episode/
    scheduling/
    workforce/
    commercial/
    medicines/
    communications/
    governance/

  components/
    shared/

  lib/
    api/
    realtime/
    auth/
    formatting/
```

Pages are compositions over feature/domain APIs. They must not contain independent business-state engines.

## 24. Offline development architecture

Normal offline workflow:

```text
local Git repo
+ local Python environment
+ local Node dependencies
+ SQLite development database
+ local API on 127.0.0.1:8000
+ local web app on 127.0.0.1:3000
+ optional Ollama coding/AI models
```

Create a dedicated offline startup command that performs no `pip install`, `npm install`, `git pull` or network call.

Online/bootstrap commands are separate.

## 25. Testing requirements

Minimum layers:

### Domain tests

- state transitions;
- authority policies;
- conflict rules;
- price/estimate versioning;
- evidence creation;
- idempotency;
- retention/complaint clocks.

### API tests

- authentication;
- permissions;
- command validation;
- concurrency;
- integration retry behaviour.

### Browser tests

- real navigation;
- actual state changes;
- blocker resolution;
- patient-to-episode-to-work drilldown;
- master-board behaviour.

### Scale acceptance

Retain at minimum:

```text
40 simultaneous rooms/areas
100 named active staff
multiple concurrent cases
```

### Integrity tests

- evidence hash-chain verification;
- migration upgrade from supported previous schema;
- estimate history cannot be silently rewritten;
- rejected/expired authority prevents protected actions.

## 26. Migration strategy for the existing repository

Do not delete the existing system before classification.

For every current module/file/feature classify:

```text
KEEP      = already conforms
EXTEND    = correct foundation but incomplete
MERGE     = duplicate capability that belongs in canonical domain
MIGRATE   = useful behaviour in wrong location/architecture
RETIRE    = replaced after tests prove canonical equivalent
REMOVE    = genuinely unused and safely proven unnecessary
```

No feature is removed solely because its file name or route version looks old.

## 27. Immediate architectural priorities

### P0 — make the spine authoritative

1. canonical Patient / Episode references;
2. canonical WorkItem / WorkBlock / resource assignment;
3. one command path for consequential writes;
4. shared authority evaluation;
5. shared EvidenceEvent creation;
6. version/idempotency/concurrency discipline.

### P0 — commercial/regulatory chain

1. CommercialService + ServiceVariant;
2. PriceVersion;
3. anchor EstimateVersion to exact price versions;
4. client financial authority / consent link;
5. actual-charge variance reconstruction.

### P1 — master-board readiness engine

Generate readiness/blocker state from canonical dependencies and make all department views consume it.

### P1 — workforce capability

Strengthen existing competency records into effective-authority evaluation with professional status, local authorisation and supervision.

### P1 — AI verification

Make AI verification/provenance a reusable workflow rather than scattered fields on individual features.

### P1 — complaints/governance

Link complaints, incidents and corrective actions to episode/evidence objects.

## 28. Architecture rules for coding agents

Before any change, a coding agent must answer:

```text
Which canonical entity does this read?
Which canonical entity does this change?
Which command performs the change?
Which authority policy permits it?
Which conflict/safety rules apply?
Which EvidenceEvent is created?
Which other views must observe the change?
What is the rollback/failure behaviour?
What tests prove the behaviour?
```

If the answer is "this page keeps its own state", the design is normally wrong.

## 29. Definition of complete

A feature is complete only when:

- it uses canonical entities;
- writes use the authoritative backend command path;
- permissions/authority are enforced server-side;
- conflicts and blockers are explicit;
- consequential changes produce evidence;
- dependent views observe the same state;
- tests cover the real behaviour;
- the feature functions in the local development environment without requiring cloud AI.

## 30. Product north star

LucyWorksOS should become the **operational orchestration, authority and evidence layer for a specialist referral hospital**.

Its defensible advantage is not the number of screens. It is that patient flow, staff capability, resources, commercial authority, safety, AI verification and regulatory evidence all operate against one connected hospital state.