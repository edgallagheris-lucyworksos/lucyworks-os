from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth import AuthContext, require_roles
from app.bvs_v6_service import (
    answer_verification_task,
    claim_dict,
    competency_dict,
    config_dict,
    coverage_assessment,
    create_referral,
    create_replay,
    dashboard,
    referral_dict,
    replay_dict,
    review_claim,
    seed_bvs_draft,
    task_dict,
    transition_referral,
    update_referral_information,
    upsert_competency,
    upsert_configuration,
    upsert_workforce,
    workforce_dict,
)
from app.database import get_session

router = APIRouter(prefix="/api/bvs-v6", tags=["bvs-configuration-workforce-referrals-v6"])

READ_ROLES = ("admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")
CONFIG_ROLES = ("admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "supervisor")
CLINICAL_DECISION_ROLES = ("admin", "clinical_director", "senior_clinician", "supervisor")
REFERRAL_CREATE_ROLES = ("admin", "clinician", "clinical_director", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")


class ConfigurationPayload(BaseModel):
    expectedVersion: int | None = None
    name: str | None = None
    attributes: dict[str, Any] | None = None
    operationalStatus: str | None = None
    verificationStatus: str | None = None
    authoritativeSourceRef: str | None = None
    reason: str | None = None


class ClaimReviewPayload(BaseModel):
    expectedVersion: int
    status: str
    evidenceRef: str | None = None
    notes: str | None = None
    reason: str | None = None


class VerificationAnswerPayload(BaseModel):
    expectedVersion: int
    answer: str
    evidenceRefs: list[str] = Field(default_factory=list)
    status: str = "answered"
    reason: str | None = None


class WorkforcePayload(BaseModel):
    expectedVersion: int | None = None
    displayName: str | None = None
    employmentStatus: str | None = None
    primaryRoleRef: str | None = None
    departmentRef: str | None = None
    gradeOrTrainingLevel: str | None = None
    registrationBody: str | None = None
    registrationNumber: str | None = None
    contractedHoursWeekly: float | None = None
    maximumSafeHoursWeekly: float | None = None
    supervisorStaffRef: str | None = None
    onCallEligible: bool | None = None
    sourceStatus: str | None = None
    reason: str | None = None


class CompetencyPayload(BaseModel):
    expectedVersion: int | None = None
    level: str = "supervised"
    status: str = "provisional"
    evidenceSummary: str | None = None
    validFrom: str | None = None
    validUntil: str | None = None
    reason: str | None = None


class ReferralCreatePayload(BaseModel):
    referralRef: str | None = None
    sourceChannel: str = "portal"
    urgency: str = "routine"
    referringPractice: str
    referringVet: str | None = None
    practiceContact: str | None = None
    patientName: str
    species: str
    ownerName: str
    ownerContact: str | None = None
    requestedServiceRef: str | None = None
    presentingProblem: str
    historySummary: str | None = None
    insuranceStatus: str = "unknown"
    attachmentManifest: list[dict[str, Any]] = Field(default_factory=list)
    requiredInformation: dict[str, bool] | None = None


class ReferralTransitionPayload(BaseModel):
    expectedVersion: int
    status: str
    decision: str | None = None
    decisionReason: str | None = None
    assignedRole: str | None = None
    assignedActorId: str | None = None
    assignedActorName: str | None = None
    requiredInformation: dict[str, bool] | None = None
    reason: str | None = None


class ReferralInformationPayload(BaseModel):
    expectedVersion: int
    historySummary: str | None = None
    attachmentManifest: list[dict[str, Any]] | None = None
    requestedServiceRef: str | None = None
    requiredInformation: dict[str, bool] | None = None
    reason: str | None = None


class ReplayPayload(BaseModel):
    runRef: str | None = None
    sourceDate: str
    dataClassification: str = "anonymised"
    events: list[dict[str, Any]]


def translated(exc: Exception) -> HTTPException:
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/bootstrap")
def bootstrap(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    try:
        counts = seed_bvs_draft(session, auth)
        session.commit()
        return {"created": counts, "dashboard": dashboard(session)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.get("/dashboard")
def get_dashboard(
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    return dashboard(session)


@router.put("/configuration/{entity_type}/{entity_ref}")
def put_configuration(
    entity_type: str,
    entity_ref: str,
    payload: ConfigurationPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    try:
        row = upsert_configuration(session, entity_type, entity_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"configuration": config_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.patch("/claims/{claim_ref}")
def patch_claim(
    claim_ref: str,
    payload: ClaimReviewPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    try:
        row = review_claim(session, claim_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"claim": claim_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.patch("/verification-tasks/{task_ref}")
def patch_verification_task(
    task_ref: str,
    payload: VerificationAnswerPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    try:
        row = answer_verification_task(session, task_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"task": task_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.put("/workforce/{staff_ref}")
def put_workforce(
    staff_ref: str,
    payload: WorkforcePayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if data.get("expectedVersion") is None and (not data.get("displayName") or not data.get("primaryRoleRef") or not data.get("departmentRef")):
        raise HTTPException(status_code=400, detail="new workforce profiles require displayName, primaryRoleRef and departmentRef")
    try:
        row = upsert_workforce(session, staff_ref, data, auth)
        session.commit()
        session.refresh(row)
        return {"workforce": workforce_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.put("/workforce/{staff_ref}/competencies/{competency_ref}/{scope_ref}")
def put_competency(
    staff_ref: str,
    competency_ref: str,
    scope_ref: str,
    payload: CompetencyPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    try:
        row = upsert_competency(session, staff_ref, competency_ref, scope_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"competency": competency_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.get("/coverage-assessment")
def get_coverage_assessment(
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    return coverage_assessment(session)


@router.post("/referrals")
def post_referral(
    payload: ReferralCreatePayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*REFERRAL_CREATE_ROLES)),
) -> dict[str, Any]:
    try:
        row = create_referral(session, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"referral": referral_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.patch("/referrals/{referral_ref}/information")
def patch_referral_information(
    referral_ref: str,
    payload: ReferralInformationPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*REFERRAL_CREATE_ROLES)),
) -> dict[str, Any]:
    try:
        row = update_referral_information(session, referral_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"referral": referral_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.patch("/referrals/{referral_ref}/transition")
def patch_referral_transition(
    referral_ref: str,
    payload: ReferralTransitionPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_DECISION_ROLES)),
) -> dict[str, Any]:
    try:
        row = transition_referral(session, referral_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"referral": referral_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.post("/historical-replays")
def post_historical_replay(
    payload: ReplayPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CONFIG_ROLES)),
) -> dict[str, Any]:
    try:
        row = create_replay(session, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return {"replay": replay_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc
