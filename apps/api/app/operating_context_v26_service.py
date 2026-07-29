from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext, auth_mode
from app.evidence_service import create_evidence_event
from app.operational_context_v26_models import (
    ActiveOperatingContextV26,
    ContextSwitchEvidenceV26,
    OrganisationV26,
    SiteMembershipV26,
    SiteV26,
    utc_now,
)

DEFAULT_ORGANISATION_REF = "lucyworks-demo"
DEFAULT_SITE_REF = "bvs-bristol"
DEFAULT_PREMISES_REF = "bvs-bristol"


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


@dataclass(frozen=True)
class OperatingContext:
    context_ref: str
    subject: str
    organisation_ref: str
    site_ref: str
    premises_ref: str
    version: int
    membership_ref: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "contextRef": self.context_ref,
            "subject": self.subject,
            "organisationRef": self.organisation_ref,
            "siteRef": self.site_ref,
            "premisesRef": self.premises_ref,
            "version": self.version,
            "membershipRef": self.membership_ref,
        }


def _claim_values(auth: AuthContext, name: str) -> list[str]:
    value = auth.claims.get(name)
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if item and str(item).strip()]


def _bootstrap_allowed() -> bool:
    configured = os.getenv("V26_CONTEXT_BOOTSTRAP_ENABLED", "").strip().lower()
    return configured in {"1", "true", "yes", "on"} if configured else auth_mode() == "local"


def _ensure_site(
    session: Session,
    organisation_ref: str,
    site_ref: str,
    premises_ref: str,
    *,
    organisation_name: str,
    site_name: str,
    configuration_state: str,
) -> None:
    if premises_ref == "default-premises":
        raise HTTPException(status_code=409, detail={"code": "default_premises_forbidden"})
    if not session.exec(select(OrganisationV26).where(OrganisationV26.organisation_ref == organisation_ref)).first():
        session.add(OrganisationV26(organisation_ref=organisation_ref, name=organisation_name))
    if not session.exec(select(SiteV26).where(SiteV26.site_ref == site_ref)).first():
        session.add(SiteV26(
            site_ref=site_ref,
            organisation_ref=organisation_ref,
            premises_ref=premises_ref,
            name=site_name,
            configuration_state=configuration_state,
        ))
    session.flush()


def _ensure_membership(
    session: Session,
    auth: AuthContext,
    *,
    organisation_ref: str,
    site_ref: str,
    premises_ref: str,
    is_primary: bool,
    granted_by: str,
) -> None:
    existing = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == auth.subject,
        SiteMembershipV26.site_ref == site_ref,
    )).first()
    if existing:
        return
    session.add(SiteMembershipV26(
        membership_ref=new_ref("membership"),
        subject=auth.subject,
        actor_id=auth.actor_id,
        organisation_ref=organisation_ref,
        site_ref=site_ref,
        premises_ref=premises_ref,
        role=auth.role,
        is_primary=is_primary,
        granted_by_subject=granted_by,
    ))
    session.flush()


def provision_memberships(session: Session, auth: AuthContext) -> None:
    organisations = _claim_values(auth, os.getenv("AUTH_ORGANISATION_CLAIM", "organisation_ref"))
    sites = _claim_values(auth, os.getenv("AUTH_SITE_CLAIM", "site_refs"))
    premises = _claim_values(auth, os.getenv("AUTH_PREMISES_CLAIM", "premises_refs"))
    if sites:
        organisation_ref = organisations[0] if organisations else DEFAULT_ORGANISATION_REF
        for index, site_ref in enumerate(sites):
            premises_ref = premises[index] if index < len(premises) else site_ref
            _ensure_site(
                session,
                organisation_ref,
                site_ref,
                premises_ref,
                organisation_name=organisation_ref.replace("-", " ").title(),
                site_name=site_ref.replace("-", " ").title(),
                configuration_state="claim_provisioned",
            )
            _ensure_membership(
                session,
                auth,
                organisation_ref=organisation_ref,
                site_ref=site_ref,
                premises_ref=premises_ref,
                is_primary=index == 0,
                granted_by="oidc-claim",
            )
    if _bootstrap_allowed():
        _ensure_site(
            session,
            DEFAULT_ORGANISATION_REF,
            DEFAULT_SITE_REF,
            DEFAULT_PREMISES_REF,
            organisation_name="LucyWorks Demonstration Organisation",
            site_name="Bristol Referral Hospital",
            configuration_state="synthetic",
        )
        _ensure_membership(
            session,
            auth,
            organisation_ref=DEFAULT_ORGANISATION_REF,
            site_ref=DEFAULT_SITE_REF,
            premises_ref=DEFAULT_PREMISES_REF,
            is_primary=True,
            granted_by=auth.subject,
        )


