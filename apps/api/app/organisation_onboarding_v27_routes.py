from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated
from app.database import get_session
from app.organisation_onboarding_v27_models import (
    ConfigurationChangeV27,
    ConfigurationReleaseV27,
    OnboardingSiteV27,
    StaffImportBatchV27,
)
from app.organisation_onboarding_v27_service import (
    approve_release,
    approve_staff_access,
    change_dict,
    commit_staff_import,
    competency_dict,
    credential_dict,
    match_staff_identity,
    onboarding_bundle,
    organisation_dict,
    policy_dict,
    preview_staff_import,
    readiness_summary,
    release_dict,
    require_configuration_admin,
    rollback_release,
    save_competency,
    save_credential,
    save_department,
    save_equipment,
    save_organisation,
    save_policy,
    save_room,
    save_service,
    save_site,
    site_dict,
    staff_dict,
)

router = APIRouter(prefix="/api/v27", tags=["organisation-onboarding-v27"])


class PayloadRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class StaffImportPreviewRequest(BaseModel):
    siteRef: str
    sourceType: str = "csv"
    sourceRef: str | None = None
    rows: list[dict[str, Any]]
    reason: str = Field(default="Staff directory import previewed", min_length=3, max_length=500)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class IdentityMatchRequest(BaseModel):
    authSubject: str = Field(min_length=2, max_length=300)
    reason: str = Field(min_length=3, max_length=1000)


class AccessApprovalRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    evidenceRefs: list[str] = Field(default_factory=list)


