from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app import compliance_safety_routes as base
from app.auth import AuthContext, require_roles
from app.compliance_safety_models import DeploymentProfileV10, utc_now
from app.database import get_session

router = APIRouter(prefix="/api/v10/compliance-safety", tags=["compliance-safety-v10"])
APPROVAL_ROLES = ("clinical_director", "governance_lead", "hospital_director")


class DeploymentEvidenceUpdate(BaseModel):
    expectedVersion: int
    organisationName: str
    identityEvidenceRef: str | None = None
    dataGovernanceEvidenceRef: str | None = None
    vendorEvidenceRef: str | None = None
    clinicalSafetyOfficerEvidenceRef: str | None = None
    dpiaEvidenceRef: str | None = None
    penetrationTestEvidenceRef: str | None = None
    staffUatEvidenceRef: str | None = None
    reason: str


def profile_dict(row: DeploymentProfileV10) -> dict[str, Any]:
    return {
        "profileRef": row.profile_ref,
        "environmentName": row.environment_name,
        "organisationName": row.organisation_name,
        "target": row.target,
        "dataMode": row.data_mode,
        "identityMode": row.identity_mode,
        "vendorMode": row.vendor_mode,
        "realIdentityConfirmed": row.real_identity_confirmed,
        "identityEvidenceRef": row.identity_evidence_ref,
        "realDataGovernanceConfirmed": row.real_data_governance_confirmed,
        "dataGovernanceEvidenceRef": row.data_governance_evidence_ref,
        "realVendorConnectionsConfirmed": row.real_vendor_connections_confirmed,
        "vendorEvidenceRef": row.vendor_evidence_ref,
        "clinicalSafetyOfficerConfirmed": row.clinical_safety_officer_confirmed,
        "clinicalSafetyOfficerEvidenceRef": row.clinical_safety_officer_evidence_ref,
        "dpiaApproved": row.dpi_a_approved,
        "dpiaEvidenceRef": row.dpia_evidence_ref,
        "penetrationTestConfirmed": row.penetration_test_confirmed,
        "penetrationTestEvidenceRef": row.penetration_test_evidence_ref,
        "staffUatConfirmed": row.staff_uat_confirmed,
        "staffUatEvidenceRef": row.staff_uat_evidence_ref,
        "blockers": base.parse_json(row.blockers_json, []),
        "status": row.status,
        "version": row.version,
        "updatedAt": row.updated_at.isoformat(),
    }


_original_release_gate = base.release_gate


def release_gate(
    session: Session,
    target: str,
    case: Any = None,
    profile: DeploymentProfileV10 | None = None,
) -> dict[str, Any]:
    result = _original_release_gate(session, target, case=case, profile=profile)
    profile = profile or session.exec(select(DeploymentProfileV10).order_by(DeploymentProfileV10.created_at.desc())).first()
    if target in {"shadow", "bounded_pilot", "live"} and profile:
        additions: list[dict[str, str]] = []
        if not (profile.organisation_name or "").strip():
            additions.append({"code": "deployment_organisation", "detail": "A named deploying legal organisation is required."})
        confirmations = [
            ("real_identity", profile.real_identity_confirmed, profile.identity_evidence_ref, "verified identity-group mapping"),
            ("data_governance", profile.real_data_governance_confirmed, profile.data_governance_evidence_ref, "data-controller and governance approval"),
            ("vendor_connections", profile.real_vendor_connections_confirmed, profile.vendor_evidence_ref, "tested vendor connection and reconciliation evidence"),
            ("clinical_safety_officer", profile.clinical_safety_officer_confirmed, profile.clinical_safety_officer_evidence_ref, "named safety owner acceptance"),
            ("dpia_approval", profile.dpi_a_approved, profile.dpia_evidence_ref, "approved DPIA"),
        ]
        if target in {"bounded_pilot", "live"}:
            confirmations.extend([
                ("penetration_test", profile.penetration_test_confirmed, profile.penetration_test_evidence_ref, "penetration-test closure evidence"),
                ("staff_uat", profile.staff_uat_confirmed, profile.staff_uat_evidence_ref, "representative staff UAT acceptance"),
            ])
        for code, confirmed, evidence_ref, label in confirmations:
            if confirmed and not (evidence_ref or "").strip():
                additions.append({"code": f"{code}_evidence", "detail": f"Confirmation requires a durable evidence reference for {label}."})
        existing = {item.get("code") for item in result.get("blockers", [])}
        result["blockers"].extend(item for item in additions if item["code"] not in existing)
        result["canRelease"] = not result["blockers"]
    return result


base.profile_dict = profile_dict
base.release_gate = release_gate


@router.patch("/deployment-profile/{profile_ref}/evidence")
def record_deployment_evidence(
    profile_ref: str,
    payload: DeploymentEvidenceUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVAL_ROLES)),
) -> dict[str, Any]:
    query = select(DeploymentProfileV10).where(DeploymentProfileV10.profile_ref == profile_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="deployment profile not found")
    if row.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale deployment profile", "currentVersion": row.version})
    organisation = payload.organisationName.strip()
    if not organisation:
        raise HTTPException(status_code=422, detail="organisationName is required")

    before = profile_dict(row)
    row.organisation_name = organisation
    mappings = [
        ("identity_evidence_ref", "real_identity_confirmed", payload.identityEvidenceRef),
        ("data_governance_evidence_ref", "real_data_governance_confirmed", payload.dataGovernanceEvidenceRef),
        ("vendor_evidence_ref", "real_vendor_connections_confirmed", payload.vendorEvidenceRef),
        ("clinical_safety_officer_evidence_ref", "clinical_safety_officer_confirmed", payload.clinicalSafetyOfficerEvidenceRef),
        ("dpia_evidence_ref", "dpi_a_approved", payload.dpiaEvidenceRef),
        ("penetration_test_evidence_ref", "penetration_test_confirmed", payload.penetrationTestEvidenceRef),
        ("staff_uat_evidence_ref", "staff_uat_confirmed", payload.staffUatEvidenceRef),
    ]
    for evidence_field, confirmation_field, value in mappings:
        normalised = value.strip() if value else None
        setattr(row, evidence_field, normalised)
        setattr(row, confirmation_field, bool(normalised))
    row.version += 1
    row.updated_at = utc_now()
    gate = release_gate(session, row.target, profile=row)
    row.blockers_json = base.json_text(gate["blockers"])
    row.status = "ready" if gate["canRelease"] else "blocked" if row.target not in {"synthetic", "historical_replay"} else "synthetic_ready"
    session.add(row)
    after = profile_dict(row)
    base.record_event(
        session,
        auth,
        "deployment evidence recorded",
        "deployment_profile",
        row.profile_ref,
        before,
        after,
        payload.reason,
        "green" if gate["canRelease"] else "amber",
    )
    session.commit()
    session.refresh(row)
    return {"deploymentProfile": profile_dict(row), "gate": release_gate(session, row.target, profile=row)}
