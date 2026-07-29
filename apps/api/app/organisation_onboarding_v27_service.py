from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import ALLOWED_ROLES, CLINICAL_ROLES, SENIOR_ROLES, AuthContext
from app.bvs_v6_models import HospitalConfigurationRecord, WorkforceCompetency, WorkforceProfile
from app.evidence_service import create_evidence_event
from app.operational_context_v26_models import OrganisationV26, SiteMembershipV26, SiteV26
from app.organisation_onboarding_v27_models import (
    ConfigurationChangeV27,
    ConfigurationReleaseV27,
    OnboardingDepartmentV27,
    OnboardingEquipmentV27,
    OnboardingOrganisationV27,
    OnboardingRoomV27,
    OnboardingServiceV27,
    OnboardingSiteV27,
    OnboardingStaffV27,
    SitePolicyV27,
    StaffAccessApprovalV27,
    StaffCompetencyV27,
    StaffCredentialV27,
    StaffImportBatchV27,
    utc_now,
)

REQUIRED_POLICY_KEYS = {
    "fatigue_and_safe_staffing",
    "patient_safety_escalation",
    "service_restriction",
    "safeguarding",
    "data_retention",
    "downtime_and_recovery",
}
CONFIGURATION_ADMIN_ROLES = set(SENIOR_ROLES) | {"admin", "hr"}


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def require_configuration_admin(auth: AuthContext) -> None:
    if auth.role not in CONFIGURATION_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="configuration administrator or senior role required")


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def organisation_dict(row: OnboardingOrganisationV27) -> dict[str, Any]:
    return {
        "organisationRef": row.organisation_ref,
        "legalName": row.legal_name,
        "tradingName": row.trading_name,
        "companyNumber": row.company_number,
        "countryCode": row.country_code,
        "registeredAddress": row.registered_address,
        "dataControllerName": row.data_controller_name,
        "dataControllerEmail": row.data_controller_email,
        "accountableExecutiveSubject": row.accountable_executive_subject,
        "accountableExecutiveName": row.accountable_executive_name,
        "status": row.status,
        "version": row.version,
        "updatedAt": row.updated_at.isoformat(),
    }


def site_dict(row: OnboardingSiteV27) -> dict[str, Any]:
    return {
        "siteRef": row.site_ref,
        "organisationRef": row.organisation_ref,
        "premisesRef": row.premises_ref,
        "name": row.name,
        "siteType": row.site_type,
        "timezone": row.timezone_name,
        "address": row.address,
        "regulatorPremisesRefs": row.regulator_premises_refs,
        "emergencyStatus": row.emergency_status,
        "accountableDirectorSubject": row.accountable_director_subject,
        "accountableDirectorName": row.accountable_director_name,
        "clinicalGovernanceSubject": row.clinical_governance_subject,
        "clinicalGovernanceName": row.clinical_governance_name,
        "status": row.status,
        "activeReleaseRef": row.active_release_ref,
        "version": row.version,
        "updatedAt": row.updated_at.isoformat(),
    }


def department_dict(row: OnboardingDepartmentV27) -> dict[str, Any]:
    return {
        "departmentRef": row.department_ref,
        "name": row.name,
        "departmentType": row.department_type,
        "accountableRole": row.accountable_role,
        "accountableSubject": row.accountable_subject,
        "status": row.status,
        "attributes": row.attributes,
        "version": row.version,
    }


def service_dict(row: OnboardingServiceV27) -> dict[str, Any]:
    return {
        "serviceRef": row.service_ref,
        "departmentRef": row.department_ref,
        "name": row.name,
        "serviceType": row.service_type,
        "clinicalService": row.clinical_service,
        "operationalStatus": row.operational_status,
        "hours": row.hours,
        "capabilities": row.capabilities,
        "minimumStaffing": row.minimum_staffing,
        "requiredEquipmentRefs": row.required_equipment_refs,
        "escalationRole": row.escalation_role,
        "version": row.version,
    }


def room_dict(row: OnboardingRoomV27) -> dict[str, Any]:
    return {
        "roomRef": row.room_ref,
        "departmentRef": row.department_ref,
        "name": row.name,
        "roomType": row.room_type,
        "serviceRefs": row.service_refs,
        "infectionControlZone": row.infection_control_zone,
        "capacity": row.capacity,
        "operationalStatus": row.operational_status,
        "attributes": row.attributes,
        "version": row.version,
    }


def equipment_dict(row: OnboardingEquipmentV27) -> dict[str, Any]:
    return {
        "equipmentRef": row.equipment_ref,
        "name": row.name,
        "equipmentType": row.equipment_type,
        "roomRef": row.room_ref,
        "serviceRefs": row.service_refs,
        "assetIdentifier": row.asset_identifier,
        "maintenanceStatus": row.maintenance_status,
        "maintenanceDueAt": row.maintenance_due_at.isoformat() if row.maintenance_due_at else None,
        "operationalStatus": row.operational_status,
        "attributes": row.attributes,
        "version": row.version,
    }


def staff_dict(row: OnboardingStaffV27) -> dict[str, Any]:
    return {
        "staffRef": row.staff_ref,
        "displayName": row.display_name,
        "email": row.email,
        "authSubject": row.auth_subject,
        "identityStatus": row.identity_status,
        "employmentStatus": row.employment_status,
        "departmentRef": row.department_ref,
        "requestedRole": row.requested_role,
        "primaryRoleRef": row.primary_role_ref,
        "gradeOrTrainingLevel": row.grade_or_training_level,
        "contractedHoursWeekly": row.contracted_hours_weekly,
        "maximumSafeHoursWeekly": row.maximum_safe_hours_weekly,
        "supervisorStaffRef": row.supervisor_staff_ref,
        "onCallEligible": row.on_call_eligible,
        "accessStatus": row.access_status,
        "clinicalAuthorityStatus": row.clinical_authority_status,
        "sourceBatchRef": row.source_batch_ref,
        "version": row.version,
    }


def credential_dict(row: StaffCredentialV27) -> dict[str, Any]:
    return {
        "credentialRef": row.credential_ref,
        "staffRef": row.staff_ref,
        "credentialType": row.credential_type,
        "issuingBody": row.issuing_body,
        "credentialNumber": row.credential_number,
        "validFrom": row.valid_from.isoformat() if row.valid_from else None,
        "validUntil": row.valid_until.isoformat() if row.valid_until else None,
        "verificationStatus": row.verification_status,
        "evidenceRefs": row.evidence_refs,
        "verifiedBySubject": row.verified_by_subject,
        "verifiedAt": row.verified_at.isoformat() if row.verified_at else None,
        "version": row.version,
    }


def competency_dict(row: StaffCompetencyV27) -> dict[str, Any]:
    return {
        "competencyRecordRef": row.competency_record_ref,
        "staffRef": row.staff_ref,
        "competencyRef": row.competency_ref,
        "scopeRef": row.scope_ref,
        "level": row.level,
        "verificationStatus": row.verification_status,
        "evidenceSummary": row.evidence_summary,
        "evidenceRefs": row.evidence_refs,
        "validFrom": row.valid_from.isoformat() if row.valid_from else None,
        "validUntil": row.valid_until.isoformat() if row.valid_until else None,
        "verifiedBySubject": row.verified_by_subject,
        "verifiedAt": row.verified_at.isoformat() if row.verified_at else None,
        "version": row.version,
    }


def policy_dict(row: SitePolicyV27) -> dict[str, Any]:
    return {
        "policyKey": row.policy_key,
        "title": row.title,
        "policyVersion": row.policy_version,
        "status": row.status,
        "rules": row.rules,
        "ownerRole": row.owner_role,
        "ownerSubject": row.owner_subject,
        "effectiveFrom": row.effective_from.isoformat() if row.effective_from else None,
        "reviewDueAt": row.review_due_at.isoformat() if row.review_due_at else None,
        "evidenceRefs": row.evidence_refs,
        "version": row.version,
    }


def release_dict(row: ConfigurationReleaseV27, *, include_snapshot: bool = False) -> dict[str, Any]:
    value = {
        "releaseRef": row.release_ref,
        "organisationRef": row.organisation_ref,
        "siteRef": row.site_ref,
        "premisesRef": row.premises_ref,
        "releaseVersion": row.release_version,
        "status": row.status,
        "snapshotHash": row.snapshot_hash,
        "readinessSummary": row.readiness_summary,
        "effectiveAt": row.effective_at.isoformat(),
        "approvedBySubject": row.approved_by_subject,
        "approvedByName": row.approved_by_name,
        "approvedByRole": row.approved_by_role,
        "reason": row.reason,
        "rollbackOfReleaseRef": row.rollback_of_release_ref,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat(),
    }
    if include_snapshot:
        value["snapshot"] = row.snapshot
    return value