def memberships_for(session: Session, auth: AuthContext) -> list[SiteMembershipV26]:
    provision_memberships(session, auth)
    rows = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == auth.subject,
        SiteMembershipV26.status == "active",
        SiteMembershipV26.revoked_at == None,  # noqa: E711
    )).all()
    if not rows:
        raise HTTPException(status_code=403, detail={
            "code": "no_authorised_hospital_site",
            "message": "Identity has no active LucyWorks site membership",
        })
    return sorted(rows, key=lambda row: (not row.is_primary, row.site_ref))


def resolve_context(session: Session, auth: AuthContext) -> OperatingContext:
    memberships = memberships_for(session, auth)
    by_site = {row.site_ref: row for row in memberships}
    row = session.exec(select(ActiveOperatingContextV26).where(
        ActiveOperatingContextV26.subject == auth.subject
    )).first()
    if row and row.site_ref not in by_site:
        row = None
    membership = by_site.get(row.site_ref) if row else memberships[0]
    if membership.premises_ref == "default-premises":
        raise HTTPException(status_code=409, detail={"code": "default_premises_forbidden"})
    if not row:
        row = ActiveOperatingContextV26(
            context_ref=new_ref("context"),
            subject=auth.subject,
            organisation_ref=membership.organisation_ref,
            site_ref=membership.site_ref,
            premises_ref=membership.premises_ref,
            selected_by_subject=auth.subject,
        )
        session.add(row)
        session.flush()
    return OperatingContext(
        context_ref=row.context_ref,
        subject=row.subject,
        organisation_ref=row.organisation_ref,
        site_ref=row.site_ref,
        premises_ref=row.premises_ref,
        version=row.version,
        membership_ref=membership.membership_ref,
    )


def assert_payload_context(context: OperatingContext, payload: dict[str, Any]) -> None:
    fields = (
        ("organisationRef", "organisation_ref", context.organisation_ref),
        ("siteRef", "site_ref", context.site_ref),
        ("premisesRef", "premises_ref", context.premises_ref),
    )
    for camel, snake, active in fields:
        supplied = payload.get(camel) or payload.get(snake)
        if supplied is None:
            continue
        if str(supplied) == "default-premises":
            raise HTTPException(status_code=409, detail={"code": "default_premises_forbidden"})
        if str(supplied) != active:
            raise HTTPException(status_code=409, detail={
                "code": "cross_site_write_rejected",
                "field": camel,
                "active": active,
                "supplied": supplied,
            })


def switch_context(
    session: Session,
    auth: AuthContext,
    *,
    site_ref: str,
    expected_version: int,
    reason: str,
) -> tuple[OperatingContext, ContextSwitchEvidenceV26]:
    membership = next((item for item in memberships_for(session, auth) if item.site_ref == site_ref), None)
    if not membership:
        raise HTTPException(status_code=403, detail={"code": "site_not_authorised", "siteRef": site_ref})
    current = resolve_context(session, auth)
    row = session.exec(select(ActiveOperatingContextV26).where(
        ActiveOperatingContextV26.subject == auth.subject
    )).one()
    if row.version != expected_version:
        raise HTTPException(status_code=409, detail={
            "code": "stale_operating_context",
            "expectedVersion": row.version,
            "suppliedVersion": expected_version,
        })
    previous = current.as_dict()
    row.organisation_ref = membership.organisation_ref
    row.site_ref = membership.site_ref
    row.premises_ref = membership.premises_ref
    row.version += 1
    row.selected_by_subject = auth.subject
    row.selected_at = utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    updated = OperatingContext(
        context_ref=row.context_ref,
        subject=row.subject,
        organisation_ref=row.organisation_ref,
        site_ref=row.site_ref,
        premises_ref=row.premises_ref,
        version=row.version,
        membership_ref=membership.membership_ref,
    )
    switch = ContextSwitchEvidenceV26(
        switch_ref=new_ref("context-switch"),
        subject=auth.subject,
        previous_context=previous,
        new_context=updated.as_dict(),
        reason=reason,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(switch)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="operating_context_switched",
        action="authorised hospital site context switched",
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state=updated.as_dict(),
        reason=reason,
        compliance_domain="information_governance",
        risk_level="amber",
        source_module="operational-context-v26",
        source_record_ref=switch.switch_ref,
        entity_type="operating_context",
        entity_id=row.context_ref,
        idempotency_key=f"context-switch:{switch.switch_ref}",
    )
    switch.evidence_event_ref = event.event_ref
    session.add(switch)
    return updated, switch
