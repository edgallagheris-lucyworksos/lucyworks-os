from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app import compliance_safety_routes as base
from app.auth import AuthContext, require_roles
from app.compliance_safety_models import DeploymentProfileV10, SafetyCaseV10, SafetyReviewV10, utc_now
from app.database import get_session
from app.production_readiness_models import ReadinessControl, ReadinessEvidence

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
_original_seed = base.seed


def seed(session: Session, auth: AuthContext) -> tuple[Any, list[Any], DeploymentProfileV10]:
    case, hazards, profile = _original_seed(session, auth)
    baseline_review = session.exec(select(SafetyReviewV10).where(
        SafetyReviewV10.safety_case_ref == case.safety_case_ref,
        SafetyReviewV10.review_type == "developer_safety_baseline",
        SafetyReviewV10.target == "synthetic",
    )).first()
    if not baseline_review:
        baseline_review = SafetyReviewV10(
            review_ref=base.ref("safety-review"),
            safety_case_ref=case.safety_case_ref,
            review_type="developer_safety_baseline",
            target="synthetic",
            outcome="developer_baseline_review",
            findings_json=base.json_text([
                {"code": "scope", "status": "accepted", "detail": "Review covers synthetic and historical engineering validation only."},
                {"code": "clinical-authority", "status": "boundary", "detail": "Qualified professionals retain all clinical judgement."},
                {"code": "deployment", "status": "boundary", "detail": "No live organisation approval, identity mapping or vendor connection is claimed."},
            ]),
            reason="Developer safety baseline and seeded hazard controls reviewed for non-live validation",
            reviewer_subject=auth.subject,
            reviewer_name=auth.actor_name,
            reviewer_role=auth.role,
        )
        session.add(baseline_review)
        if not case.approved_for_target:
            case.status = "approved_for_target"
            case.approved_for_target = "synthetic"
            case.approved_by_subject = auth.subject
            case.approved_by_name = auth.actor_name
            case.approved_at = utc_now()
            case.version += 1
            case.updated_at = utc_now()
            session.add(case)
        base.record_event(
            session,
            auth,
            "developer safety baseline reviewed",
            "safety_case",
            case.safety_case_ref,
            None,
            {"reviewRef": baseline_review.review_ref, "target": "synthetic", "outcome": baseline_review.outcome},
            baseline_review.reason,
            "green",
        )
    session.flush()
    return case, hazards, profile


def control_gate(
    session: Session,
    target: str,
    case: SafetyCaseV10 | None = None,
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


def _approved_review(session: Session, safety_case_ref: str, target: str) -> SafetyReviewV10 | None:
    rows = session.exec(select(SafetyReviewV10).where(
        SafetyReviewV10.safety_case_ref == safety_case_ref,
    ).order_by(SafetyReviewV10.created_at.desc())).all()
    if target in {"synthetic", "historical_replay"}:
        return next((row for row in rows if row.target == "synthetic" and row.outcome in {"developer_baseline_review", "approved", "approved_with_conditions"}), None)
    return next((row for row in rows if row.target == target and row.outcome in {"approved", "approved_with_conditions"}), None)


def release_gate(
    session: Session,
    target: str,
    case: SafetyCaseV10 | None = None,
    profile: DeploymentProfileV10 | None = None,
) -> dict[str, Any]:
    result = control_gate(session, target, case=case, profile=profile)
    case = case or session.exec(select(SafetyCaseV10).order_by(SafetyCaseV10.created_at.desc())).first()
    if case and not _approved_review(session, case.safety_case_ref, target):
        result["blockers"].append({
            "code": "target_safety_review",
            "detail": f"An accountable safety review approving the {target.replace('_', ' ')} target is required after all control evidence passes.",
        })
        result["canRelease"] = False
    return result


base.seed = seed
base.profile_dict = profile_dict
base.release_gate = release_gate


def _approved_evidence(session: Session, evidence_ref: str) -> bool:
    evidence = session.exec(select(ReadinessEvidence).where(ReadinessEvidence.evidence_ref == evidence_ref)).first()
    if not evidence:
        return False
    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == evidence.control_ref)).first()
    return bool(control and control.status == "passed" and control.evidence_ref == evidence_ref)


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

    submitted = {
        "identityEvidenceRef": payload.identityEvidenceRef,
        "dataGovernanceEvidenceRef": payload.dataGovernanceEvidenceRef,
        "vendorEvidenceRef": payload.vendorEvidenceRef,
        "clinicalSafetyOfficerEvidenceRef": payload.clinicalSafetyOfficerEvidenceRef,
        "dpiaEvidenceRef": payload.dpiaEvidenceRef,
        "penetrationTestEvidenceRef": payload.penetrationTestEvidenceRef,
        "staffUatEvidenceRef": payload.staffUatEvidenceRef,
    }
    invalid = {
        field: value.strip()
        for field, value in submitted.items()
        if value and not _approved_evidence(session, value.strip())
    }
    if invalid:
        raise HTTPException(status_code=409, detail={
            "message": "deployment evidence must reference the current evidence record of a passed readiness control",
            "invalidEvidence": invalid,
        })

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