def change_dict(row: ConfigurationChangeV27) -> dict[str, Any]:
    return {
        "changeRef": row.change_ref,
        "organisationRef": row.organisation_ref,
        "siteRef": row.site_ref,
        "premisesRef": row.premises_ref,
        "entityType": row.entity_type,
        "entityRef": row.entity_ref,
        "action": row.action,
        "previousState": row.previous_state,
        "newState": row.new_state,
        "reason": row.reason,
        "actor": {"subject": row.actor_subject, "name": row.actor_name, "role": row.actor_role},
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat(),
    }


def _assert_version(existing: Any, expected_version: int | None) -> None:
    if existing is not None and expected_version is not None and existing.version != expected_version:
        raise HTTPException(status_code=409, detail={
            "code": "stale_configuration_write",
            "expectedVersion": existing.version,
            "suppliedVersion": expected_version,
        })


def _record_change(
    session: Session,
    auth: AuthContext,
    *,
    organisation_ref: str,
    site_ref: str | None,
    premises_ref: str | None,
    entity_type: str,
    entity_ref: str,
    action: str,
    previous_state: dict[str, Any],
    new_state: dict[str, Any],
    reason: str,
) -> ConfigurationChangeV27:
    row = ConfigurationChangeV27(
        change_ref=new_ref("config-change"),
        organisation_ref=organisation_ref,
        site_ref=site_ref,
        premises_ref=premises_ref,
        entity_type=entity_type,
        entity_ref=entity_ref,
        action=action,
        previous_state=json_safe(previous_state),
        new_state=json_safe(new_state),
        reason=reason,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="hospital_configuration_changed",
        action=f"{action} {entity_type}",
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=json_safe(previous_state),
        new_state=json_safe(new_state),
        reason=reason,
        compliance_domain="operational_governance",
        risk_level="amber",
        source_module="organisation-onboarding-v27",
        source_record_ref=row.change_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"configuration-change:{row.change_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    return row


def _mark_site_pending(session: Session, site_ref: str) -> None:
    site = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == site_ref)).first()
    if site and site.active_release_ref:
        site.status = "changes_pending"
        site.updated_at = utc_now()
        session.add(site)


def save_organisation(session: Session, auth: AuthContext, payload: dict[str, Any]) -> OnboardingOrganisationV27:
    require_configuration_admin(auth)
    organisation_ref = str(payload.get("organisationRef") or "").strip()
    if not organisation_ref:
        raise HTTPException(status_code=422, detail="organisationRef is required")
    existing = session.exec(select(OnboardingOrganisationV27).where(
        OnboardingOrganisationV27.organisation_ref == organisation_ref
    )).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = organisation_dict(existing) if existing else {}
    row = existing or OnboardingOrganisationV27(
        organisation_ref=organisation_ref,
        legal_name=str(payload.get("legalName") or organisation_ref),
        updated_by_subject=auth.subject,
        updated_by_name=auth.actor_name,
        updated_by_role=auth.role,
    )
    row.legal_name = str(payload.get("legalName") or row.legal_name).strip()
    row.trading_name = payload.get("tradingName", row.trading_name)
    row.company_number = payload.get("companyNumber", row.company_number)
    row.country_code = str(payload.get("countryCode") or row.country_code or "GB").upper()
    row.registered_address = dict(payload.get("registeredAddress") or row.registered_address or {})
    row.data_controller_name = payload.get("dataControllerName", row.data_controller_name)
    row.data_controller_email = payload.get("dataControllerEmail", row.data_controller_email)
    row.accountable_executive_subject = payload.get("accountableExecutiveSubject", row.accountable_executive_subject)
    row.accountable_executive_name = payload.get("accountableExecutiveName", row.accountable_executive_name)
    row.status = "changes_pending" if existing and existing.status == "approved" else "draft"
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_by_name = auth.actor_name
    row.updated_by_role = auth.role
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _record_change(
        session, auth,
        organisation_ref=organisation_ref,
        site_ref=None,
        premises_ref=None,
        entity_type="organisation",
        entity_ref=organisation_ref,
        action="updated" if existing else "created",
        previous_state=previous,
        new_state=organisation_dict(row),
        reason=str(payload.get("reason") or "Organisation onboarding record updated"),
    )
    return row


def save_site(session: Session, auth: AuthContext, payload: dict[str, Any]) -> OnboardingSiteV27:
    require_configuration_admin(auth)
    site_ref = str(payload.get("siteRef") or "").strip()
    organisation_ref = str(payload.get("organisationRef") or "").strip()
    premises_ref = str(payload.get("premisesRef") or site_ref).strip()
    if not site_ref or not organisation_ref:
        raise HTTPException(status_code=422, detail="siteRef and organisationRef are required")
    if premises_ref == "default-premises":
        raise HTTPException(status_code=409, detail={"code": "default_premises_forbidden"})
    organisation = session.exec(select(OnboardingOrganisationV27).where(
        OnboardingOrganisationV27.organisation_ref == organisation_ref
    )).first()
    if not organisation:
        raise HTTPException(status_code=409, detail="organisation onboarding record not found")
    existing = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == site_ref)).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = site_dict(existing) if existing else {}
    row = existing or OnboardingSiteV27(
        site_ref=site_ref,
        organisation_ref=organisation_ref,
        premises_ref=premises_ref,
        name=str(payload.get("name") or site_ref),
        updated_by_subject=auth.subject,
        updated_by_name=auth.actor_name,
        updated_by_role=auth.role,
    )
    if existing and (row.organisation_ref != organisation_ref or row.premises_ref != premises_ref):
        raise HTTPException(status_code=409, detail="site organisation and premises identity cannot be rewritten")
    row.name = str(payload.get("name") or row.name).strip()
    row.site_type = str(payload.get("siteType") or row.site_type)
    row.timezone_name = str(payload.get("timezone") or row.timezone_name)
    row.address = dict(payload.get("address") or row.address or {})
    row.regulator_premises_refs = [str(item) for item in payload.get("regulatorPremisesRefs", row.regulator_premises_refs) if item]
    row.emergency_status = str(payload.get("emergencyStatus") or row.emergency_status)
    row.accountable_director_subject = payload.get("accountableDirectorSubject", row.accountable_director_subject)
    row.accountable_director_name = payload.get("accountableDirectorName", row.accountable_director_name)
    row.clinical_governance_subject = payload.get("clinicalGovernanceSubject", row.clinical_governance_subject)
    row.clinical_governance_name = payload.get("clinicalGovernanceName", row.clinical_governance_name)
    row.status = "changes_pending" if existing and existing.active_release_ref else "draft"
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_by_name = auth.actor_name
    row.updated_by_role = auth.role
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _record_change(
        session, auth,
        organisation_ref=organisation_ref,
        site_ref=site_ref,
        premises_ref=premises_ref,
        entity_type="site",
        entity_ref=site_ref,
        action="updated" if existing else "created",
        previous_state=previous,
        new_state=site_dict(row),
        reason=str(payload.get("reason") or "Hospital site onboarding record updated"),
    )
    return row


def _site_required(session: Session, site_ref: str) -> OnboardingSiteV27:
    row = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == site_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="onboarding site not found")
    return row


def save_department(session: Session, auth: AuthContext, payload: dict[str, Any]) -> OnboardingDepartmentV27:
    require_configuration_admin(auth)
    site = _site_required(session, str(payload.get("siteRef") or ""))
    ref = str(payload.get("departmentRef") or "").strip()
    if not ref:
        raise HTTPException(status_code=422, detail="departmentRef is required")
    existing = session.exec(select(OnboardingDepartmentV27).where(
        OnboardingDepartmentV27.site_ref == site.site_ref,
        OnboardingDepartmentV27.department_ref == ref,
    )).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = department_dict(existing) if existing else {}
    row = existing or OnboardingDepartmentV27(
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        department_ref=ref,
        name=str(payload.get("name") or ref),
        updated_by_subject=auth.subject,
    )
    row.name = str(payload.get("name") or row.name)
    row.department_type = str(payload.get("departmentType") or row.department_type)
    row.accountable_role = str(payload.get("accountableRole") or row.accountable_role)
    row.accountable_subject = payload.get("accountableSubject", row.accountable_subject)
    row.status = str(payload.get("status") or "draft")
    row.attributes = dict(payload.get("attributes") or row.attributes or {})
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _mark_site_pending(session, site.site_ref)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="department", entity_ref=ref,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=department_dict(row), reason=str(payload.get("reason") or "Department configuration updated"))
    return row


