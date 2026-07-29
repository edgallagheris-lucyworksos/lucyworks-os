from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import ALLOWED_ROLES, CLINICAL_ROLES, AuthContext
from app.evidence_service import create_evidence_event
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import (
    OnboardingStaffV27,
    StaffAccessApprovalV27,
    StaffCompetencyV27,
    StaffCredentialV27,
    utc_now,
)
from app import organisation_onboarding_v27_service as service

_original_readiness_summary = service.readiness_summary


def _active_today(valid_until) -> bool:
    return valid_until is None or valid_until >= datetime.now(timezone.utc).date()


def hardened_readiness_summary(session: Session, site_ref: str):
    result = _original_readiness_summary(session, site_ref)
    if not result.get("siteRef") or not result.get("counts"):
        return result
    active_staff = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.employment_status == "active",
    )).all()
    active_approvals = session.exec(select(StaffAccessApprovalV27).where(
        StaffAccessApprovalV27.site_ref == site_ref,
        StaffAccessApprovalV27.status == "approved",
        StaffAccessApprovalV27.revoked_at == None,  # noqa: E711
    )).all()
    approval_by_staff = {row.staff_ref: row for row in active_approvals}
    existing = {(str(item.get("code")), str(item.get("staffRef") or "")) for item in result["accessBlockers"]}
    for person in active_staff:
        if person.access_status == "not_required":
            continue
        approval = approval_by_staff.get(person.staff_ref)
        if not approval or person.access_status != "approved":
            key = ("staff_access_not_decided", person.staff_ref)
            if key not in existing:
                result["accessBlockers"].append({
                    "code": "staff_access_not_decided",
                    "message": "Every active imported staff record must be approved for access or explicitly marked as not requiring system access.",
                    "staffRef": person.staff_ref,
                })
        elif approval.auth_subject != person.auth_subject or approval.approved_role != person.requested_role:
            key = ("staff_access_approval_stale", person.staff_ref)
            if key not in existing:
                result["accessBlockers"].append({
                    "code": "staff_access_approval_stale",
                    "message": "The access approval no longer matches the staff identity or requested role.",
                    "staffRef": person.staff_ref,
                })
    result["counts"]["accessNotRequired"] = sum(1 for person in active_staff if person.access_status == "not_required")
    result["goLiveReady"] = bool(
        result.get("configurationReady")
        and result.get("activeReleaseRef")
        and not result["accessBlockers"]
        and active_approvals
    )
    return result


def hardened_approve_staff_access(
    session: Session,
    auth: AuthContext,
    site_ref: str,
    staff_ref: str,
    reason: str,
    evidence_refs: Iterable[str],
) -> StaffAccessApprovalV27:
    service.require_configuration_admin(auth)
    site = service._site_required(session, site_ref)
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
    evidence = [str(item).strip() for item in evidence_refs if str(item).strip()]
    if not evidence:
        raise HTTPException(status_code=409, detail="access approval requires evidenceRefs")

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
    if (
        existing
        and existing.status == "approved"
        and existing.approved_role == role
        and existing.auth_subject == staff.auth_subject
        and existing.clinical_authority_status == clinical_authority_status
        and existing.evidence_refs == evidence
    ):
        return existing

    previous = {
        "approvalRef": existing.approval_ref,
        "authSubject": existing.auth_subject,
        "approvedRole": existing.approved_role,
        "clinicalAuthorityStatus": existing.clinical_authority_status,
        "status": existing.status,
        "reason": existing.reason,
        "evidenceRefs": existing.evidence_refs,
        "approvedAt": existing.approved_at.isoformat(),
        "revokedAt": existing.revoked_at.isoformat() if existing.revoked_at else None,
    } if existing else {}

    approval = existing or StaffAccessApprovalV27(
        approval_ref=service.new_ref("access-approval"),
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        staff_ref=staff.staff_ref,
        auth_subject=staff.auth_subject,
        approved_role=role,
        clinical_authority_status=clinical_authority_status,
        reason=reason,
        evidence_refs=evidence,
        approved_by_subject=auth.subject,
        approved_by_name=auth.actor_name,
        approved_by_role=auth.role,
    )
    if existing:
        approval.approval_ref = service.new_ref("access-approval")
    approval.auth_subject = staff.auth_subject
    approval.approved_role = role
    approval.clinical_authority_status = clinical_authority_status
    approval.status = "approved"
    approval.reason = reason
    approval.evidence_refs = evidence
    approval.approved_by_subject = auth.subject
    approval.approved_by_name = auth.actor_name
    approval.approved_by_role = auth.role
    approval.approved_at = utc_now()
    approval.revoked_at = None
    session.add(approval)
    session.flush()

    membership = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == staff.auth_subject,
        SiteMembershipV26.site_ref == site.site_ref,
    )).first()
    if not membership:
        membership = SiteMembershipV26(
            membership_ref=service.new_ref("membership"),
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
            "evidenceRefs": evidence,
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
    service._record_change(
        session,
        auth,
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        entity_type="staff_access",
        entity_ref=staff.staff_ref,
        action="approved" if not previous else "reapproved",
        previous_state=previous,
        new_state={
            "approvalRef": approval.approval_ref,
            "role": role,
            "authSubject": staff.auth_subject,
            "clinicalAuthorityStatus": clinical_authority_status,
            "evidenceRefs": evidence,
        },
        reason=reason,
    )
    return approval


def set_access_disposition(
    session: Session,
    auth: AuthContext,
    site_ref: str,
    staff_ref: str,
    status: str,
    reason: str,
) -> OnboardingStaffV27:
    service.require_configuration_admin(auth)
    if status not in {"not_required", "requested"}:
        raise HTTPException(status_code=422, detail="status must be not_required or requested")
    staff = session.exec(select(OnboardingStaffV27).where(
        OnboardingStaffV27.site_ref == site_ref,
        OnboardingStaffV27.staff_ref == staff_ref,
    )).first()
    if not staff:
        raise HTTPException(status_code=404, detail="staff onboarding record not found")
    previous = service.staff_dict(staff)
    approval = session.exec(select(StaffAccessApprovalV27).where(
        StaffAccessApprovalV27.site_ref == site_ref,
        StaffAccessApprovalV27.staff_ref == staff_ref,
        StaffAccessApprovalV27.status == "approved",
    )).first()
    membership = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == staff.auth_subject,
        SiteMembershipV26.site_ref == site_ref,
    )).first() if staff.auth_subject else None
    if status == "not_required":
        if approval:
            approval.status = "revoked"
            approval.revoked_at = utc_now()
            session.add(approval)
        if membership:
            membership.status = "revoked"
            membership.revoked_at = utc_now()
            session.add(membership)
        staff.clinical_authority_status = "not_applicable"
    staff.access_status = status
    staff.version += 1
    staff.updated_by_subject = auth.subject
    staff.updated_at = utc_now()
    session.add(staff)
    session.flush()
    service._record_change(
        session,
        auth,
        organisation_ref=staff.organisation_ref,
        site_ref=staff.site_ref,
        premises_ref=staff.premises_ref,
        entity_type="staff_access_disposition",
        entity_ref=staff.staff_ref,
        action=status,
        previous_state=previous,
        new_state=service.staff_dict(staff),
        reason=reason,
    )
    return staff


service.readiness_summary = hardened_readiness_summary
service.approve_staff_access = hardened_approve_staff_access