@router.get("/contracts")
def onboarding_contracts(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_configuration_admin(auth)
    return {
        "version": "v27",
        "authorityBoundary": {
            "draftDataAffectsOperations": False,
            "importedRoleGrantsAccess": False,
            "clinicalRoleRequiresVerifiedIdentityCredentialAndCompetency": True,
            "siteRequiresApprovedRelease": True,
            "rollbackCreatesNewEvidence": True,
        },
        "phases": [
            "legal organisation",
            "hospital site and premises",
            "departments and services",
            "rooms and equipment",
            "staff import",
            "identity, credentials and competencies",
            "site policies",
            "configuration release",
            "staff access approval",
            "go-live readiness",
        ],
        "requiredPolicyKeys": [
            "fatigue_and_safe_staffing",
            "patient_safety_escalation",
            "service_restriction",
            "safeguarding",
            "data_retention",
            "downtime_and_recovery",
        ],
    }


@router.get("/onboarding/sites")
def list_onboarding_sites(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_configuration_admin(auth)
    rows = session.exec(select(OnboardingSiteV27).order_by(OnboardingSiteV27.name)).all()
    return {"sites": [site_dict(row) for row in rows]}


@router.get("/onboarding")
def get_onboarding_workspace(
    siteRef: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_configuration_admin(auth)
    return onboarding_bundle(session, siteRef)


@router.get("/readiness")
def get_onboarding_readiness(
    siteRef: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_configuration_admin(auth)
    return readiness_summary(session, siteRef)


@router.post("/organisations")
def upsert_organisation(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_organisation(session, auth, request.payload)
    session.commit()
    session.refresh(row)
    return {"organisation": organisation_dict(row)}


@router.post("/sites")
def upsert_site(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_site(session, auth, request.payload)
    session.commit()
    session.refresh(row)
    return {"site": site_dict(row), "readiness": readiness_summary(session, row.site_ref)}


@router.post("/departments")
def upsert_department(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_department(session, auth, request.payload)
    session.commit()
    return {"department": {
        "departmentRef": row.department_ref,
        "name": row.name,
        "status": row.status,
        "version": row.version,
    }}


@router.post("/services")
def upsert_service(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_service(session, auth, request.payload)
    session.commit()
    return {"service": {
        "serviceRef": row.service_ref,
        "departmentRef": row.department_ref,
        "name": row.name,
        "clinicalService": row.clinical_service,
        "minimumStaffing": row.minimum_staffing,
        "version": row.version,
    }}


@router.post("/rooms")
def upsert_room(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_room(session, auth, request.payload)
    session.commit()
    return {"room": {
        "roomRef": row.room_ref,
        "name": row.name,
        "serviceRefs": row.service_refs,
        "operationalStatus": row.operational_status,
        "version": row.version,
    }}


@router.post("/equipment")
def upsert_equipment(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_equipment(session, auth, request.payload)
    session.commit()
    return {"equipment": {
        "equipmentRef": row.equipment_ref,
        "name": row.name,
        "maintenanceStatus": row.maintenance_status,
        "maintenanceDueAt": row.maintenance_due_at.isoformat() if row.maintenance_due_at else None,
        "version": row.version,
    }}


@router.post("/policies")
def upsert_policy(
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_policy(session, auth, request.payload)
    session.commit()
    return {"policy": policy_dict(row)}


@router.post("/staff/imports/preview")
def staff_import_preview(
    request: StaffImportPreviewRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    batch = preview_staff_import(session, auth, request.model_dump())
    session.commit()
    return {"batch": {
        "batchRef": batch.batch_ref,
        "siteRef": batch.site_ref,
        "checksum": batch.checksum,
        "rowCount": batch.row_count,
        "validCount": batch.valid_count,
        "warningCount": batch.warning_count,
        "errorCount": batch.error_count,
        "findings": batch.validation_findings,
        "status": batch.status,
    }}


@router.post("/staff/imports/{batch_ref}/commit")
def staff_import_commit(
    batch_ref: str,
    request: ReasonRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    batch, rows = commit_staff_import(session, auth, batch_ref, request.reason)
    session.commit()
    return {
        "batch": {"batchRef": batch.batch_ref, "status": batch.status, "committedAt": batch.committed_at.isoformat() if batch.committed_at else None},
        "staff": [staff_dict(row) for row in rows],
    }


@router.post("/sites/{site_ref}/staff/{staff_ref}/identity")
def verify_staff_identity(
    site_ref: str,
    staff_ref: str,
    request: IdentityMatchRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = match_staff_identity(session, auth, site_ref, staff_ref, request.authSubject, request.reason)
    session.commit()
    return {"staff": staff_dict(row)}


@router.post("/sites/{site_ref}/staff/{staff_ref}/credentials")
def upsert_staff_credential(
    site_ref: str,
    staff_ref: str,
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_credential(session, auth, site_ref, staff_ref, request.payload)
    session.commit()
    return {"credential": credential_dict(row)}


@router.post("/sites/{site_ref}/staff/{staff_ref}/competencies")
def upsert_staff_competency(
    site_ref: str,
    staff_ref: str,
    request: PayloadRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = save_competency(session, auth, site_ref, staff_ref, request.payload)
    session.commit()
    return {"competency": competency_dict(row)}


@router.post("/sites/{site_ref}/staff/{staff_ref}/approve-access")
def approve_site_access(
    site_ref: str,
    staff_ref: str,
    request: AccessApprovalRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = approve_staff_access(session, auth, site_ref, staff_ref, request.reason, request.evidenceRefs)
    session.commit()
    return {"approval": {
        "approvalRef": row.approval_ref,
        "staffRef": row.staff_ref,
        "authSubject": row.auth_subject,
        "siteRef": row.site_ref,
        "approvedRole": row.approved_role,
        "clinicalAuthorityStatus": row.clinical_authority_status,
        "status": row.status,
        "evidenceEventRef": row.evidence_event_ref,
        "approvedAt": row.approved_at.isoformat(),
    }, "readiness": readiness_summary(session, site_ref)}


@router.post("/sites/{site_ref}/releases/approve")
def approve_configuration_release(
    site_ref: str,
    request: ReasonRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = approve_release(session, auth, site_ref, request.reason)
    session.commit()
    session.refresh(row)
    return {"release": release_dict(row), "readiness": readiness_summary(session, site_ref)}


@router.post("/releases/{release_ref}/rollback")
def rollback_configuration_release(
    release_ref: str,
    request: ReasonRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = rollback_release(session, auth, release_ref, request.reason)
    session.commit()
    session.refresh(row)
    return {"release": release_dict(row), "readiness": readiness_summary(session, row.site_ref)}


@router.get("/releases")
def list_configuration_releases(
    siteRef: str = Query(..., min_length=1),
    includeSnapshot: bool = False,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_configuration_admin(auth)
    rows = session.exec(select(ConfigurationReleaseV27).where(
        ConfigurationReleaseV27.site_ref == siteRef
    ).order_by(ConfigurationReleaseV27.release_version.desc())).all()
    return {"releases": [release_dict(row, include_snapshot=includeSnapshot) for row in rows]}


@router.get("/changes")
def list_configuration_changes(
    siteRef: str = Query(..., min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_configuration_admin(auth)
    rows = session.exec(select(ConfigurationChangeV27).where(
        ConfigurationChangeV27.site_ref == siteRef
    ).order_by(ConfigurationChangeV27.created_at.desc()).limit(limit)).all()
    return {"changes": [change_dict(row) for row in rows]}


@router.get("/staff/imports")
def list_staff_imports(
    siteRef: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_configuration_admin(auth)
    rows = session.exec(select(StaffImportBatchV27).where(
        StaffImportBatchV27.site_ref == siteRef
    ).order_by(StaffImportBatchV27.created_at.desc())).all()
    return {"imports": [{
        "batchRef": row.batch_ref,
        "checksum": row.checksum,
        "rowCount": row.row_count,
        "validCount": row.valid_count,
        "warningCount": row.warning_count,
        "errorCount": row.error_count,
        "status": row.status,
        "createdAt": row.created_at.isoformat(),
        "committedAt": row.committed_at.isoformat() if row.committed_at else None,
    } for row in rows]}