def save_service(session: Session, auth: AuthContext, payload: dict[str, Any]) -> OnboardingServiceV27:
    require_configuration_admin(auth)
    site = _site_required(session, str(payload.get("siteRef") or ""))
    ref = str(payload.get("serviceRef") or "").strip()
    department_ref = str(payload.get("departmentRef") or "").strip()
    if not ref or not department_ref:
        raise HTTPException(status_code=422, detail="serviceRef and departmentRef are required")
    if not session.exec(select(OnboardingDepartmentV27).where(
        OnboardingDepartmentV27.site_ref == site.site_ref,
        OnboardingDepartmentV27.department_ref == department_ref,
    )).first():
        raise HTTPException(status_code=409, detail="service department is not configured")
    existing = session.exec(select(OnboardingServiceV27).where(
        OnboardingServiceV27.site_ref == site.site_ref,
        OnboardingServiceV27.service_ref == ref,
    )).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = service_dict(existing) if existing else {}
    row = existing or OnboardingServiceV27(
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        service_ref=ref,
        department_ref=department_ref,
        name=str(payload.get("name") or ref),
        updated_by_subject=auth.subject,
    )
    row.department_ref = department_ref
    row.name = str(payload.get("name") or row.name)
    row.service_type = str(payload.get("serviceType") or row.service_type)
    row.clinical_service = bool(payload.get("clinicalService", row.clinical_service))
    row.operational_status = str(payload.get("operationalStatus") or "draft")
    row.hours = dict(payload.get("hours") or row.hours or {})
    row.capabilities = [str(item) for item in payload.get("capabilities", row.capabilities) if item]
    row.minimum_staffing = list(payload.get("minimumStaffing", row.minimum_staffing) or [])
    row.required_equipment_refs = [str(item) for item in payload.get("requiredEquipmentRefs", row.required_equipment_refs) if item]
    row.escalation_role = str(payload.get("escalationRole") or row.escalation_role)
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _mark_site_pending(session, site.site_ref)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="service", entity_ref=ref,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=service_dict(row), reason=str(payload.get("reason") or "Service configuration updated"))
    return row


def save_room(session: Session, auth: AuthContext, payload: dict[str, Any]) -> OnboardingRoomV27:
    require_configuration_admin(auth)
    site = _site_required(session, str(payload.get("siteRef") or ""))
    ref = str(payload.get("roomRef") or "").strip()
    department_ref = str(payload.get("departmentRef") or "").strip()
    if not ref or not department_ref:
        raise HTTPException(status_code=422, detail="roomRef and departmentRef are required")
    existing = session.exec(select(OnboardingRoomV27).where(
        OnboardingRoomV27.site_ref == site.site_ref,
        OnboardingRoomV27.room_ref == ref,
    )).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = room_dict(existing) if existing else {}
    row = existing or OnboardingRoomV27(
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        room_ref=ref,
        department_ref=department_ref,
        name=str(payload.get("name") or ref),
        room_type=str(payload.get("roomType") or "clinical_room"),
        updated_by_subject=auth.subject,
    )
    row.department_ref = department_ref
    row.name = str(payload.get("name") or row.name)
    row.room_type = str(payload.get("roomType") or row.room_type)
    row.service_refs = [str(item) for item in payload.get("serviceRefs", row.service_refs) if item]
    row.infection_control_zone = payload.get("infectionControlZone", row.infection_control_zone)
    row.capacity = max(1, int(payload.get("capacity", row.capacity)))
    row.operational_status = str(payload.get("operationalStatus") or "draft")
    row.attributes = dict(payload.get("attributes") or row.attributes or {})
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _mark_site_pending(session, site.site_ref)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="room", entity_ref=ref,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=room_dict(row), reason=str(payload.get("reason") or "Room configuration updated"))
    return row


def save_equipment(session: Session, auth: AuthContext, payload: dict[str, Any]) -> OnboardingEquipmentV27:
    require_configuration_admin(auth)
    site = _site_required(session, str(payload.get("siteRef") or ""))
    ref = str(payload.get("equipmentRef") or "").strip()
    if not ref:
        raise HTTPException(status_code=422, detail="equipmentRef is required")
    existing = session.exec(select(OnboardingEquipmentV27).where(
        OnboardingEquipmentV27.site_ref == site.site_ref,
        OnboardingEquipmentV27.equipment_ref == ref,
    )).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = equipment_dict(existing) if existing else {}
    due = payload.get("maintenanceDueAt")
    if isinstance(due, str) and due:
        due = date.fromisoformat(due)
    row = existing or OnboardingEquipmentV27(
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        equipment_ref=ref,
        name=str(payload.get("name") or ref),
        equipment_type=str(payload.get("equipmentType") or "equipment"),
        updated_by_subject=auth.subject,
    )
    row.name = str(payload.get("name") or row.name)
    row.equipment_type = str(payload.get("equipmentType") or row.equipment_type)
    row.room_ref = payload.get("roomRef", row.room_ref)
    row.service_refs = [str(item) for item in payload.get("serviceRefs", row.service_refs) if item]
    row.asset_identifier = payload.get("assetIdentifier", row.asset_identifier)
    row.maintenance_status = str(payload.get("maintenanceStatus") or row.maintenance_status)
    row.maintenance_due_at = due if due is not None else row.maintenance_due_at
    row.operational_status = str(payload.get("operationalStatus") or "draft")
    row.attributes = dict(payload.get("attributes") or row.attributes or {})
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _mark_site_pending(session, site.site_ref)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="equipment", entity_ref=ref,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=equipment_dict(row), reason=str(payload.get("reason") or "Equipment configuration updated"))
    return row


def save_policy(session: Session, auth: AuthContext, payload: dict[str, Any]) -> SitePolicyV27:
    require_configuration_admin(auth)
    site = _site_required(session, str(payload.get("siteRef") or ""))
    key = str(payload.get("policyKey") or "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="policyKey is required")
    existing = session.exec(select(SitePolicyV27).where(
        SitePolicyV27.site_ref == site.site_ref,
        SitePolicyV27.policy_key == key,
    )).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = policy_dict(existing) if existing else {}
    effective = payload.get("effectiveFrom")
    review = payload.get("reviewDueAt")
    if isinstance(effective, str) and effective:
        effective = date.fromisoformat(effective)
    if isinstance(review, str) and review:
        review = date.fromisoformat(review)
    requested_status = str(payload.get("status") or "draft")
    evidence_refs = [str(item) for item in payload.get("evidenceRefs", existing.evidence_refs if existing else []) if item]
    if requested_status == "approved" and not evidence_refs:
        raise HTTPException(status_code=409, detail="approved policy requires evidenceRefs")
    row = existing or SitePolicyV27(
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        policy_key=key,
        title=str(payload.get("title") or key.replace("_", " ").title()),
        policy_version=str(payload.get("policyVersion") or "1.0"),
        owner_role=str(payload.get("ownerRole") or "governance_lead"),
        updated_by_subject=auth.subject,
    )
    row.title = str(payload.get("title") or row.title)
    row.policy_version = str(payload.get("policyVersion") or row.policy_version)
    row.status = requested_status
    row.rules = dict(payload.get("rules") or row.rules or {})
    row.owner_role = str(payload.get("ownerRole") or row.owner_role)
    row.owner_subject = payload.get("ownerSubject", row.owner_subject)
    row.effective_from = effective if effective is not None else row.effective_from
    row.review_due_at = review if review is not None else row.review_due_at
    row.evidence_refs = evidence_refs
    row.version = (existing.version + 1) if existing else 1
    row.updated_by_subject = auth.subject
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    _mark_site_pending(session, site.site_ref)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="policy", entity_ref=key,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=policy_dict(row), reason=str(payload.get("reason") or "Site policy updated"))
    return row


