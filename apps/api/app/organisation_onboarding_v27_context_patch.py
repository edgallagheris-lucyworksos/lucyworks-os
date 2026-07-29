from __future__ import annotations

import os

from fastapi import HTTPException
from sqlmodel import Session, select

from app import operating_context_v26_service as context_service
from app.auth import AuthContext, auth_mode
from app.operational_context_v26_models import SiteMembershipV26, SiteV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27, StaffAccessApprovalV27

_original_memberships_for = context_service.memberships_for


def configuration_required() -> bool:
    configured = os.getenv("V27_CONFIGURATION_REQUIRED", "").strip().lower()
    if configured:
        return configured in {"1", "true", "yes", "on"}
    return auth_mode() != "local"


def governed_memberships_for(session: Session, auth: AuthContext) -> list[SiteMembershipV26]:
    if not configuration_required():
        return _original_memberships_for(session, auth)

    approvals = session.exec(select(StaffAccessApprovalV27).where(
        StaffAccessApprovalV27.auth_subject == auth.subject,
        StaffAccessApprovalV27.status == "approved",
        StaffAccessApprovalV27.revoked_at == None,  # noqa: E711
    )).all()
    if not approvals:
        raise HTTPException(status_code=403, detail={
            "code": "no_approved_hospital_access",
            "message": "Identity has no approved LucyWorks hospital-site access.",
        })

    memberships: list[SiteMembershipV26] = []
    for approval in approvals:
        if approval.approved_role != auth.role:
            raise HTTPException(status_code=403, detail={
                "code": "role_claim_not_approved_for_site",
                "siteRef": approval.site_ref,
                "approvedRole": approval.approved_role,
                "tokenRole": auth.role,
            })
        configured_site = session.exec(select(OnboardingSiteV27).where(
            OnboardingSiteV27.site_ref == approval.site_ref,
            OnboardingSiteV27.active_release_ref != None,  # noqa: E711
            OnboardingSiteV27.status == "approved",
        )).first()
        runtime_site = session.exec(select(SiteV26).where(
            SiteV26.site_ref == approval.site_ref,
            SiteV26.configuration_state == "approved_v27",
            SiteV26.status == "active",
        )).first()
        if not configured_site or not runtime_site:
            raise HTTPException(status_code=409, detail={
                "code": "hospital_configuration_not_approved",
                "siteRef": approval.site_ref,
            })
        membership = session.exec(select(SiteMembershipV26).where(
            SiteMembershipV26.subject == auth.subject,
            SiteMembershipV26.site_ref == approval.site_ref,
        )).first()
        if not membership:
            membership = SiteMembershipV26(
                membership_ref=f"membership-v27-{approval.approval_ref}",
                subject=auth.subject,
                actor_id=auth.actor_id,
                organisation_ref=approval.organisation_ref,
                site_ref=approval.site_ref,
                premises_ref=approval.premises_ref,
                role=approval.approved_role,
                status="active",
                is_primary=not memberships,
                granted_by_subject=approval.approved_by_subject,
            )
        membership.actor_id = auth.actor_id
        membership.organisation_ref = approval.organisation_ref
        membership.premises_ref = approval.premises_ref
        membership.role = approval.approved_role
        membership.status = "active"
        membership.revoked_at = None
        session.add(membership)
        session.flush()
        memberships.append(membership)

    return sorted(memberships, key=lambda row: (not row.is_primary, row.site_ref))


context_service.memberships_for = governed_memberships_for