def create_review(
    payload: base.ReviewCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVAL_ROLES)),
) -> dict[str, Any]:
    if payload.target not in base.TARGETS:
        raise HTTPException(status_code=422, detail="invalid target")
    if payload.outcome not in {"approved", "approved_with_conditions", "changes_required", "rejected", "developer_baseline_review"}:
        raise HTTPException(status_code=422, detail="invalid outcome")
    query = select(SafetyCaseV10).where(SafetyCaseV10.safety_case_ref == payload.safetyCaseRef)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    case = session.exec(query).first()
    if not case:
        raise HTTPException(status_code=404, detail="safety case not found")
    gate = control_gate(session, payload.target, case=case)
    if payload.outcome in {"approved", "approved_with_conditions"} and not gate["canRelease"]:
        raise HTTPException(status_code=409, detail={"message": "control evidence gate blocked", "blockers": gate["blockers"]})
    row = SafetyReviewV10(
        review_ref=base.ref("safety-review"),
        safety_case_ref=case.safety_case_ref,
        review_type=payload.reviewType,
        target=payload.target,
        outcome=payload.outcome,
        findings_json=base.json_text(payload.findings),
        reason=payload.reason,
        reviewer_subject=auth.subject,
        reviewer_name=auth.actor_name,
        reviewer_role=auth.role,
    )
    session.add(row)
    if payload.outcome in {"approved", "approved_with_conditions"}:
        case.status = "approved_for_target"
        case.approved_for_target = payload.target
        case.approved_by_subject = auth.subject
        case.approved_by_name = auth.actor_name
        case.approved_at = utc_now()
        case.version += 1
        case.updated_at = utc_now()
        session.add(case)
    base.record_event(
        session,
        auth,
        "safety review recorded",
        "safety_case",
        case.safety_case_ref,
        None,
        {"reviewRef": row.review_ref, "target": payload.target, "outcome": payload.outcome, "controlGate": gate},
        payload.reason,
        "green" if payload.outcome in {"approved", "approved_with_conditions"} else "amber",
    )
    session.commit()
    session.refresh(case)
    final_gate = release_gate(session, payload.target, case=case)
    return {
        "review": {"reviewRef": row.review_ref, "target": row.target, "outcome": row.outcome, "reviewerRole": row.reviewer_role},
        "safetyCase": base.case_dict(case),
        "gate": final_gate,
    }


def patch_route(path: str, method: str, endpoint: Any) -> None:
    for route in base.router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            route.endpoint = endpoint
            route.dependant.call = endpoint


base.create_review = create_review
patch_route("/api/v10/compliance-safety/reviews", "POST", create_review)