def preview_staff_import(session: Session, auth: AuthContext, payload: dict[str, Any]) -> StaffImportBatchV27:
    require_configuration_admin(auth)
    site = _site_required(session, str(payload.get("siteRef") or ""))
    rows = list(payload.get("rows") or [])
    if not rows:
        raise HTTPException(status_code=422, detail="staff import rows are required")
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_count = 0
    for index, raw in enumerate(rows):
        staff_ref = str(raw.get("staffRef") or "").strip()
        missing = [name for name in ("staffRef", "displayName", "departmentRef") if not str(raw.get(name) or "").strip()]
        if missing:
            findings.append({"row": index + 1, "severity": "error", "code": "missing_required_fields", "fields": missing})
            continue
        if staff_ref in seen:
            findings.append({"row": index + 1, "severity": "error", "code": "duplicate_staff_ref", "staffRef": staff_ref})
            continue
        seen.add(staff_ref)
        requested_role = str(raw.get("requestedRole") or "viewer").lower()
        if requested_role not in ALLOWED_ROLES:
            findings.append({"row": index + 1, "severity": "warning", "code": "role_requires_mapping", "requestedRole": requested_role})
        if raw.get("authSubject"):
            findings.append({"row": index + 1, "severity": "warning", "code": "identity_requires_independent_match", "staffRef": staff_ref})
        valid_count += 1
    checksum = canonical_hash(rows)
    existing = session.exec(select(StaffImportBatchV27).where(
        StaffImportBatchV27.site_ref == site.site_ref,
        StaffImportBatchV27.checksum == checksum,
        StaffImportBatchV27.status == "preview",
    )).first()
    if existing:
        return existing
    batch = StaffImportBatchV27(
        batch_ref=new_ref("staff-import"),
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        source_type=str(payload.get("sourceType") or "csv"),
        source_ref=payload.get("sourceRef"),
        checksum=checksum,
        rows=json_safe(rows),
        row_count=len(rows),
        valid_count=valid_count,
        warning_count=sum(1 for item in findings if item["severity"] == "warning"),
        error_count=sum(1 for item in findings if item["severity"] == "error"),
        validation_findings=findings,
        created_by_subject=auth.subject,
    )
    session.add(batch)
    session.flush()
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="staff_import", entity_ref=batch.batch_ref,
                   action="previewed", previous_state={}, new_state={"checksum": checksum, "rowCount": len(rows), "findings": findings},
                   reason=str(payload.get("reason") or "Staff directory import previewed"))
    return batch


def commit_staff_import(session: Session, auth: AuthContext, batch_ref: str, reason: str) -> tuple[StaffImportBatchV27, list[OnboardingStaffV27]]:
    require_configuration_admin(auth)
    batch = session.exec(select(StaffImportBatchV27).where(StaffImportBatchV27.batch_ref == batch_ref)).first()
    if not batch:
        raise HTTPException(status_code=404, detail="staff import batch not found")
    if batch.status == "committed":
        rows = session.exec(select(OnboardingStaffV27).where(OnboardingStaffV27.source_batch_ref == batch_ref)).all()
        return batch, rows
    if batch.error_count:
        raise HTTPException(status_code=409, detail={"code": "staff_import_has_errors", "errorCount": batch.error_count})
    created_or_updated: list[OnboardingStaffV27] = []
    for raw in batch.rows:
        staff_ref = str(raw.get("staffRef") or "").strip()
        requested_role = str(raw.get("requestedRole") or "viewer").lower()
        if requested_role not in ALLOWED_ROLES:
            requested_role = "viewer" if "viewer" in ALLOWED_ROLES else "admin"
        existing = session.exec(select(OnboardingStaffV27).where(
            OnboardingStaffV27.site_ref == batch.site_ref,
            OnboardingStaffV27.staff_ref == staff_ref,
        )).first()
        previous = staff_dict(existing) if existing else {}
        row = existing or OnboardingStaffV27(
            organisation_ref=batch.organisation_ref,
            site_ref=batch.site_ref,
            premises_ref=batch.premises_ref,
            staff_ref=staff_ref,
            display_name=str(raw.get("displayName")),
            department_ref=str(raw.get("departmentRef")),
            updated_by_subject=auth.subject,
        )
        row.display_name = str(raw.get("displayName") or row.display_name)
        row.email = raw.get("email", row.email)
        supplied_subject = raw.get("authSubject")
        if supplied_subject and row.identity_status != "verified":
            row.auth_subject = str(supplied_subject)
            row.identity_status = "pending_match"
        row.employment_status = str(raw.get("employmentStatus") or row.employment_status)
        row.department_ref = str(raw.get("departmentRef") or row.department_ref)
        row.requested_role = requested_role
        row.primary_role_ref = str(raw.get("primaryRoleRef") or row.primary_role_ref)
        row.grade_or_training_level = raw.get("gradeOrTrainingLevel", row.grade_or_training_level)
        row.contracted_hours_weekly = raw.get("contractedHoursWeekly", row.contracted_hours_weekly)
        row.maximum_safe_hours_weekly = raw.get("maximumSafeHoursWeekly", row.maximum_safe_hours_weekly)
        row.supervisor_staff_ref = raw.get("supervisorStaffRef", row.supervisor_staff_ref)
        row.on_call_eligible = bool(raw.get("onCallEligible", row.on_call_eligible))
        row.source_batch_ref = batch.batch_ref
        row.access_status = "not_requested" if row.access_status != "approved" else row.access_status
        row.version = (existing.version + 1) if existing else 1
        row.updated_by_subject = auth.subject
        row.updated_at = utc_now()
        session.add(row)
        session.flush()
        _record_change(session, auth, organisation_ref=batch.organisation_ref, site_ref=batch.site_ref,
                       premises_ref=batch.premises_ref, entity_type="staff", entity_ref=staff_ref,
                       action="updated" if existing else "created", previous_state=previous,
                       new_state=staff_dict(row), reason=reason)
        created_or_updated.append(row)
    batch.status = "committed"
    batch.committed_by_subject = auth.subject
    batch.committed_at = utc_now()
    session.add(batch)
    _mark_site_pending(session, batch.site_ref)
    return batch, created_or_updated


def match_staff_identity(session: Session, auth: AuthContext, site_ref: str, staff_ref: str, auth_subject: str, reason: str) -> OnboardingStaffV27:
    require_configuration_admin(auth)
    staff = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.staff_ref == staff_ref,
    )).first()
    if not staff:
        raise HTTPException(status_code=404, detail="staff onboarding record not found")
    duplicate = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.auth_subject == auth_subject,
        OnboardingStaffV27.staff_ref != staff_ref,
    )).first()
    if duplicate:
        raise HTTPException(status_code=409, detail={"code": "auth_subject_already_matched", "staffRef": duplicate.staff_ref})
    previous = staff_dict(staff)
    staff.auth_subject = auth_subject
    staff.identity_status = "verified"
    staff.version += 1
    staff.updated_by_subject = auth.subject
    staff.updated_at = utc_now()
    session.add(staff)
    session.flush()
    _record_change(session, auth, organisation_ref=staff.organisation_ref, site_ref=site_ref,
                   premises_ref=staff.premises_ref, entity_type="staff_identity", entity_ref=staff_ref,
                   action="verified", previous_state=previous, new_state=staff_dict(staff), reason=reason)
    return staff


def save_credential(session: Session, auth: AuthContext, site_ref: str, staff_ref: str, payload: dict[str, Any]) -> StaffCredentialV27:
    require_configuration_admin(auth)
    staff = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.staff_ref == staff_ref,
    )).first()
    if not staff:
        raise HTTPException(status_code=404, detail="staff onboarding record not found")
    credential_ref = str(payload.get("credentialRef") or new_ref("credential"))
    existing = session.exec(select(StaffCredentialV27).where(StaffCredentialV27.credential_ref == credential_ref)).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = credential_dict(existing) if existing else {}
    valid_from = payload.get("validFrom")
    valid_until = payload.get("validUntil")
    if isinstance(valid_from, str) and valid_from:
        valid_from = date.fromisoformat(valid_from)
    if isinstance(valid_until, str) and valid_until:
        valid_until = date.fromisoformat(valid_until)
    verification_status = str(payload.get("verificationStatus") or "unverified")
    evidence_refs = [str(item) for item in payload.get("evidenceRefs", existing.evidence_refs if existing else []) if item]
    if verification_status == "verified" and not evidence_refs:
        raise HTTPException(status_code=409, detail="verified credential requires evidenceRefs")
    row = existing or StaffCredentialV27(
        credential_ref=credential_ref,
        organisation_ref=staff.organisation_ref,
        site_ref=site_ref,
        premises_ref=staff.premises_ref,
        staff_ref=staff_ref,
        credential_type=str(payload.get("credentialType") or "professional_registration"),
        issuing_body=str(payload.get("issuingBody") or "unknown"),
        credential_number=str(payload.get("credentialNumber") or ""),
    )
    if not str(payload.get("credentialNumber") or row.credential_number).strip():
        raise HTTPException(status_code=422, detail="credentialNumber is required")
    row.credential_type = str(payload.get("credentialType") or row.credential_type)
    row.issuing_body = str(payload.get("issuingBody") or row.issuing_body)
    row.credential_number = str(payload.get("credentialNumber") or row.credential_number)
    row.valid_from = valid_from if valid_from is not None else row.valid_from
    row.valid_until = valid_until if valid_until is not None else row.valid_until
    row.verification_status = verification_status
    row.evidence_refs = evidence_refs
    if verification_status == "verified":
        row.verified_by_subject = auth.subject
        row.verified_by_name = auth.actor_name
        row.verified_at = utc_now()
    row.version = (existing.version + 1) if existing else 1
    session.add(row)
    session.flush()
    _record_change(session, auth, organisation_ref=staff.organisation_ref, site_ref=site_ref,
                   premises_ref=staff.premises_ref, entity_type="staff_credential", entity_ref=credential_ref,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=credential_dict(row), reason=str(payload.get("reason") or "Staff credential recorded"))
    return row


