# Organisation onboarding and hospital configuration v27

## Purpose

v27 turns organisation and hospital setup into a governed product workflow. It does not treat a CSV, an OIDC claim, a copied configuration file or a job title as operational truth.

The operating rule is:

> Draft onboarding data is isolated. Only an approved, versioned configuration release may publish into the hospital runtime. Staff access is approved separately.

This is code and control architecture. It is not evidence that a real hospital, identity provider, regulator, vendor or staff directory has been configured.

## Authority boundary

LucyWorks may store, validate, compare, hold, route, publish and evidence configuration. Configuration cannot autonomously:

- diagnose or select treatment;
- prescribe or change a dose;
- administer medication;
- complete consent;
- acknowledge a clinical result;
- admit, discharge or change a clinical phase;
- grant clinical authority from an imported title;
- keep clinical access active after employment, registration or competency evidence expires.

## Lifecycle

1. Record the legal organisation and accountable executive.
2. Record each hospital site and real premises reference.
3. Configure departments and named accountability.
4. Configure services, capabilities, minimum staffing and escalation roles.
5. Map rooms and infection-control zones.
6. Map equipment, maintenance status and service dependencies.
7. Preview a staff import without writing staff or access records.
8. Commit only a valid import into the onboarding workspace.
9. Independently match staff records to authenticated identities.
10. Verify professional credentials and competencies where required.
11. approve hospital-specific policies with evidence.
12. Assess configuration readiness.
13. Approve and publish a hashed configuration release.
14. Approve each staff member's site role separately, or mark access as not required.
15. Assess go-live readiness.
16. Keep later edits isolated until another release is approved.
17. Roll back by creating a new evidenced release from a previous approved snapshot.

## Section audit

### Legal organisation

**Weakness before v27:** v26 could bootstrap an organisation name but did not prove legal identity, data-controller ownership or accountable executive.

**v27 control:** legal name, trading name, company number, country, registered address, data-controller contact and accountable executive are versioned onboarding records. Missing legal or data-controller information blocks configuration release.

### Hospital site and premises

**Weakness before v27:** a site could be created from token claims or local bootstrap and become context without a governed hospital configuration.

**v27 control:** production context requires an approved v27 site release. `default-premises` is forbidden. Site address, accountable director and clinical-governance owner are release blockers.

### Departments and accountability

**Weakness before v27:** departments existed in multiple runtime catalogues with no single approved release boundary.

**v27 control:** departments are draft entities linked to one site and premises. Unknown department references from services, rooms or staff block release.

### Services and capacity

**Weakness before v27:** service availability could be represented without proving minimum staffing, room mapping or required equipment.

**v27 control:** every clinical service must define minimum staffing and map to at least one room. Required equipment must exist and have current verified maintenance.

### Rooms and facilities

**Weakness before v27:** room names and capabilities could be edited directly in runtime configuration.

**v27 control:** rooms are included in the approved snapshot. Draft changes do not alter runtime. Unknown departments or services block release.

### Equipment

**Weakness before v27:** equipment and service state could diverge, and a configured service could reference an unverified asset.

**v27 control:** equipment is mapped to rooms and services. Required equipment must have verified, current maintenance before release.

### Workforce import

**Weakness before v27:** imported staff data risked becoming authority or runtime truth too early.

**v27 control:** preview and commit are separate. Missing fields and duplicate staff references are detected. A committed import creates onboarding staff records only. It creates no site membership and grants no access.

### Identity matching

**Weakness before v27:** a supplied subject or email could be assumed to identify the correct employee.

**v27 control:** imported subjects remain `pending_match`. A configuration administrator must independently match one staff record to one authenticated subject. Duplicate subject matches are rejected.

### Roles and access

**Weakness before v27:** OIDC roles and imported job titles could be mistaken for hospital authority.

**v27 control:** the requested role, verified identity and approved role must match. Site membership is created only after a separate access approval with evidence. Every active imported person must be approved or explicitly marked as not requiring system access before go-live readiness passes.

Non-clinical hospital roles are authenticated without being added to clinical or prescribing authority:

- reception;
- referral coordinator;
- insurance;
- pharmacy;
- laboratory;
- imaging;
- ward assistant;
- facilities;
- HR;
- finance;
- viewer.

### Professional credentials

**Weakness before v27:** a clinical role could exist without current evidence of professional registration.

**v27 control:** clinical access approval requires a current verified credential with evidence. The context resolver rechecks expiry whenever hospital context is loaded.

