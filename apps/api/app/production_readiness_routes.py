from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.production_readiness_service import (
    add_observation,
    control_dict,
    create_pilot,
    dashboard,
    evidence_dict,
    observation_dict,
    pilot_dict,
    record_control_evidence,
    resolve_observation,
    security_self_test,
    seed_controls,
    seed_synthetic_hospital,
    update_control,
    update_pilot,
    vendor_mapping_catalogue,
)

router = APIRouter(prefix="/api/production-readiness", tags=["production-readiness-v4"])
SENIOR_ROLES = ("admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "senior_clinician", "supervisor")
APPROVAL_ROLES = ("clinical_director", "governance_lead", "hospital_director", "ops_manager", "supervisor")


class ControlUpdate(BaseModel):
    expectedVersion: int
    status: str
    ownerRole: str | None = None
    evidenceSummary: str | None = None
    reason: str | None = None
    waiverReason: str | None = None
    validDays: int = Field(default=180, ge=1, le=730)


class EvidencePayload(BaseModel):
    evidenceType: str = "manual_attestation"
    summary: str
    sourceRef: str | None = None
    payload: Any = None


class PilotCreate(BaseModel):
    phase: str = "synthetic"
    serviceLine: str = "referral"
    premisesRef: str = "default-premises"
    accountableOwner: str | None = None
    successCriteria: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    startNow: bool = True


class PilotUpdate(BaseModel):
    status: str | None = None
    metrics: dict[str, Any] | None = None
    approvalNote: str | None = None


class ObservationCreate(BaseModel):
    severity: str = "amber"
    category: str = "workflow"
    summary: str
    expectedBehaviour: str | None = None
    actualBehaviour: str | None = None
    ownerRole: str = "ops_manager"


class ObservationResolve(BaseModel):
    resolution: str


class SyntheticSeed(BaseModel):
    premisesRef: str = "synthetic-referral-hospital"
    confirmation: str


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/bootstrap")
def bootstrap(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    rows = seed_controls(session)
    session.commit()
    return {"controls": len(rows), "actor": auth.actor_name}


@router.get("/dashboard")
def get_dashboard(
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    result = dashboard(session)
    session.commit()
    return result


@router.patch("/controls/{control_ref}")
def patch_control(
    control_ref: str,
    payload: ControlUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVAL_ROLES)),
) -> dict[str, Any]:
    try:
        row = update_control(session, control_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"control": control_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translate_error(exc) from exc


@router.post("/controls/{control_ref}/evidence")
def post_evidence(
    control_ref: str,
    payload: EvidencePayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    try:
        row = record_control_evidence(session, control_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"evidence": evidence_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translate_error(exc) from exc


@router.post("/security/self-test")
def post_security_self_test(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles("admin", "governance_lead", "hospital_director", "ops_manager")),
) -> dict[str, Any]:
    seed_controls(session)
    run = security_self_test(session, auth)
    session.commit()
    return {
        "runRef": run.run_ref,
        "status": run.status,
        "score": run.score,
        "passedCount": run.passed_count,
        "failedCount": run.failed_count,
        "warningCount": run.warning_count,
    }


@router.post("/synthetic-hospital/seed")
def post_synthetic_seed(
    payload: SyntheticSeed,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles("admin", "ops_manager")),
) -> dict[str, Any]:
    if payload.confirmation != "CREATE SYNTHETIC DATA":
        raise HTTPException(status_code=400, detail="confirmation must be CREATE SYNTHETIC DATA")
    result = seed_synthetic_hospital(session, payload.premisesRef)
    session.commit()
    return result


@router.get("/vendor-mappings")
def get_vendor_mappings(
    _: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    return vendor_mapping_catalogue()


@router.post("/pilots")
def post_pilot(
    payload: PilotCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVAL_ROLES)),
) -> dict[str, Any]:
    try:
        row = create_pilot(session, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"pilot": pilot_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translate_error(exc) from exc


@router.patch("/pilots/{run_ref}")
def patch_pilot(
    run_ref: str,
    payload: PilotUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVAL_ROLES)),
) -> dict[str, Any]:
    try:
        row = update_pilot(session, run_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"pilot": pilot_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translate_error(exc) from exc


@router.post("/pilots/{run_ref}/observations")
def post_observation(
    run_ref: str,
    payload: ObservationCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    try:
        row = add_observation(session, run_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"observation": observation_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translate_error(exc) from exc


@router.patch("/observations/{observation_ref}/resolve")
def patch_observation(
    observation_ref: str,
    payload: ObservationResolve,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVAL_ROLES)),
) -> dict[str, Any]:
    try:
        row = resolve_observation(session, observation_ref, payload.model_dump(), auth)
        session.commit()
        session.refresh(row)
        return {"observation": observation_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translate_error(exc) from exc