def save_competency(session: Session, auth: AuthContext, site_ref: str, staff_ref: str, payload: dict[str, Any]) -> StaffCompetencyV27:
    require_configuration_admin(auth)
    staff = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.staff_ref == staff_ref,
    )).first()
    if not staff:
        raise HTTPException(status_code=404, detail="staff onboarding record not found")
    record_ref = str(payload.get("competencyRecordRef") or new_ref("competency"))
    existing = session.exec(select(StaffCompetencyV27).where(StaffCompetencyV27.competency_record_ref == record_ref)).first()
    _assert_version(existing, payload.get("expectedVersion"))
    previous = competency_dict(existing) if existing else {}
    valid_from = payload.get("validFrom")
    valid_until = payload.get("validUntil")
    if isinstance(valid_from, str) and valid_from:
        valid_from = date.fromisoformat(valid_from)
    if isinstance(valid_until, str) and valid_until:
        valid_until = date.fromisoformat(valid_until)
    verification_status = str(payload.get("verificationStatus") or "unverified")
    evidence_refs = [str(item) for item in payload.get("evidenceRefs", existing.evidence_refs if existing else []) if item]
    if verification_status == "verified" and not (evidence_refs or payload.get("evidenceSummary")):
        raise HTTPException(status_code=409, detail="verified competency requires evidence")
    row = existing or StaffCompetencyV27(
        competency_record_ref=record_ref,
        organisation_ref=staff.organisation_ref,
        site_ref=site_ref,
        premises_ref=staff.premises_ref,
        staff_ref=staff_ref,
        competency_ref=str(payload.get("competencyRef") or "general_clinical"),
    )
    row.competency_ref = str(payload.get("competencyRef") or row.competency_ref)
    row.scope_ref = str(payload.get("scopeRef") or row.scope_ref)
    row.level = str(payload.get("level") or row.level)
    row.verification_status = verification_status
    row.evidence_summary = payload.get("evidenceSummary", row.evidence_summary)
    row.evidence_refs = evidence_refs
    row.valid_from = valid_from if valid_from is not None else row.valid_from
    row.valid_until = valid_until if valid_until is not None else row.valid_until
    if verification_status == "verified":
        row.verified_by_subject = auth.subject
        row.verified_by_name = auth.actor_name
        row.verified_at = utc_now()
    row.version = (existing.version + 1) if existing else 1
    session.add(row)
    session.flush()
    _record_change(session, auth, organisation_ref=staff.organisation_ref, site_ref=site_ref,
                   premises_ref=staff.premises_ref, entity_type="staff_competency", entity_ref=record_ref,
                   action="updated" if existing else "created", previous_state=previous,
                   new_state=competency_dict(row), reason=str(payload.get("reason") or "Staff competency recorded"))
    return row


def _active_today(valid_until: date | None) -> bool:
    return valid_until is None or valid_until >= datetime.now(timezone.utc).date()


def readiness_summary(session: Session, site_ref: str) -> dict[str, Any]:
    site = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == site_ref)).first()
    if not site:
        return {
            "siteRef": site_ref,
            "configurationReady": False,
            "goLiveReady": False,
            "configurationBlockers": [{"code": "site_not_configured", "message": "Hospital site onboarding has not started."}],
            "accessBlockers": [],
            "warnings": [],
            "counts": {},
        }
    organisation = session.exec(select(OnboardingOrganisationV27).where(
        OnboardingOrganisationV27.organisation_ref == site.organisation_ref
    )).first()
    departments = session.exec(select(OnboardingDepartmentV27).where(OnboardingDepartmentV27.site_ref == site_ref)).all()
    services = session.exec(select(OnboardingServiceV27).where(OnboardingServiceV27.site_ref == site_ref)).all()
    rooms = session.exec(select(OnboardingRoomV27).where(OnboardingRoomV27.site_ref == site_ref)).all()
    equipment = session.exec(select(OnboardingEquipmentV27).where(OnboardingEquipmentV27.site_ref == site_ref)).all()
    staff = session.exec(select(OnboardingStaffV27).where(OnboardingStaffV27.site_ref == site_ref)).all()
    credentials = session.exec(select(StaffCredentialV27).where(StaffCredentialV27.site_ref == site_ref)).all()
    competencies = session.exec(select(StaffCompetencyV27).where(StaffCompetencyV27.site_ref == site_ref)).all()
    policies = session.exec(select(SitePolicyV27).where(SitePolicyV27.site_ref == site_ref)).all()
    imports = session.exec(select(StaffImportBatchV27).where(
        StaffImportBatchV27.site_ref == site_ref,
        StaffImportBatchV27.status == "committed",
    )).all()
    approvals = session.exec(select(StaffAccessApprovalV27).where(
        StaffAccessApprovalV27.site_ref == site_ref,
        StaffAccessApprovalV27.status == "approved",
        StaffAccessApprovalV27.revoked_at == None,  # noqa: E711
    )).all()

    configuration_blockers: list[dict[str, Any]] = []
    access_blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def block(code: str, message: str, **detail: Any) -> None:
        configuration_blockers.append({"code": code, "message": message, **detail})

    def access_block(code: str, message: str, **detail: Any) -> None:
        access_blockers.append({"code": code, "message": message, **detail})

    if not organisation:
        block("organisation_missing", "The legal organisation record is missing.")
    else:
        if not organisation.legal_name or not organisation.registered_address:
            block("legal_identity_incomplete", "Legal name and registered address are required.")
        if not organisation.data_controller_name or not organisation.data_controller_email:
            block("data_controller_missing", "A named data controller and contact email are required.")
        if not organisation.accountable_executive_subject:
            block("accountable_executive_missing", "The organisation requires a named accountable executive.")
    if site.premises_ref == "default-premises":
        block("default_premises_forbidden", "The hospital must have a real premises reference.")
    if not site.address:
        block("site_address_missing", "The hospital site address is required.")
    if not site.accountable_director_subject:
        block("hospital_director_missing", "The site requires a named accountable director.")
    if not site.clinical_governance_subject:
        block("clinical_governance_owner_missing", "The site requires a named clinical-governance owner.")
    if not departments:
        block("departments_missing", "At least one department must be configured.")
    if not services:
        block("services_missing", "At least one hospital service must be configured.")

    department_refs = {row.department_ref for row in departments}
    service_refs = {row.service_ref for row in services}
    room_refs = {row.room_ref for row in rooms}
    equipment_by_ref = {row.equipment_ref: row for row in equipment}
    for service in services:
        if service.department_ref not in department_refs:
            block("service_department_missing", "A service references an unknown department.", serviceRef=service.service_ref)
        if service.clinical_service and not service.minimum_staffing:
            block("minimum_staffing_missing", "Clinical services require explicit minimum staffing.", serviceRef=service.service_ref)
        if service.clinical_service and not any(service.service_ref in (room.service_refs or []) for room in rooms):
            block("service_room_missing", "Clinical services require at least one mapped room.", serviceRef=service.service_ref)
        for equipment_ref in service.required_equipment_refs or []:
            item = equipment_by_ref.get(equipment_ref)
            if not item:
                block("required_equipment_missing", "A service requires equipment that is not configured.", serviceRef=service.service_ref, equipmentRef=equipment_ref)
            elif item.maintenance_status != "verified" or not _active_today(item.maintenance_due_at):
                block("equipment_maintenance_unverified", "Required equipment maintenance must be current and verified.", serviceRef=service.service_ref, equipmentRef=equipment_ref)
    for room in rooms:
        if room.department_ref not in department_refs:
            block("room_department_missing", "A room references an unknown department.", roomRef=room.room_ref)
        unknown_services = sorted(set(room.service_refs or []) - service_refs)
        if unknown_services:
            block("room_service_unknown", "A room references unknown services.", roomRef=room.room_ref, serviceRefs=unknown_services)
    for item in equipment:
        if item.room_ref and item.room_ref not in room_refs:
            block("equipment_room_unknown", "Equipment references an unknown room.", equipmentRef=item.equipment_ref)

    policy_by_key = {row.policy_key: row for row in policies}
    for key in sorted(REQUIRED_POLICY_KEYS):
        policy = policy_by_key.get(key)
        if not policy:
            block("required_policy_missing", "A required hospital policy is missing.", policyKey=key)
        elif policy.status != "approved":
            block("required_policy_not_approved", "A required hospital policy is not approved.", policyKey=key)
        elif policy.review_due_at and policy.review_due_at < datetime.now(timezone.utc).date():
            block("required_policy_overdue", "A required hospital policy review is overdue.", policyKey=key)
    if not imports:
        block("workforce_import_missing", "At least one validated workforce import must be committed.")
    active_staff = [row for row in staff if row.employment_status == "active"]
    if not active_staff:
        block("active_workforce_missing", "At least one active staff record is required.")
    for person in active_staff:
        if person.department_ref not in department_refs:
            block("staff_department_unknown", "A staff record references an unknown department.", staffRef=person.staff_ref)
        if person.maximum_safe_hours_weekly is None:
            warnings.append({"code": "safe_hours_not_set", "message": "Maximum safe weekly hours are not configured.", "staffRef": person.staff_ref})
        if person.identity_status != "verified" or not person.auth_subject:
            access_block("staff_identity_unverified", "Staff identity must be independently matched before access.", staffRef=person.staff_ref)
        if person.requested_role in CLINICAL_ROLES:
            valid_credentials = [row for row in credentials if row.staff_ref == person.staff_ref and row.verification_status == "verified" and _active_today(row.valid_until)]
            valid_competencies = [row for row in competencies if row.staff_ref == person.staff_ref and row.verification_status == "verified" and _active_today(row.valid_until)]
            if not valid_credentials:
                access_block("clinical_credential_missing", "Clinical access requires a current verified professional credential.", staffRef=person.staff_ref)
            if not valid_competencies:
                access_block("clinical_competency_missing", "Clinical access requires at least one current verified competency.", staffRef=person.staff_ref)
    if site.active_release_ref and not approvals:
        access_block("approved_access_missing", "At least one staff access approval is required before operational use.")

    configuration_ready = not configuration_blockers
    go_live_ready = configuration_ready and bool(site.active_release_ref) and not access_blockers and bool(approvals)
    return {
        "siteRef": site_ref,
        "organisationRef": site.organisation_ref,
        "premisesRef": site.premises_ref,
        "configurationReady": configuration_ready,
        "goLiveReady": go_live_ready,
        "activeReleaseRef": site.active_release_ref,
        "configurationBlockers": configuration_blockers,
        "accessBlockers": access_blockers,
        "warnings": warnings,
        "counts": {
            "departments": len(departments),
            "services": len(services),
            "rooms": len(rooms),
            "equipment": len(equipment),
            "staff": len(staff),
            "activeStaff": len(active_staff),
            "credentials": len(credentials),
            "competencies": len(competencies),
            "approvedPolicies": sum(1 for row in policies if row.status == "approved"),
            "committedImports": len(imports),
            "accessApprovals": len(approvals),
        },
    }