### Competency

**Weakness before v27:** registration alone could be treated as competence for a service, procedure or area.

**v27 control:** clinical access also requires at least one current verified competency. Competency scope, level, dates and evidence are recorded separately from professional registration. Expiry blocks context.

### Employment and access removal

**Weakness before v27:** an old membership could remain active after employment or access status changed.

**v27 control:** context resolution rechecks active employment, verified identity, approved access status and role consistency. Marking access as not required revokes any active approval and membership.

### Hospital policies

**Weakness before v27:** generic product rules could be used without the hospital approving its actual operational policies.

**v27 control:** configuration release requires approved, evidenced site policies for:

- fatigue and safe staffing;
- patient-safety escalation;
- service restriction;
- safeguarding;
- data retention;
- downtime and recovery.

An overdue policy review blocks release.

### Configuration release

**Weakness before v27:** partial edits could immediately affect rooms, services, staff or context.

**v27 control:** the complete snapshot is canonicalised and SHA-256 hashed. Approval creates an immutable release and publishes it into the existing v6 runtime configuration and workforce tables plus the v26 organisation/site context.

### Pending changes

**Weakness to avoid:** disabling a live hospital merely because an administrator starts editing the next version.

**v27 control:** a site with `changes_pending` continues to operate from its last approved release. The draft remains isolated until approval.

### Rollback

**Weakness before v27:** restoring earlier values could overwrite audit history.

**v27 control:** rollback never reactivates an old database row in place. It creates a new release version containing the earlier approved snapshot, records who approved the rollback and republishes that snapshot.

### Runtime publication

**Weakness to avoid:** adding a second operational configuration system.

**v27 control:** approved snapshots publish into existing `HospitalConfigurationRecord`, `WorkforceProfile`, `WorkforceCompetency`, `OrganisationV26` and `SiteV26` records. v27 is the governed onboarding/release layer; those existing tables remain runtime views.

### Patient and clinical crossover

A configuration problem can affect patient flow, staffing or service availability. v27 itself does not create clinical decisions. v26 canonical commands and v25 safety controls remain responsible for live patient blockers, service restrictions, equipment downtime, handovers and critical results.

### Confidentiality

The onboarding workspace stores staff identity, employment, credential and competency information. Daily patient-facing boards must not expose this detail. v27 provides readiness counts and blockers for authorised administrators; operational views continue to use board-safe summaries.

### Concurrency and evidence

Configuration records are versioned and support stale-write rejection through `expectedVersion`. Every material change records authenticated actor, previous state, new state, reason and an evidence event. Release hashes allow later verification that runtime publication came from the approved snapshot.

### Recovery

Migration `0021_organisation_onboarding_v27` adds fourteen onboarding, release and access-control tables. Restore rehearsal must verify every table and retain release, access and change evidence.

## Connected proof

The v27 proof demonstrates:

1. draft organisation and site records do not create runtime context;
2. draft room, equipment, service and policy data remains isolated;
3. invalid staff imports cannot be committed;
4. a valid import grants no access;
5. configuration readiness and go-live readiness are separate;
6. clinical access is blocked without verified credential and competency evidence;
7. an approved release publishes to existing runtime tables;
8. production-style context requires the approved person, role and site release;
9. reception can use an approved non-clinical role without clinical authority;
10. later drafts do not alter the active runtime;
11. a second release publishes the reviewed change;
12. rollback creates a third release and restores the earlier runtime snapshot;
13. expired credentials and inactive employment block context;
14. no medication order, administration, episode transition or discharge/closure is created;
15. the evidence chain remains valid.

## Remaining real deployment dependencies

v27 does not supply or verify the hospital's real data. Deployment still requires:

- actual company, data-controller and premises details;
- actual OIDC issuer, role mapping and subject identifiers;
- verified HR/staff-directory import mapping;
- direct or manually governed professional-register checks;
- hospital-approved competency framework and assessors;
- actual department, service, room and equipment catalogue;
- maintenance and calibration evidence;
- real staffing thresholds and escalation policies;
- approved safeguarding, retention, downtime and whistleblowing policies;
- PMS, imaging, laboratory, pharmacy, rota and finance integrations;
- data-protection impact assessment, retention implementation and access review;
- UAT, historical replay, downtime rehearsal, restore rehearsal and bounded pilot evidence;
- named hospital executives accepting release and go-live accountability.
