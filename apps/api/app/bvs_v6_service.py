from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import AuthContext
from app.bvs_v6_models import (
    ConfigurationClaim,
    ConfigurationVerificationTask,
    CoverageRequirement,
    HistoricalReplayEvent,
    HistoricalReplayRun,
    HospitalConfigurationRecord,
    ReferralIntake,
    ReferralIntakeEvent,
    WorkforceCompetency,
    WorkforceProfile,
)
from app.evidence_service import create_evidence_event

PREMISES_REF = "bvs-bristol"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _actor(auth: AuthContext) -> tuple[str, str, str]:
    return auth.actor_id or auth.subject, auth.actor_name, auth.role


def _evidence(
    session: Session,
    auth: AuthContext,
    *,
    event_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    previous_state: Any,
    new_state: Any,
    reason: str,
    risk_level: str = "amber",
) -> None:
    actor_id, actor_name, actor_role = _actor(auth)
    create_evidence_event(
        session,
        event_type=event_type,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        actor_auth_source=auth.auth_source,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        justification="LucyWorks BVS configuration, workforce and referral governance",
        evidence_links=[{"type": entity_type, "id": entity_id}],
        compliance_domain="hospital_operations",
        risk_level=risk_level,
        source_module="bvs_v6",
        source_record_ref=entity_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def config_dict(row: HospitalConfigurationRecord) -> dict[str, Any]:
    return {
        "premisesRef": row.premises_ref,
        "entityType": row.entity_type,
        "entityRef": row.entity_ref,
        "name": row.name,
        "attributes": row.attributes,
        "operationalStatus": row.operational_status,
        "verificationStatus": row.verification_status,
        "authoritativeSourceRef": row.authoritative_source_ref,
        "version": row.version,
        "updatedBy": row.updated_by_actor_name,
        "updatedAt": row.updated_at.isoformat(),
    }


def claim_dict(row: ConfigurationClaim) -> dict[str, Any]:
    return {
        "claimRef": row.claim_ref,
        "premisesRef": row.premises_ref,
        "entityType": row.entity_type,
        "entityRef": row.entity_ref,
        "fieldName": row.field_name,
        "claimedValue": row.claimed_value,
        "sourceType": row.source_type,
        "sourceRef": row.source_ref,
        "sourceUrl": row.source_url,
        "observedAt": row.observed_at.isoformat() if row.observed_at else None,
        "confidence": row.confidence,
        "status": row.status,
        "notes": row.notes,
        "version": row.version,
        "reviewedBy": row.reviewed_by_actor_name,
        "reviewedAt": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def task_dict(row: ConfigurationVerificationTask) -> dict[str, Any]:
    return {
        "taskRef": row.task_ref,
        "premisesRef": row.premises_ref,
        "category": row.category,
        "question": row.question,
        "whyItMatters": row.why_it_matters,
        "requestedEvidence": row.requested_evidence,
        "accountableRole": row.accountable_role,
        "priority": row.priority,
        "status": row.status,
        "linkedEntityType": row.linked_entity_type,
        "linkedEntityRef": row.linked_entity_ref,
        "linkedClaimRefs": row.linked_claim_refs,
        "answer": row.answer,
        "evidenceRefs": row.evidence_refs,
        "version": row.version,
        "answeredBy": row.answered_by_actor_name,
        "answeredAt": row.answered_at.isoformat() if row.answered_at else None,
    }


def workforce_dict(row: WorkforceProfile) -> dict[str, Any]:
    return {
        "premisesRef": row.premises_ref,
        "staffRef": row.staff_ref,
        "displayName": row.display_name,
        "employmentStatus": row.employment_status,
        "primaryRoleRef": row.primary_role_ref,
        "departmentRef": row.department_ref,
        "gradeOrTrainingLevel": row.grade_or_training_level,
        "registrationBody": row.registration_body,
        "registrationNumber": row.registration_number,
        "contractedHoursWeekly": row.contracted_hours_weekly,
        "maximumSafeHoursWeekly": row.maximum_safe_hours_weekly,
        "supervisorStaffRef": row.supervisor_staff_ref,
        "onCallEligible": row.on_call_eligible,
        "sourceStatus": row.source_status,
        "version": row.version,
        "updatedBy": row.updated_by_actor_name,
        "updatedAt": row.updated_at.isoformat(),
    }


def competency_dict(row: WorkforceCompetency) -> dict[str, Any]:
    return {
        "premisesRef": row.premises_ref,
        "staffRef": row.staff_ref,
        "competencyRef": row.competency_ref,
        "scopeRef": row.scope_ref,
        "level": row.level,
        "status": row.status,
        "evidenceSummary": row.evidence_summary,
        "validFrom": row.valid_from.isoformat() if row.valid_from else None,
        "validUntil": row.valid_until.isoformat() if row.valid_until else None,
        "verifiedBy": row.verified_by_actor_name,
        "verifiedAt": row.verified_at.isoformat() if row.verified_at else None,
        "version": row.version,
    }


def coverage_dict(row: CoverageRequirement) -> dict[str, Any]:
    return {
        "requirementRef": row.requirement_ref,
        "premisesRef": row.premises_ref,
        "serviceRef": row.service_ref,
        "areaRef": row.area_ref,
        "roleRef": row.role_ref,
        "competencyRef": row.competency_ref,
        "dayType": row.day_type,
        "startsAtLocal": row.starts_at_local,
        "endsAtLocal": row.ends_at_local,
        "minimumCount": row.minimum_count,
        "escalationRole": row.escalation_role,
        "verificationStatus": row.verification_status,
        "version": row.version,
    }


def referral_dict(row: ReferralIntake) -> dict[str, Any]:
    return {
        "referralRef": row.referral_ref,
        "premisesRef": row.premises_ref,
        "receivedAt": row.received_at.isoformat(),
        "sourceChannel": row.source_channel,
        "urgency": row.urgency,
        "referringPractice": row.referring_practice,
        "referringVet": row.referring_vet,
        "practiceContact": row.practice_contact,
        "patientName": row.patient_name,
        "species": row.species,
        "ownerName": row.owner_name,
        "ownerContact": row.owner_contact,
        "requestedServiceRef": row.requested_service_ref,
        "presentingProblem": row.presenting_problem,
        "historySummary": row.history_summary,
        "insuranceStatus": row.insurance_status,
        "attachmentManifest": row.attachment_manifest,
        "requiredInformation": row.required_information,
        "missingInformation": row.missing_information,
        "status": row.status,
        "decision": row.decision,
        "decisionReason": row.decision_reason,
        "assignedRole": row.assigned_role,
        "assignedActorId": row.assigned_actor_id,
        "assignedActorName": row.assigned_actor_name,
        "responseDueAt": row.response_due_at.isoformat() if row.response_due_at else None,
        "version": row.version,
        "createdBy": row.created_by_actor_name,
        "updatedAt": row.updated_at.isoformat(),
    }


def replay_dict(row: HistoricalReplayRun) -> dict[str, Any]:
    return {
        "runRef": row.run_ref,
        "premisesRef": row.premises_ref,
        "sourceDate": row.source_date.isoformat(),
        "dataClassification": row.data_classification,
        "status": row.status,
        "eventCount": row.event_count,
        "metrics": row.metrics,
        "findings": row.findings,
        "createdBy": row.created_by_actor_name,
        "createdAt": row.created_at.isoformat(),
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
    }


_DRAFT_CONFIG = [
    ("premises", PREMISES_REF, "Bristol Vet Specialists", {"operatingModel": "24/7 referral hospital", "addressStatus": "requires local verification"}),
    ("service", "emergency-critical-care", "Emergency and critical care", {"operatingHours": "24/7 public claim"}),
    ("service", "neurology-neurosurgery", "Neurology and neurosurgery", {}),
    ("service", "internal-medicine", "Internal medicine", {}),
    ("service", "surgery", "Surgery", {}),
    ("service", "diagnostic-imaging", "Diagnostic imaging", {"modalities": ["MRI", "CT", "X-ray", "ultrasound"]}),
    ("service", "oncology-radiotherapy", "Oncology and radiotherapy", {"equipment": ["linear accelerator"]}),
    ("service", "cardiology", "Cardiology", {}),
    ("service", "anaesthesia-analgesia", "Anaesthesia and analgesia", {}),
    ("service", "clinical-pathology", "Clinical pathology", {"urgentTesting": "onsite public claim"}),
    ("area", "theatre-suite", "Operating theatre suite", {"configuredCount": None}),
    ("area", "mri", "MRI", {"scanner": "1.5T public claim"}),
    ("area", "ct", "CT", {"scanner": "64-slice public claim"}),
    ("area", "dog-ward", "Dog ward", {"speciesSeparated": True}),
    ("area", "cat-ward", "Cat ward", {"speciesSeparated": True}),
    ("area", "isolation", "Isolation", {}),
]


_DRAFT_CLAIMS = [
    {
        "claim_ref": "bvs-public-theatre-count-5",
        "entity_type": "area",
        "entity_ref": "theatre-suite",
        "field_name": "operatingTheatreCount",
        "claimed_value": 5,
        "source_type": "public_website",
        "source_ref": "bvs-facilities-public-2026",
        "source_url": "https://www.bristolvetspecialists.co.uk/about-us/facilities/",
        "confidence": "publicly_evidenced",
        "notes": "Current public facilities page describes five operating theatres.",
    },
    {
        "claim_ref": "bvs-internal-theatre-count-11",
        "entity_type": "area",
        "entity_ref": "theatre-suite",
        "field_name": "operatingTheatreCount",
        "claimed_value": 11,
        "source_type": "internal_report",
        "source_ref": "lucyworks-project-context",
        "source_url": None,
        "confidence": "unverified",
        "notes": "Earlier internal project information stated 11 theatres; hospital confirmation required.",
    },
    {
        "claim_ref": "bvs-public-24-7",
        "entity_type": "premises",
        "entity_ref": PREMISES_REF,
        "field_name": "operatingModel",
        "claimed_value": "24/7 referral hospital",
        "source_type": "public_website",
        "source_ref": "bvs-public-operating-model-2026",
        "source_url": "https://www.bristolvetspecialists.co.uk/",
        "confidence": "publicly_evidenced",
        "notes": "Public operating model; detailed overnight service coverage remains unverified.",
    },
]


_VERIFICATION_TASKS = [
    ("facilities.theatres", "facilities", "How many operating theatres are operational, commissioned and schedulable today?", "The master grid and turnover constraints depend on the real operational count, not marketing terminology.", "Approved room register, floor plan or facilities confirmation", "facilities_manager", "red", ["bvs-public-theatre-count-5", "bvs-internal-theatre-count-11"]),
    ("services.overnight", "services", "Which specialties, diagnostics and support services are physically staffed overnight and which are on-call only?", "24/7 opening does not prove every service has continuous staffed capacity.", "Approved service-hours matrix and on-call policy", "hospital_manager", "red", ["bvs-public-24-7"]),
    ("flow.control", "operations", "Who owns the live hospital-wide theatre, imaging, ward and emergency flow decision at each time of day?", "LucyWorks needs one accountable control role for cross-department conflicts.", "Current escalation chart and role description", "hospital_manager", "red", []),
    ("referral.acceptance", "referrals", "Which roles may accept, decline, redirect or request more information on routine and urgent referrals?", "Referral decisions require explicit authority and response deadlines.", "Referral SOP and delegated-authority matrix", "clinical_director", "red", []),
    ("estimates.overruns", "finance", "Who may approve estimate creation, estimate revision and treatment above an authorised ceiling?", "Financial gates must not be inferred from job titles.", "Estimate and consent policy", "hospital_director", "red", []),
    ("imaging.staffing", "diagnostics", "Are MRI and CT independently staffed, and which competencies are mandatory for operation and anaesthesia support?", "The board must prevent unsafe or impossible imaging assignments.", "Imaging rota, competency matrix and local rules", "head_diagnostic_imaging", "amber", []),
    ("nursing.overnight", "nursing", "What is the overnight nursing command structure for wards, ICU and emergency admissions?", "Escalation and minimum coverage differ materially overnight.", "Night rota and nursing escalation SOP", "head_nursing_services", "red", []),
    ("systems.pims", "integrations", "Which PIMS is authoritative for patient, owner, episode, estimate and billing data?", "Integration mappings require a named source of truth.", "Vendor name, test access and data dictionary", "it_lead", "red", []),
    ("systems.rota", "integrations", "Which system holds contracts, shifts, leave, sickness, on-call and competency data?", "Safe staffing cannot be calculated from manually typed availability alone.", "Workforce-system owner and export/API specification", "hr_lead", "red", []),
    ("systems.lab-imaging", "integrations", "Which laboratory and PACS/RIS systems are used and what interfaces are available?", "Result acknowledgement and imaging readiness depend on real interfaces.", "Vendor interface specifications and sample messages", "it_lead", "amber", []),
    ("wards.capacity", "capacity", "What are the staffed safe capacities for ICU, dog ward, cat ward, isolation and recovery by shift?", "Physical beds do not equal safely staffed capacity.", "Approved capacity and staffing policy", "head_nursing_services", "red", []),
    ("trainee.supervision", "workforce", "Which activities require direct, indirect or retrospective supervision for interns, residents, students and newly competent nurses?", "Titles alone cannot determine privileges.", "Training programme and privilege matrix", "clinical_director", "red", []),
]


def seed_bvs_draft(session: Session, auth: AuthContext) -> dict[str, int]:
    actor_id, actor_name, actor_role = _actor(auth)
    counts = {"configuration": 0, "claims": 0, "tasks": 0, "coverage": 0}
    for entity_type, entity_ref, name, attributes in _DRAFT_CONFIG:
        existing = session.exec(select(HospitalConfigurationRecord).where(
            HospitalConfigurationRecord.premises_ref == PREMISES_REF,
            HospitalConfigurationRecord.entity_type == entity_type,
            HospitalConfigurationRecord.entity_ref == entity_ref,
        )).first()
        if existing:
            continue
        session.add(HospitalConfigurationRecord(
            premises_ref=PREMISES_REF,
            entity_type=entity_type,
            entity_ref=entity_ref,
            name=name,
            attributes=attributes,
            operational_status="draft",
            verification_status="unverified",
            updated_by_actor_id=actor_id,
            updated_by_actor_name=actor_name,
            updated_by_actor_role=actor_role,
        ))
        counts["configuration"] += 1

    for item in _DRAFT_CLAIMS:
        if session.exec(select(ConfigurationClaim).where(ConfigurationClaim.claim_ref == item["claim_ref"])).first():
            continue
        session.add(ConfigurationClaim(
            premises_ref=PREMISES_REF,
            observed_at=utc_now(),
            status="disputed" if item["field_name"] == "operatingTheatreCount" else "proposed",
            version=1,
            created_by_actor_id=actor_id,
            created_by_actor_name=actor_name,
            **item,
        ))
        counts["claims"] += 1

    for task_ref, category, question, why, evidence, accountable, priority, linked_claims in _VERIFICATION_TASKS:
        if session.exec(select(ConfigurationVerificationTask).where(ConfigurationVerificationTask.task_ref == task_ref)).first():
            continue
        session.add(ConfigurationVerificationTask(
            task_ref=task_ref,
            premises_ref=PREMISES_REF,
            category=category,
            question=question,
            why_it_matters=why,
            requested_evidence=evidence,
            accountable_role=accountable,
            priority=priority,
            linked_claim_refs=linked_claims,
        ))
        counts["tasks"] += 1

    defaults = [
        ("coverage.icu.nurse.24h", "emergency-critical-care", "icu", "icu_ecc_nurse", "icu_monitoring", 1),
        ("coverage.theatre.rvn.day", "surgery", "theatre-suite", "registered_veterinary_nurse", "anaesthesia_support", 1),
        ("coverage.imaging.radiographer.day", "diagnostic-imaging", "mri", "diagnostic_radiographer", "mri_operation", 1),
        ("coverage.referrals.coordinator.day", "referrals", None, "referral_coordinator", None, 1),
    ]
    for ref, service_ref, area_ref, role_ref, competency_ref, minimum in defaults:
        if session.exec(select(CoverageRequirement).where(CoverageRequirement.requirement_ref == ref)).first():
            continue
        session.add(CoverageRequirement(
            premises_ref=PREMISES_REF,
            requirement_ref=ref,
            service_ref=service_ref,
            area_ref=area_ref,
            role_ref=role_ref,
            competency_ref=competency_ref,
            minimum_count=minimum,
            verification_status="unverified",
        ))
        counts["coverage"] += 1

    session.flush()
    _evidence(
        session,
        auth,
        event_type="bvs_draft_configuration_seeded",
        action="BVS draft configuration seeded",
        entity_type="hospital_configuration",
        entity_id=PREMISES_REF,
        previous_state=None,
        new_state=counts,
        reason="Create a provisional BVS model from public evidence and explicit verification questions",
    )
    return counts


def dashboard(session: Session) -> dict[str, Any]:
    configs = session.exec(select(HospitalConfigurationRecord).where(HospitalConfigurationRecord.premises_ref == PREMISES_REF)).all()
    claims = session.exec(select(ConfigurationClaim).where(ConfigurationClaim.premises_ref == PREMISES_REF)).all()
    tasks = session.exec(select(ConfigurationVerificationTask).where(ConfigurationVerificationTask.premises_ref == PREMISES_REF)).all()
    workforce = session.exec(select(WorkforceProfile).where(WorkforceProfile.premises_ref == PREMISES_REF)).all()
    competencies = session.exec(select(WorkforceCompetency).where(WorkforceCompetency.premises_ref == PREMISES_REF)).all()
    coverage = session.exec(select(CoverageRequirement).where(CoverageRequirement.premises_ref == PREMISES_REF)).all()
    referrals = session.exec(select(ReferralIntake).where(ReferralIntake.premises_ref == PREMISES_REF).order_by(ReferralIntake.received_at.desc())).all()
    replays = session.exec(select(HistoricalReplayRun).where(HistoricalReplayRun.premises_ref == PREMISES_REF).order_by(HistoricalReplayRun.created_at.desc())).all()

    open_red = sum(1 for task in tasks if task.status != "verified" and task.priority == "red")
    disputed_claims = sum(1 for claim in claims if claim.status == "disputed")
    verified_config = sum(1 for item in configs if item.verification_status == "verified")
    provisional_competencies = sum(1 for item in competencies if item.status != "verified")
    referral_missing = sum(1 for item in referrals if item.missing_information)
    replay_passed = sum(1 for item in replays if item.status == "passed")

    return {
        "premisesRef": PREMISES_REF,
        "configuration": [config_dict(row) for row in configs],
        "claims": [claim_dict(row) for row in claims],
        "verificationTasks": [task_dict(row) for row in tasks],
        "workforce": [workforce_dict(row) for row in workforce],
        "competencies": [competency_dict(row) for row in competencies],
        "coverageRequirements": [coverage_dict(row) for row in coverage],
        "referrals": [referral_dict(row) for row in referrals[:100]],
        "replayRuns": [replay_dict(row) for row in replays[:30]],
        "summary": {
            "configurationRecords": len(configs),
            "verifiedConfiguration": verified_config,
            "claims": len(claims),
            "disputedClaims": disputed_claims,
            "verificationTasks": len(tasks),
            "openRedTasks": open_red,
            "workforceProfiles": len(workforce),
            "provisionalCompetencies": provisional_competencies,
            "coverageRequirements": len(coverage),
            "referrals": len(referrals),
            "referralsMissingInformation": referral_missing,
            "historicalReplays": len(replays),
            "passedReplays": replay_passed,
            "shadowEligible": open_red == 0 and disputed_claims == 0 and verified_config > 0 and replay_passed > 0,
        },
    }


def upsert_configuration(session: Session, entity_type: str, entity_ref: str, payload: dict[str, Any], auth: AuthContext) -> HospitalConfigurationRecord:
    row = session.exec(select(HospitalConfigurationRecord).where(
        HospitalConfigurationRecord.premises_ref == PREMISES_REF,
        HospitalConfigurationRecord.entity_type == entity_type,
        HospitalConfigurationRecord.entity_ref == entity_ref,
    )).first()
    actor_id, actor_name, actor_role = _actor(auth)
    if row:
        expected = int(payload.get("expectedVersion", 0))
        if row.version != expected:
            raise RuntimeError(f"stale configuration version: expected {expected}, current {row.version}")
        before = config_dict(row)
        row.name = str(payload.get("name") or row.name)
        row.attributes = payload.get("attributes", row.attributes)
        row.operational_status = str(payload.get("operationalStatus") or row.operational_status)
        row.verification_status = str(payload.get("verificationStatus") or row.verification_status)
        row.authoritative_source_ref = payload.get("authoritativeSourceRef", row.authoritative_source_ref)
        row.version += 1
        row.updated_by_actor_id = actor_id
        row.updated_by_actor_name = actor_name
        row.updated_by_actor_role = actor_role
        row.updated_at = utc_now()
    else:
        before = None
        row = HospitalConfigurationRecord(
            premises_ref=PREMISES_REF,
            entity_type=entity_type,
            entity_ref=entity_ref,
            name=str(payload["name"]),
            attributes=payload.get("attributes", {}),
            operational_status=str(payload.get("operationalStatus") or "draft"),
            verification_status=str(payload.get("verificationStatus") or "unverified"),
            authoritative_source_ref=payload.get("authoritativeSourceRef"),
            updated_by_actor_id=actor_id,
            updated_by_actor_name=actor_name,
            updated_by_actor_role=actor_role,
        )
        session.add(row)
    session.flush()
    _evidence(session, auth, event_type="hospital_configuration_updated", action=f"{entity_type} configuration updated", entity_type="hospital_configuration", entity_id=f"{entity_type}:{entity_ref}", previous_state=before, new_state=config_dict(row), reason=str(payload.get("reason") or "Hospital configuration maintained"), risk_level="red" if row.verification_status == "verified" else "amber")
    return row


def review_claim(session: Session, claim_ref: str, payload: dict[str, Any], auth: AuthContext) -> ConfigurationClaim:
    row = session.exec(select(ConfigurationClaim).where(ConfigurationClaim.claim_ref == claim_ref)).first()
    if not row:
        raise ValueError("configuration claim not found")
    expected = int(payload.get("expectedVersion", 0))
    if row.version != expected:
        raise RuntimeError(f"stale claim version: expected {expected}, current {row.version}")
    status = str(payload.get("status") or "")
    if status not in {"verified", "rejected", "disputed", "superseded"}:
        raise ValueError("claim status must be verified, rejected, disputed or superseded")
    if status == "verified" and not str(payload.get("evidenceRef") or "").strip():
        raise ValueError("evidenceRef is required to verify a claim")
    before = claim_dict(row)
    actor_id, actor_name, _ = _actor(auth)
    row.status = status
    row.notes = str(payload.get("notes") or row.notes or "")
    row.reviewed_by_actor_id = actor_id
    row.reviewed_by_actor_name = actor_name
    row.reviewed_at = utc_now()
    row.version += 1
    session.flush()
    _evidence(session, auth, event_type="configuration_claim_reviewed", action=f"configuration claim marked {status}", entity_type="configuration_claim", entity_id=claim_ref, previous_state=before, new_state=claim_dict(row), reason=str(payload.get("reason") or payload.get("notes") or status), risk_level="red" if status == "verified" else "amber")
    return row


def answer_verification_task(session: Session, task_ref: str, payload: dict[str, Any], auth: AuthContext) -> ConfigurationVerificationTask:
    row = session.exec(select(ConfigurationVerificationTask).where(ConfigurationVerificationTask.task_ref == task_ref)).first()
    if not row:
        raise ValueError("verification task not found")
    expected = int(payload.get("expectedVersion", 0))
    if row.version != expected:
        raise RuntimeError(f"stale task version: expected {expected}, current {row.version}")
    answer = str(payload.get("answer") or "").strip()
    evidence_refs = [str(item).strip() for item in payload.get("evidenceRefs", []) if str(item).strip()]
    status = str(payload.get("status") or "answered")
    if status == "verified" and (not answer or not evidence_refs):
        raise ValueError("verified tasks require an answer and at least one evidence reference")
    before = task_dict(row)
    actor_id, actor_name, actor_role = _actor(auth)
    row.answer = answer
    row.evidence_refs = evidence_refs
    row.status = status
    row.answered_by_actor_id = actor_id
    row.answered_by_actor_name = actor_name
    row.answered_by_actor_role = actor_role
    row.answered_at = utc_now()
    row.version += 1
    session.flush()
    _evidence(session, auth, event_type="configuration_verification_answered", action=f"verification task marked {status}", entity_type="configuration_verification_task", entity_id=task_ref, previous_state=before, new_state=task_dict(row), reason=str(payload.get("reason") or answer), risk_level="red" if row.priority == "red" else "amber")
    return row


def upsert_workforce(session: Session, staff_ref: str, payload: dict[str, Any], auth: AuthContext) -> WorkforceProfile:
    row = session.exec(select(WorkforceProfile).where(WorkforceProfile.premises_ref == PREMISES_REF, WorkforceProfile.staff_ref == staff_ref)).first()
    actor_id, actor_name, _ = _actor(auth)
    if row:
        expected = int(payload.get("expectedVersion", 0))
        if row.version != expected:
            raise RuntimeError(f"stale workforce version: expected {expected}, current {row.version}")
        before = workforce_dict(row)
        for attr, key in {
            "display_name": "displayName", "employment_status": "employmentStatus", "primary_role_ref": "primaryRoleRef",
            "department_ref": "departmentRef", "grade_or_training_level": "gradeOrTrainingLevel", "registration_body": "registrationBody",
            "registration_number": "registrationNumber", "contracted_hours_weekly": "contractedHoursWeekly",
            "maximum_safe_hours_weekly": "maximumSafeHoursWeekly", "supervisor_staff_ref": "supervisorStaffRef",
            "on_call_eligible": "onCallEligible", "source_status": "sourceStatus",
        }.items():
            if key in payload:
                setattr(row, attr, payload[key])
        row.version += 1
        row.updated_by_actor_id = actor_id
        row.updated_by_actor_name = actor_name
        row.updated_at = utc_now()
    else:
        before = None
        row = WorkforceProfile(
            premises_ref=PREMISES_REF,
            staff_ref=staff_ref,
            display_name=str(payload["displayName"]),
            employment_status=str(payload.get("employmentStatus") or "active"),
            primary_role_ref=str(payload["primaryRoleRef"]),
            department_ref=str(payload["departmentRef"]),
            grade_or_training_level=payload.get("gradeOrTrainingLevel"),
            registration_body=payload.get("registrationBody"),
            registration_number=payload.get("registrationNumber"),
            contracted_hours_weekly=payload.get("contractedHoursWeekly"),
            maximum_safe_hours_weekly=payload.get("maximumSafeHoursWeekly"),
            supervisor_staff_ref=payload.get("supervisorStaffRef"),
            on_call_eligible=bool(payload.get("onCallEligible", False)),
            source_status=str(payload.get("sourceStatus") or "draft"),
            updated_by_actor_id=actor_id,
            updated_by_actor_name=actor_name,
        )
        session.add(row)
    session.flush()
    _evidence(session, auth, event_type="workforce_profile_updated", action="workforce profile updated", entity_type="workforce_profile", entity_id=staff_ref, previous_state=before, new_state=workforce_dict(row), reason=str(payload.get("reason") or "Workforce profile maintained"))
    return row


def upsert_competency(session: Session, staff_ref: str, competency_ref: str, scope_ref: str, payload: dict[str, Any], auth: AuthContext) -> WorkforceCompetency:
    row = session.exec(select(WorkforceCompetency).where(
        WorkforceCompetency.premises_ref == PREMISES_REF,
        WorkforceCompetency.staff_ref == staff_ref,
        WorkforceCompetency.competency_ref == competency_ref,
        WorkforceCompetency.scope_ref == scope_ref,
    )).first()
    if row:
        expected = int(payload.get("expectedVersion", 0))
        if row.version != expected:
            raise RuntimeError(f"stale competency version: expected {expected}, current {row.version}")
        before = competency_dict(row)
    else:
        before = None
        row = WorkforceCompetency(premises_ref=PREMISES_REF, staff_ref=staff_ref, competency_ref=competency_ref, scope_ref=scope_ref)
        session.add(row)
    row.level = str(payload.get("level") or row.level)
    row.status = str(payload.get("status") or row.status)
    row.evidence_summary = payload.get("evidenceSummary", row.evidence_summary)
    row.valid_from = date.fromisoformat(payload["validFrom"]) if payload.get("validFrom") else row.valid_from
    row.valid_until = date.fromisoformat(payload["validUntil"]) if payload.get("validUntil") else row.valid_until
    if row.status == "verified":
        if not row.evidence_summary:
            raise ValueError("verified competency requires evidenceSummary")
        actor_id, actor_name, _ = _actor(auth)
        row.verified_by_actor_id = actor_id
        row.verified_by_actor_name = actor_name
        row.verified_at = utc_now()
    if row.id is not None:
        row.version += 1
    session.flush()
    _evidence(session, auth, event_type="workforce_competency_updated", action=f"competency marked {row.status}", entity_type="workforce_competency", entity_id=f"{staff_ref}:{competency_ref}:{scope_ref}", previous_state=before, new_state=competency_dict(row), reason=str(payload.get("reason") or row.evidence_summary or "Competency maintained"), risk_level="red" if row.status == "verified" else "amber")
    return row


def create_referral(session: Session, payload: dict[str, Any], auth: AuthContext) -> ReferralIntake:
    referral_ref = str(payload.get("referralRef") or f"REF-{utc_now().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}")
    if session.exec(select(ReferralIntake).where(ReferralIntake.referral_ref == referral_ref)).first():
        raise RuntimeError("referral reference already exists")
    required = payload.get("requiredInformation") or {
        "patientAndOwner": bool(payload.get("patientName") and payload.get("ownerName")),
        "clinicalHistory": bool(payload.get("historySummary")),
        "presentingProblem": bool(payload.get("presentingProblem")),
        "referringPractice": bool(payload.get("referringPractice")),
        "requestedService": bool(payload.get("requestedServiceRef")),
    }
    missing = [key for key, complete in required.items() if not complete]
    urgency = str(payload.get("urgency") or "routine")
    response_minutes = 30 if urgency in {"emergency", "critical"} else 240 if urgency == "urgent" else 1440
    actor_id, actor_name, actor_role = _actor(auth)
    row = ReferralIntake(
        referral_ref=referral_ref,
        premises_ref=PREMISES_REF,
        source_channel=str(payload.get("sourceChannel") or "portal"),
        urgency=urgency,
        referring_practice=str(payload["referringPractice"]),
        referring_vet=payload.get("referringVet"),
        practice_contact=payload.get("practiceContact"),
        patient_name=str(payload["patientName"]),
        species=str(payload["species"]),
        owner_name=str(payload["ownerName"]),
        owner_contact=payload.get("ownerContact"),
        requested_service_ref=payload.get("requestedServiceRef"),
        presenting_problem=str(payload["presentingProblem"]),
        history_summary=payload.get("historySummary"),
        insurance_status=str(payload.get("insuranceStatus") or "unknown"),
        attachment_manifest=payload.get("attachmentManifest", []),
        required_information=required,
        missing_information=missing,
        status="information_requested" if missing else "ready_for_clinical_review",
        assigned_role="referral_coordinator",
        assigned_actor_id=actor_id,
        assigned_actor_name=actor_name,
        response_due_at=utc_now() + timedelta(minutes=response_minutes),
        created_by_actor_id=actor_id,
        created_by_actor_name=actor_name,
    )
    session.add(row)
    session.flush()
    session.add(ReferralIntakeEvent(referral_ref=referral_ref, event_type="referral_received", new_status=row.status, detail={"missingInformation": missing}, actor_id=actor_id, actor_name=actor_name, actor_role=actor_role))
    _evidence(session, auth, event_type="referral_intake_created", action="referral intake created", entity_type="referral_intake", entity_id=referral_ref, previous_state=None, new_state=referral_dict(row), reason="Referral received and information completeness assessed", risk_level="red" if urgency in {"emergency", "critical"} else "amber")
    return row


_REFERRAL_TRANSITIONS = {
    "received": {"information_requested", "ready_for_clinical_review"},
    "information_requested": {"ready_for_clinical_review", "declined", "redirected"},
    "ready_for_clinical_review": {"accepted", "declined", "redirected", "information_requested"},
    "accepted": {"booked", "emergency_transfer", "cancelled"},
    "booked": {"arrived", "cancelled"},
    "emergency_transfer": {"arrived", "cancelled"},
    "arrived": set(),
    "declined": set(),
    "redirected": set(),
    "cancelled": set(),
}


def transition_referral(session: Session, referral_ref: str, payload: dict[str, Any], auth: AuthContext) -> ReferralIntake:
    row = session.exec(select(ReferralIntake).where(ReferralIntake.referral_ref == referral_ref)).first()
    if not row:
        raise ValueError("referral not found")
    expected = int(payload.get("expectedVersion", 0))
    if row.version != expected:
        raise RuntimeError(f"stale referral version: expected {expected}, current {row.version}")
    new_status = str(payload.get("status") or "")
    allowed = _REFERRAL_TRANSITIONS.get(row.status, set())
    if new_status not in allowed:
        raise ValueError(f"transition {row.status} -> {new_status} is not permitted")
    if new_status in {"accepted", "declined", "redirected"} and not str(payload.get("decisionReason") or "").strip():
        raise ValueError("decisionReason is required for referral decisions")
    if new_status in {"ready_for_clinical_review", "accepted", "booked", "emergency_transfer"} and row.missing_information:
        raise RuntimeError(f"referral cannot progress with missing information: {', '.join(row.missing_information)}")
    before = referral_dict(row)
    previous = row.status
    actor_id, actor_name, actor_role = _actor(auth)
    row.status = new_status
    row.decision = payload.get("decision", row.decision)
    row.decision_reason = payload.get("decisionReason", row.decision_reason)
    row.assigned_role = str(payload.get("assignedRole") or row.assigned_role)
    row.assigned_actor_id = payload.get("assignedActorId", actor_id)
    row.assigned_actor_name = payload.get("assignedActorName", actor_name)
    if "requiredInformation" in payload:
        row.required_information = payload["requiredInformation"]
        row.missing_information = [key for key, complete in row.required_information.items() if not complete]
    row.version += 1
    row.updated_at = utc_now()
    session.add(ReferralIntakeEvent(referral_ref=referral_ref, event_type="referral_status_changed", previous_status=previous, new_status=new_status, detail={"decision": row.decision, "reason": row.decision_reason}, actor_id=actor_id, actor_name=actor_name, actor_role=actor_role))
    session.flush()
    _evidence(session, auth, event_type="referral_intake_transition", action=f"referral moved to {new_status}", entity_type="referral_intake", entity_id=referral_ref, previous_state=before, new_state=referral_dict(row), reason=str(payload.get("decisionReason") or payload.get("reason") or new_status), risk_level="red" if new_status in {"accepted", "declined", "emergency_transfer"} else "amber")
    return row


def update_referral_information(session: Session, referral_ref: str, payload: dict[str, Any], auth: AuthContext) -> ReferralIntake:
    row = session.exec(select(ReferralIntake).where(ReferralIntake.referral_ref == referral_ref)).first()
    if not row:
        raise ValueError("referral not found")
    expected = int(payload.get("expectedVersion", 0))
    if row.version != expected:
        raise RuntimeError(f"stale referral version: expected {expected}, current {row.version}")
    before = referral_dict(row)
    if "historySummary" in payload:
        row.history_summary = payload["historySummary"]
    if "attachmentManifest" in payload:
        row.attachment_manifest = payload["attachmentManifest"]
    if "requestedServiceRef" in payload:
        row.requested_service_ref = payload["requestedServiceRef"]
    required = payload.get("requiredInformation", row.required_information)
    row.required_information = required
    row.missing_information = [key for key, complete in required.items() if not complete]
    if not row.missing_information and row.status == "information_requested":
        row.status = "ready_for_clinical_review"
    row.version += 1
    row.updated_at = utc_now()
    session.flush()
    _evidence(session, auth, event_type="referral_information_updated", action="referral information updated", entity_type="referral_intake", entity_id=referral_ref, previous_state=before, new_state=referral_dict(row), reason=str(payload.get("reason") or "Missing referral information updated"))
    return row


def create_replay(session: Session, payload: dict[str, Any], auth: AuthContext) -> HistoricalReplayRun:
    run_ref = str(payload.get("runRef") or f"REPLAY-{date.fromisoformat(payload['sourceDate']).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}")
    if session.exec(select(HistoricalReplayRun).where(HistoricalReplayRun.run_ref == run_ref)).first():
        raise RuntimeError("replay reference already exists")
    events = payload.get("events", [])
    if not events:
        raise ValueError("historical replay requires events")
    if str(payload.get("dataClassification") or "anonymised") != "anonymised":
        raise ValueError("v6 historical replay accepts anonymised data only")
    actor_id, actor_name, _ = _actor(auth)
    row = HistoricalReplayRun(run_ref=run_ref, premises_ref=PREMISES_REF, source_date=date.fromisoformat(payload["sourceDate"]), data_classification="anonymised", status="processing", event_count=len(events), created_by_actor_id=actor_id, created_by_actor_name=actor_name)
    session.add(row)
    session.flush()
    for index, item in enumerate(events):
        occurred_at = datetime.fromisoformat(str(item["occurredAt"]).replace("Z", "+00:00"))
        session.add(HistoricalReplayEvent(run_ref=run_ref, event_ref=str(item.get("eventRef") or f"event-{index+1}"), occurred_at=occurred_at, event_type=str(item["eventType"]), episode_ref=item.get("episodeRef"), area_ref=item.get("areaRef"), staff_refs=item.get("staffRefs", []), payload=item.get("payload", {})))
    session.flush()
    analyse_replay(session, row)
    _evidence(session, auth, event_type="historical_replay_created", action="historical hospital day replayed", entity_type="historical_replay", entity_id=run_ref, previous_state=None, new_state=replay_dict(row), reason="Evaluate LucyWorks against anonymised historical hospital activity")
    return row


def analyse_replay(session: Session, run: HistoricalReplayRun) -> None:
    events = session.exec(select(HistoricalReplayEvent).where(HistoricalReplayEvent.run_ref == run.run_ref).order_by(HistoricalReplayEvent.occurred_at)).all()
    delays = [event for event in events if event.event_type in {"delay", "overrun"}]
    handovers = [event for event in events if event.event_type == "handover"]
    missing_handover = [event for event in handovers if not event.payload.get("acknowledged")]
    capacity_breaches = [event for event in events if event.event_type == "capacity" and event.payload.get("occupied", 0) > event.payload.get("safeCapacity", 999999)]
    conflicts = [event for event in events if event.event_type in {"staff_conflict", "room_conflict", "equipment_conflict"}]
    alerts_expected = [event for event in events if event.payload.get("expectedAlert")]
    alerts_detected = [event for event in events if event.payload.get("lucyworksDetected")]
    missed = [event for event in alerts_expected if not event.payload.get("lucyworksDetected")]
    false_positive = [event for event in alerts_detected if not event.payload.get("expectedAlert")]
    decision_latency = [float(event.payload["decisionLatencyMinutes"]) for event in events if event.payload.get("decisionLatencyMinutes") is not None]
    findings: list[dict[str, Any]] = []
    for event in missed:
        findings.append({"severity": "red", "eventRef": event.event_ref, "finding": "Expected operational alert was missed"})
    for event in false_positive:
        findings.append({"severity": "amber", "eventRef": event.event_ref, "finding": "LucyWorks produced an alert not expected by the historical reviewer"})
    for event in capacity_breaches:
        findings.append({"severity": "red", "eventRef": event.event_ref, "finding": "Safe staffed capacity was exceeded"})
    run.metrics = {
        "events": len(events),
        "delaysOrOverruns": len(delays),
        "unacknowledgedHandovers": len(missing_handover),
        "capacityBreaches": len(capacity_breaches),
        "resourceConflicts": len(conflicts),
        "expectedAlerts": len(alerts_expected),
        "detectedAlerts": len(alerts_detected),
        "missedAlerts": len(missed),
        "falsePositiveAlerts": len(false_positive),
        "averageDecisionLatencyMinutes": round(sum(decision_latency) / len(decision_latency), 2) if decision_latency else None,
    }
    run.findings = findings
    run.status = "passed" if not any(item["severity"] == "red" for item in findings) else "failed"
    run.completed_at = utc_now()


def coverage_assessment(session: Session) -> dict[str, Any]:
    requirements = session.exec(select(CoverageRequirement).where(CoverageRequirement.premises_ref == PREMISES_REF)).all()
    workforce = session.exec(select(WorkforceProfile).where(WorkforceProfile.premises_ref == PREMISES_REF, WorkforceProfile.employment_status == "active")).all()
    competencies = session.exec(select(WorkforceCompetency).where(WorkforceCompetency.premises_ref == PREMISES_REF, WorkforceCompetency.status == "verified")).all()
    competency_index = {(item.staff_ref, item.competency_ref) for item in competencies if not item.valid_until or item.valid_until >= date.today()}
    results = []
    for req in requirements:
        candidates = [person for person in workforce if person.primary_role_ref == req.role_ref and (not req.competency_ref or (person.staff_ref, req.competency_ref) in competency_index)]
        results.append({
            "requirement": coverage_dict(req),
            "candidateCount": len(candidates),
            "candidateStaffRefs": [person.staff_ref for person in candidates],
            "gap": max(0, req.minimum_count - len(candidates)),
            "status": "met" if len(candidates) >= req.minimum_count else "gap",
            "note": "This is a credential/capability pool check, not a shift-level rota check." if candidates else "No verified eligible workforce profile found.",
        })
    return {"premisesRef": PREMISES_REF, "results": results, "gapCount": sum(1 for item in results if item["status"] == "gap")}