def snapshot_for_site(session: Session, site_ref: str) -> dict[str, Any]:
    site = _site_required(session, site_ref)
    organisation = session.exec(select(OnboardingOrganisationV27).where(
        OnboardingOrganisationV27.organisation_ref == site.organisation_ref
    )).one()
    return {
        "organisation": organisation_dict(organisation),
        "site": site_dict(site),
        "departments": [department_dict(row) for row in session.exec(select(OnboardingDepartmentV27).where(OnboardingDepartmentV27.site_ref == site_ref).order_by(OnboardingDepartmentV27.department_ref)).all()],
        "services": [service_dict(row) for row in session.exec(select(OnboardingServiceV27).where(OnboardingServiceV27.site_ref == site_ref).order_by(OnboardingServiceV27.service_ref)).all()],
        "rooms": [room_dict(row) for row in session.exec(select(OnboardingRoomV27).where(OnboardingRoomV27.site_ref == site_ref).order_by(OnboardingRoomV27.room_ref)).all()],
        "equipment": [equipment_dict(row) for row in session.exec(select(OnboardingEquipmentV27).where(OnboardingEquipmentV27.site_ref == site_ref).order_by(OnboardingEquipmentV27.equipment_ref)).all()],
        "staff": [staff_dict(row) for row in session.exec(select(OnboardingStaffV27).where(OnboardingStaffV27.site_ref == site_ref).order_by(OnboardingStaffV27.staff_ref)).all()],
        "credentials": [credential_dict(row) for row in session.exec(select(StaffCredentialV27).where(StaffCredentialV27.site_ref == site_ref).order_by(StaffCredentialV27.credential_ref)).all()],
        "competencies": [competency_dict(row) for row in session.exec(select(StaffCompetencyV27).where(StaffCompetencyV27.site_ref == site_ref).order_by(StaffCompetencyV27.competency_record_ref)).all()],
        "policies": [policy_dict(row) for row in session.exec(select(SitePolicyV27).where(SitePolicyV27.site_ref == site_ref).order_by(SitePolicyV27.policy_key)).all()],
    }


def _upsert_runtime_config(session: Session, *, premises_ref: str, entity_type: str, entity_ref: str, name: str, attributes: dict[str, Any], auth: AuthContext) -> None:
    row = session.exec(select(HospitalConfigurationRecord).where(
        HospitalConfigurationRecord.premises_ref == premises_ref,
        HospitalConfigurationRecord.entity_type == entity_type,
        HospitalConfigurationRecord.entity_ref == entity_ref,
    )).first()
    if not row:
        row = HospitalConfigurationRecord(
            premises_ref=premises_ref,
            entity_type=entity_type,
            entity_ref=entity_ref,
            name=name,
            updated_by_actor_id=auth.actor_id or auth.subject,
            updated_by_actor_name=auth.actor_name,
            updated_by_actor_role=auth.role,
        )
    row.name = name
    row.attributes = json_safe(attributes)
    row.operational_status = "active"
    row.verification_status = "approved_v27"
    row.authoritative_source_ref = attributes.get("releaseRef")
    row.version += 1 if row.id else 0
    row.updated_by_actor_id = auth.actor_id or auth.subject
    row.updated_by_actor_name = auth.actor_name
    row.updated_by_actor_role = auth.role
    row.updated_at = utc_now()
    session.add(row)


def publish_snapshot(session: Session, auth: AuthContext, release: ConfigurationReleaseV27) -> None:
    snapshot = release.snapshot
    organisation = snapshot["organisation"]
    site = snapshot["site"]
    organisation_row = session.exec(select(OrganisationV26).where(
        OrganisationV26.organisation_ref == release.organisation_ref
    )).first()
    if not organisation_row:
        organisation_row = OrganisationV26(organisation_ref=release.organisation_ref, name=organisation["legalName"])
    organisation_row.name = organisation.get("tradingName") or organisation["legalName"]
    organisation_row.status = "active"
    session.add(organisation_row)

    site_row = session.exec(select(SiteV26).where(SiteV26.site_ref == release.site_ref)).first()
    if not site_row:
        site_row = SiteV26(
            site_ref=release.site_ref,
            organisation_ref=release.organisation_ref,
            premises_ref=release.premises_ref,
            name=site["name"],
        )
    site_row.name = site["name"]
    site_row.timezone_name = site.get("timezone") or "Europe/London"
    site_row.status = "active"
    site_row.configuration_state = "approved_v27"
    session.add(site_row)

    runtime_entities: list[tuple[str, str, str, dict[str, Any]]] = [
        ("organisation", release.organisation_ref, organisation["legalName"], organisation),
        ("site", release.site_ref, site["name"], site),
    ]
    for entity_type, collection, ref_key in (
        ("department", snapshot.get("departments", []), "departmentRef"),
        ("service", snapshot.get("services", []), "serviceRef"),
        ("room", snapshot.get("rooms", []), "roomRef"),
        ("equipment", snapshot.get("equipment", []), "equipmentRef"),
        ("policy", snapshot.get("policies", []), "policyKey"),
    ):
        for item in collection:
            runtime_entities.append((entity_type, item[ref_key], item.get("name") or item.get("title") or item[ref_key], item))
    active_keys = {(entity_type, entity_ref) for entity_type, entity_ref, _, _ in runtime_entities}
    for entity_type, entity_ref, name, attributes in runtime_entities:
        enriched = dict(attributes)
        enriched["releaseRef"] = release.release_ref
        enriched["snapshotHash"] = release.snapshot_hash
        _upsert_runtime_config(session, premises_ref=release.premises_ref, entity_type=entity_type,
                               entity_ref=entity_ref, name=name, attributes=enriched, auth=auth)
    for row in session.exec(select(HospitalConfigurationRecord).where(
        HospitalConfigurationRecord.premises_ref == release.premises_ref,
        HospitalConfigurationRecord.entity_type.in_(["organisation", "site", "department", "service", "room", "equipment", "policy"]),
    )).all():
        if (row.entity_type, row.entity_ref) not in active_keys:
            row.operational_status = "retired"
            row.verification_status = "superseded_v27"
            row.updated_at = utc_now()
            session.add(row)

    staff_items = {item["staffRef"]: item for item in snapshot.get("staff", [])}
    for item in staff_items.values():
        row = session.exec(select(WorkforceProfile).where(
            WorkforceProfile.premises_ref == release.premises_ref,
            WorkforceProfile.staff_ref == item["staffRef"],
        )).first()
        if not row:
            row = WorkforceProfile(
                premises_ref=release.premises_ref,
                staff_ref=item["staffRef"],
                display_name=item["displayName"],
                primary_role_ref=item["primaryRoleRef"],
                department_ref=item["departmentRef"],
                updated_by_actor_id=auth.actor_id or auth.subject,
                updated_by_actor_name=auth.actor_name,
            )
        row.display_name = item["displayName"]
        row.employment_status = item["employmentStatus"]
        row.primary_role_ref = item["primaryRoleRef"]
        row.department_ref = item["departmentRef"]
        row.grade_or_training_level = item.get("gradeOrTrainingLevel")
        row.contracted_hours_weekly = item.get("contractedHoursWeekly")
        row.maximum_safe_hours_weekly = item.get("maximumSafeHoursWeekly")
        row.supervisor_staff_ref = item.get("supervisorStaffRef")
        row.on_call_eligible = bool(item.get("onCallEligible"))
        row.source_status = "approved_v27"
        row.version += 1 if row.id else 0
        row.updated_by_actor_id = auth.actor_id or auth.subject
        row.updated_by_actor_name = auth.actor_name
        row.updated_at = utc_now()
        session.add(row)
    for row in session.exec(select(WorkforceProfile).where(WorkforceProfile.premises_ref == release.premises_ref)).all():
        if row.staff_ref not in staff_items:
            row.employment_status = "inactive"
            row.source_status = "superseded_v27"
            row.updated_at = utc_now()
            session.add(row)

    for item in snapshot.get("competencies", []):
        if item.get("verificationStatus") != "verified":
            continue
        row = session.exec(select(WorkforceCompetency).where(
            WorkforceCompetency.premises_ref == release.premises_ref,
            WorkforceCompetency.staff_ref == item["staffRef"],
            WorkforceCompetency.competency_ref == item["competencyRef"],
            WorkforceCompetency.scope_ref == item["scopeRef"],
        )).first()
        if not row:
            row = WorkforceCompetency(
                premises_ref=release.premises_ref,
                staff_ref=item["staffRef"],
                competency_ref=item["competencyRef"],
                scope_ref=item["scopeRef"],
            )
        row.level = item["level"]
        row.status = "verified_v27"
        row.evidence_summary = item.get("evidenceSummary")
        row.valid_from = date.fromisoformat(item["validFrom"]) if item.get("validFrom") else None
        row.valid_until = date.fromisoformat(item["validUntil"]) if item.get("validUntil") else None
        row.verified_by_actor_id = auth.actor_id or auth.subject
        row.verified_by_actor_name = auth.actor_name
        row.verified_at = utc_now()
        row.version += 1 if row.id else 0
        session.add(row)
    session.flush()


def approve_release(session: Session, auth: AuthContext, site_ref: str, reason: str) -> ConfigurationReleaseV27:
    require_configuration_admin(auth)
    readiness = readiness_summary(session, site_ref)
    if not readiness["configurationReady"]:
        raise HTTPException(status_code=409, detail={
            "code": "configuration_release_blocked",
            "blockers": readiness["configurationBlockers"],
        })
    site = _site_required(session, site_ref)
    snapshot = snapshot_for_site(session, site_ref)
    snapshot_hash = canonical_hash(snapshot)
    existing_same = session.exec(select(ConfigurationReleaseV27).where(
        ConfigurationReleaseV27.site_ref == site_ref,
        ConfigurationReleaseV27.snapshot_hash == snapshot_hash,
        ConfigurationReleaseV27.status == "active",
    )).first()
    if existing_same:
        return existing_same
    previous_active = session.exec(select(ConfigurationReleaseV27).where(
        ConfigurationReleaseV27.site_ref == site_ref,
        ConfigurationReleaseV27.status == "active",
    )).first()
    versions = session.exec(select(ConfigurationReleaseV27).where(ConfigurationReleaseV27.site_ref == site_ref)).all()
    release = ConfigurationReleaseV27(
        release_ref=new_ref("config-release"),
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        release_version=max([row.release_version for row in versions] or [0]) + 1,
        status="active",
        snapshot=json_safe(snapshot),
        snapshot_hash=snapshot_hash,
        readiness_summary=json_safe(readiness),
        approved_by_subject=auth.subject,
        approved_by_name=auth.actor_name,
        approved_by_role=auth.role,
        reason=reason,
    )
    if previous_active:
        previous_active.status = "superseded"
        session.add(previous_active)
    session.add(release)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="hospital_configuration_release_approved",
        action="approved hospital configuration release",
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=release_dict(previous_active) if previous_active else {},
        new_state=release_dict(release),
        reason=reason,
        supervisor_required=True,
        supervisor_approval_status="approved",
        compliance_domain="operational_governance",
        risk_level="amber",
        source_module="organisation-onboarding-v27",
        source_record_ref=release.release_ref,
        entity_type="configuration_release",
        entity_id=release.release_ref,
        idempotency_key=f"configuration-release:{release.release_ref}",
    )
    release.evidence_event_ref = event.event_ref
    session.add(release)
    site.active_release_ref = release.release_ref
    site.status = "approved"
    site.updated_at = utc_now()
    session.add(site)
    organisation = session.exec(select(OnboardingOrganisationV27).where(
        OnboardingOrganisationV27.organisation_ref == site.organisation_ref
    )).one()
    organisation.status = "approved"
    organisation.updated_at = utc_now()
    session.add(organisation)
    publish_snapshot(session, auth, release)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="configuration_release", entity_ref=release.release_ref,
                   action="approved", previous_state=release_dict(previous_active) if previous_active else {},
                   new_state=release_dict(release), reason=reason)
    return release


def rollback_release(session: Session, auth: AuthContext, target_release_ref: str, reason: str) -> ConfigurationReleaseV27:
    require_configuration_admin(auth)
    target = session.exec(select(ConfigurationReleaseV27).where(
        ConfigurationReleaseV27.release_ref == target_release_ref
    )).first()
    if not target:
        raise HTTPException(status_code=404, detail="target configuration release not found")
    site = _site_required(session, target.site_ref)
    current = session.exec(select(ConfigurationReleaseV27).where(
        ConfigurationReleaseV27.site_ref == target.site_ref,
        ConfigurationReleaseV27.status == "active",
    )).first()
    versions = session.exec(select(ConfigurationReleaseV27).where(ConfigurationReleaseV27.site_ref == target.site_ref)).all()
    release = ConfigurationReleaseV27(
        release_ref=new_ref("config-release"),
        organisation_ref=target.organisation_ref,
        site_ref=target.site_ref,
        premises_ref=target.premises_ref,
        release_version=max([row.release_version for row in versions] or [0]) + 1,
        status="active",
        snapshot=target.snapshot,
        snapshot_hash=target.snapshot_hash,
        readiness_summary=target.readiness_summary,
        approved_by_subject=auth.subject,
        approved_by_name=auth.actor_name,
        approved_by_role=auth.role,
        reason=reason,
        rollback_of_release_ref=target.release_ref,
    )
    if current:
        current.status = "superseded"
        session.add(current)
    session.add(release)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="hospital_configuration_release_rolled_back",
        action="rolled back hospital configuration to approved release",
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=release_dict(current) if current else {},
        new_state=release_dict(release),
        reason=reason,
        supervisor_required=True,
        supervisor_approval_status="approved",
        compliance_domain="operational_governance",
        risk_level="red",
        source_module="organisation-onboarding-v27",
        source_record_ref=release.release_ref,
        entity_type="configuration_release",
        entity_id=release.release_ref,
        idempotency_key=f"configuration-rollback:{release.release_ref}",
    )
    release.evidence_event_ref = event.event_ref
    session.add(release)
    site.active_release_ref = release.release_ref
    site.status = "approved"
    site.updated_at = utc_now()
    session.add(site)
    publish_snapshot(session, auth, release)
    _record_change(session, auth, organisation_ref=target.organisation_ref, site_ref=target.site_ref,
                   premises_ref=target.premises_ref, entity_type="configuration_release", entity_ref=release.release_ref,
                   action="rolled_back", previous_state=release_dict(current) if current else {},
                   new_state=release_dict(release), reason=reason)
    return release


def approve_staff_access(session: Session, auth: AuthContext, site_ref: str, staff_ref: str, reason: str, evidence_refs: Iterable[str]) -> StaffAccessApprovalV27:
    require_configuration_admin(auth)
    site = _site_required(session, site_ref)
    if not site.active_release_ref:
        raise HTTPException(status_code=409, detail="an approved configuration release is required before staff access")
    staff = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.staff_ref == staff_ref,
    )).first()
    if not staff:
        raise HTTPException(status_code=404, detail="staff onboarding record not found")
    if staff.employment_status != "active" or staff.identity_status != "verified" or not staff.auth_subject:
        raise HTTPException(status_code=409, detail="active employment and verified identity are required")
    role = staff.requested_role
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=409, detail={"code": "role_not_supported", "role": role})
    clinical_authority_status = "not_applicable"
    if role in CLINICAL_ROLES:
        credentials = session.exec(select(StaffCredentialV27).where(
            StaffCredentialV27.site_ref == site_ref,
            StaffCredentialV27.staff_ref == staff_ref,
            StaffCredentialV27.verification_status == "verified",
        )).all()
        competencies = session.exec(select(StaffCompetencyV27).where(
            StaffCompetencyV27.site_ref == site_ref,
            StaffCompetencyV27.staff_ref == staff_ref,
            StaffCompetencyV27.verification_status == "verified",
        )).all()
        if not any(_active_today(row.valid_until) for row in credentials):
            raise HTTPException(status_code=409, detail="current verified professional credential required")
        if not any(_active_today(row.valid_until) for row in competencies):
            raise HTTPException(status_code=409, detail="current verified competency required")
        clinical_authority_status = "verified"
    existing = session.exec(select(StaffAccessApprovalV27).where(
        StaffAccessApprovalV27.site_ref == site_ref,
        StaffAccessApprovalV27.staff_ref == staff_ref,
    )).first()
    if existing and existing.status == "approved" and existing.approved_role == role and existing.auth_subject == staff.auth_subject:
        return existing
    previous = {
        "approval": {
            "approvalRef": existing.approval_ref,
            "role": existing.approved_role,
            "status": existing.status,
        }
    } if existing else {}
    if existing:
        existing.status = "superseded"
        existing.revoked_at = utc_now()
        session.add(existing)
        session.flush()
        session.delete(existing)
        session.flush()
    approval = StaffAccessApprovalV27(
        approval_ref=new_ref("access-approval"),
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        staff_ref=staff.staff_ref,
        auth_subject=staff.auth_subject,
        approved_role=role,
        clinical_authority_status=clinical_authority_status,
        reason=reason,
        evidence_refs=[str(item) for item in evidence_refs if item],
        approved_by_subject=auth.subject,
        approved_by_name=auth.actor_name,
        approved_by_role=auth.role,
    )
    session.add(approval)
    session.flush()
    membership = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == staff.auth_subject,
        SiteMembershipV26.site_ref == site.site_ref,
    )).first()
    if not membership:
        membership = SiteMembershipV26(
            membership_ref=new_ref("membership"),
            subject=staff.auth_subject,
            organisation_ref=site.organisation_ref,
            site_ref=site.site_ref,
            premises_ref=site.premises_ref,
            role=role,
            is_primary=True,
            granted_by_subject=auth.subject,
        )
    membership.role = role
    membership.status = "active"
    membership.revoked_at = None
    membership.granted_by_subject = auth.subject
    session.add(membership)
    staff.access_status = "approved"
    staff.clinical_authority_status = clinical_authority_status
    staff.version += 1
    staff.updated_by_subject = auth.subject
    staff.updated_at = utc_now()
    session.add(staff)
    event, _ = create_evidence_event(
        session,
        event_type="staff_site_access_approved",
        action="approved staff access to configured hospital site",
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state={
            "approvalRef": approval.approval_ref,
            "staffRef": staff.staff_ref,
            "authSubject": staff.auth_subject,
            "siteRef": site.site_ref,
            "role": role,
            "clinicalAuthorityStatus": clinical_authority_status,
        },
        reason=reason,
        supervisor_required=True,
        supervisor_approval_status="approved",
        compliance_domain="access_control",
        risk_level="red" if role in CLINICAL_ROLES else "amber",
        source_module="organisation-onboarding-v27",
        source_record_ref=approval.approval_ref,
        entity_type="site_membership",
        entity_id=membership.membership_ref,
        idempotency_key=f"staff-access:{approval.approval_ref}",
    )
    approval.evidence_event_ref = event.event_ref
    session.add(approval)
    _record_change(session, auth, organisation_ref=site.organisation_ref, site_ref=site.site_ref,
                   premises_ref=site.premises_ref, entity_type="staff_access", entity_ref=staff.staff_ref,
                   action="approved", previous_state=previous,
                   new_state={"approvalRef": approval.approval_ref, "role": role, "authSubject": staff.auth_subject}, reason=reason)
    return approval


def onboarding_bundle(session: Session, site_ref: str) -> dict[str, Any]:
    site = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == site_ref)).first()
    if not site:
        return {"siteRef": site_ref, "site": None, "readiness": readiness_summary(session, site_ref)}
    organisation = session.exec(select(OnboardingOrganisationV27).where(
        OnboardingOrganisationV27.organisation_ref == site.organisation_ref
    )).first()
    releases = session.exec(select(ConfigurationReleaseV27).where(
        ConfigurationReleaseV27.site_ref == site_ref
    ).order_by(ConfigurationReleaseV27.release_version.desc())).all()
    changes = session.exec(select(ConfigurationChangeV27).where(
        ConfigurationChangeV27.site_ref == site_ref
    ).order_by(ConfigurationChangeV27.created_at.desc())).all()
    return {
        "organisation": organisation_dict(organisation) if organisation else None,
        "site": site_dict(site),
        "departments": [department_dict(row) for row in session.exec(select(OnboardingDepartmentV27).where(OnboardingDepartmentV27.site_ref == site_ref).order_by(OnboardingDepartmentV27.department_ref)).all()],
        "services": [service_dict(row) for row in session.exec(select(OnboardingServiceV27).where(OnboardingServiceV27.site_ref == site_ref).order_by(OnboardingServiceV27.service_ref)).all()],
        "rooms": [room_dict(row) for row in session.exec(select(OnboardingRoomV27).where(OnboardingRoomV27.site_ref == site_ref).order_by(OnboardingRoomV27.room_ref)).all()],
        "equipment": [equipment_dict(row) for row in session.exec(select(OnboardingEquipmentV27).where(OnboardingEquipmentV27.site_ref == site_ref).order_by(OnboardingEquipmentV27.equipment_ref)).all()],
        "staff": [staff_dict(row) for row in session.exec(select(OnboardingStaffV27).where(OnboardingStaffV27.site_ref == site_ref).order_by(OnboardingStaffV27.staff_ref)).all()],
        "credentials": [credential_dict(row) for row in session.exec(select(StaffCredentialV27).where(StaffCredentialV27.site_ref == site_ref).order_by(StaffCredentialV27.credential_ref)).all()],
        "competencies": [competency_dict(row) for row in session.exec(select(StaffCompetencyV27).where(StaffCompetencyV27.site_ref == site_ref).order_by(StaffCompetencyV27.competency_record_ref)).all()],
        "policies": [policy_dict(row) for row in session.exec(select(SitePolicyV27).where(SitePolicyV27.site_ref == site_ref).order_by(SitePolicyV27.policy_key)).all()],
        "releases": [release_dict(row) for row in releases],
        "changes": [change_dict(row) for row in changes[:100]],
        "readiness": readiness_summary(session, site_ref),
    }
