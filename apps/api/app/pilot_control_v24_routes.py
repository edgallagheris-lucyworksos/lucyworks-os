from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlmodel import Session

from app.auth import AuthContext, SENIOR_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.pilot_control_v24_service import (
    APPROVAL_ACKNOWLEDGEMENT,
    PILOT_ACKNOWLEDGEMENTS,
    ROLLBACK_ACKNOWLEDGEMENT,
    SUPPORTED_PILOT_MODES,
    UAT_SCENARIOS,
    approval_payload,
    authorise,
    command_state,
    complete_authority,
    create_authority,
    gate_for,
    import_shadow_comparisons,
    list_authorities,
    record_approval,
    require_authority,
    review_shadow_comparison,
    rollback_authority,
    start_authority,
    stop_authority,
    update_authority,
    update_uat,
)
from app.production_readiness_service import add_observation, observation_dict, resolve_observation


legacy_shadow_guard_router = APIRouter(prefix="/api/shadow-mode", tags=["legacy-shadow-mode-guard-v24"])
router = APIRouter(prefix="/api/v24/pilots", tags=["bounded-pilot-control-v24"])

PILOT_CONTROL_ROLES = tuple(sorted(set(SENIOR_ROLES) | {"admin"}))
PILOT_AUTHORISATION_ROLES = (
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "ops_manager",
    "supervisor",
)
ROLLBACK_ROLES = (
    "admin",
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "ops_manager",
    "supervisor",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NamedOwner(StrictModel):
    subject: str = PydanticField(min_length=1, max_length=200)
    name: str = PydanticField(min_length=2, max_length=200)
    role: str = PydanticField(min_length=2, max_length=80)


class PilotCreate(StrictModel):
    requestedMode: str = "synthetic"
    premisesRef: str = PydanticField(default="default-premises", min_length=1, max_length=160)
    serviceLine: str = PydanticField(default="referral", min_length=1, max_length=120)
    scope: dict[str, Any] = PydanticField(default_factory=dict)
    successCriteria: dict[str, Any] = PydanticField(default_factory=dict)
    stopCriteria: dict[str, Any] = PydanticField(default_factory=dict)
    rollbackPlan: dict[str, Any] = PydanticField(default_factory=dict)
    integrationScope: list[str] = PydanticField(default_factory=list)
    automationMode: str = "disabled"
    accountableOwner: NamedOwner | None = None
    clinicalOwner: NamedOwner | None = None
    reason: str = PydanticField(min_length=8, max_length=2000)


class PilotUpdate(StrictModel):
    expectedVersion: int = PydanticField(ge=1)
    requestedMode: str | None = None
    serviceLine: str | None = PydanticField(default=None, min_length=1, max_length=120)
    scope: dict[str, Any] | None = None
    successCriteria: dict[str, Any] | None = None
    stopCriteria: dict[str, Any] | None = None
    rollbackPlan: dict[str, Any] | None = None
    integrationScope: list[str] | None = None
    automationMode: str | None = None
    accountableOwner: NamedOwner | None = None
    clinicalOwner: NamedOwner | None = None
    reason: str = PydanticField(min_length=8, max_length=2000)


class ApprovalRequest(StrictModel):
    approvalType: str
    decision: str
    reason: str = PydanticField(min_length=8, max_length=2000)
    acknowledgement: str | None = PydanticField(default=None, max_length=200)


class AuthoriseRequest(StrictModel):
    expectedVersion: int = PydanticField(ge=1)
    mode: str
    reason: str = PydanticField(min_length=8, max_length=2000)
    acknowledgement: str = PydanticField(min_length=3, max_length=200)


class VersionedReason(StrictModel):
    expectedVersion: int = PydanticField(ge=1)
    reason: str = PydanticField(min_length=8, max_length=2000)


class RollbackRequest(VersionedReason):
    acknowledgement: str = PydanticField(min_length=3, max_length=200)


class StopRequest(StrictModel):
    reason: str = PydanticField(min_length=8, max_length=2000)


class UATUpdate(StrictModel):
    expectedVersion: int = PydanticField(ge=1)
    status: str
    evidenceSummary: str | None = PydanticField(default=None, max_length=4000)
    reason: str = PydanticField(min_length=8, max_length=2000)


class ShadowComparisonRow(StrictModel):
    externalRef: str = PydanticField(min_length=1, max_length=200)
    canonicalEpisodeRef: str = PydanticField(min_length=1, max_length=200)
    sourceSystem: str = PydanticField(default="external_shadow_source", min_length=1, max_length=160)
    externalSnapshot: dict[str, Any] = PydanticField(default_factory=dict)


class ShadowImport(StrictModel):
    rows: list[ShadowComparisonRow] = PydanticField(min_length=1, max_length=1000)
    reason: str = PydanticField(min_length=8, max_length=2000)


class ShadowReview(StrictModel):
    expectedVersion: int = PydanticField(ge=1)
    decision: str
    note: str = PydanticField(min_length=8, max_length=2000)


class ObservationCreate(StrictModel):
    severity: str = "amber"
    category: str = PydanticField(default="workflow", min_length=2, max_length=120)
    summary: str = PydanticField(min_length=8, max_length=2000)
    expectedBehaviour: str | None = PydanticField(default=None, max_length=4000)
    actualBehaviour: str | None = PydanticField(default=None, max_length=4000)
    ownerRole: str = PydanticField(default="ops_manager", min_length=2, max_length=80)


class ObservationResolve(StrictModel):
    resolution: str = PydanticField(min_length=8, max_length=4000)


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    return HTTPException(status_code=400, detail=str(exc))


def _legacy_shadow_block() -> None:
    raise HTTPException(
        status_code=409,
        detail={
            "code": "canonical_pilot_route_required",
            "message": "Legacy caller-attributed shadow writes are retired. Use /api/v24/pilots/{authority_ref}/shadow-comparisons.",
        },
    )


@legacy_shadow_guard_router.post("/import-rows")
def block_legacy_shadow_import(_: AuthContext = Depends(require_authenticated)) -> None:
    _legacy_shadow_block()


@legacy_shadow_guard_router.post("/validate")
def block_legacy_shadow_validate(_: AuthContext = Depends(require_authenticated)) -> None:
    _legacy_shadow_block()


@legacy_shadow_guard_router.post("/approve")
def block_legacy_shadow_approve(_: AuthContext = Depends(require_authenticated)) -> None:
    _legacy_shadow_block()


@legacy_shadow_guard_router.post("/reject")
def block_legacy_shadow_reject(_: AuthContext = Depends(require_authenticated)) -> None:
    _legacy_shadow_block()


@router.get("/contracts")
def pilot_contracts(_: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {
        "supportedModes": sorted(SUPPORTED_PILOT_MODES),
        "approvalAcknowledgement": APPROVAL_ACKNOWLEDGEMENT,
        "authorisationAcknowledgements": PILOT_ACKNOWLEDGEMENTS,
        "rollbackAcknowledgement": ROLLBACK_ACKNOWLEDGEMENT,
        "defaultPlan": {
            "scope": {
                "includedWorkflows": ["referral_intake", "patient_command", "hospital_today", "care_brief"],
                "maxConcurrentPatients": 5,
                "operatingWindow": "08:00-18:00",
                "excludedEffects": ["autonomous_clinical_decision", "automatic_discharge", "automatic_rescheduling"],
            },
            "successCriteria": {
                "measures": {
                    "unresolvedRedObservations": 0,
                    "lostUpdates": 0,
                    "criticalWorkflowAccuracyPercent": 100,
                    "staffAgreementPercent": 95,
                }
            },
            "stopCriteria": {
                "decisionOwner": "Named pilot owner or any authorised safety lead",
                "triggers": [
                    "patient identity mismatch",
                    "unresolved red safety observation",
                    "evidence-chain or data-integrity failure",
                    "critical integration unavailable beyond agreed tolerance",
                    "named clinical owner requests stop",
                ],
            },
            "rollbackPlan": {
                "owner": "",
                "steps": [],
                "recoveryPoint": "",
                "communications": "",
            },
        },
        "uatScenarios": list(UAT_SCENARIOS),
        "authorityBoundary": "LucyWorks may coordinate a bounded validation run. It cannot replace a veterinary professional's clinical decision or evidence.",
    }


@router.get("")
def get_pilots(
    premises_ref: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = list_authorities(session, premises_ref)
    session.commit()
    return {"pilots": rows, "count": len(rows)}


@router.post("")
def post_pilot(
    payload: PilotCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    try:
        row = create_authority(session, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return command_state(session, row)
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.get("/{authority_ref}")
def get_pilot(
    authority_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = require_authority(session, authority_ref)
    result = command_state(session, row)
    session.commit()
    return result


@router.put("/{authority_ref}")
def put_pilot(
    authority_ref: str,
    payload: PilotUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    try:
        row = update_authority(session, authority_ref, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(row)
        return command_state(session, row)
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/validate")
def validate_pilot(
    authority_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = require_authority(session, authority_ref)
    result = gate_for(session, row)
    session.commit()
    return result


@router.post("/{authority_ref}/approvals")
def post_approval(
    authority_ref: str,
    payload: ApprovalRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        approval = record_approval(session, row, payload.model_dump(exclude_none=True), auth)
        session.commit()
        session.refresh(approval)
        return {"approval": approval_payload(approval), "command": command_state(session, row)}
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/authorise")
def post_authorise(
    authority_ref: str,
    payload: AuthoriseRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_AUTHORISATION_ROLES)),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        authorise(session, row, payload.model_dump(), auth)
        session.commit()
        session.refresh(row)
        return command_state(session, row)
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/start")
def post_start(
    authority_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_AUTHORISATION_ROLES)),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        start_authority(session, row, payload.model_dump(), auth)
        session.commit()
        session.refresh(row)
        return command_state(session, row)
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/stop")
def post_stop(
    authority_ref: str,
    payload: StopRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        row, action = stop_authority(session, row, payload.reason, auth)
        session.commit()
        session.refresh(row)
        result = command_state(session, row)
        result["stopActionCreated"] = action is not None
        return result
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/rollback")
def post_rollback(
    authority_ref: str,
    payload: RollbackRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ROLLBACK_ROLES)),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        rollback_authority(session, row, payload.model_dump(), auth)
        session.commit()
        session.refresh(row)
        return command_state(session, row)
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/complete")
def post_complete(
    authority_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_AUTHORISATION_ROLES)),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        complete_authority(session, row, payload.model_dump(), auth)
        session.commit()
        session.refresh(row)
        return command_state(session, row)
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.put("/{authority_ref}/uat/{scenario_ref}")
def put_uat(
    authority_ref: str,
    scenario_ref: str,
    payload: UATUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        scenario = update_uat(session, authority_ref, scenario_ref, payload.model_dump(exclude_none=True), auth)
        row = require_authority(session, authority_ref)
        session.commit()
        session.refresh(scenario)
        return {"scenario": scenario.model_dump(mode="json"), "command": command_state(session, row)}
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/shadow-comparisons")
def post_shadow_comparisons(
    authority_ref: str,
    payload: ShadowImport,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles("admin", "ops_manager", "supervisor", "hospital_director")),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        comparisons = import_shadow_comparisons(session, row, payload.model_dump(), auth)
        session.commit()
        return {"comparisons": [item.model_dump(mode="json") for item in comparisons], "command": command_state(session, row)}
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/shadow-comparisons/{comparison_ref}/review")
def post_shadow_review(
    authority_ref: str,
    comparison_ref: str,
    payload: ShadowReview,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        comparison = review_shadow_comparison(session, row, comparison_ref, payload.model_dump(), auth)
        session.commit()
        session.refresh(comparison)
        return {"comparison": comparison.model_dump(mode="json"), "command": command_state(session, row)}
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.post("/{authority_ref}/observations")
def post_pilot_observation(
    authority_ref: str,
    payload: ObservationCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref, lock=True)
        observation = add_observation(session, row.run_ref, payload.model_dump(exclude_none=True), auth)
        stop_created = False
        if observation.severity == "red":
            _, action = stop_authority(session, row, f"Red pilot observation: {observation.summary}", auth)
            stop_created = action is not None
        session.commit()
        session.refresh(observation)
        return {"observation": observation_dict(observation), "pilotStopped": stop_created, "command": command_state(session, row)}
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc


@router.patch("/{authority_ref}/observations/{observation_ref}/resolve")
def patch_pilot_observation(
    authority_ref: str,
    observation_ref: str,
    payload: ObservationResolve,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    try:
        row = require_authority(session, authority_ref)
        observation = resolve_observation(session, observation_ref, payload.model_dump(), auth)
        if observation.run_ref != row.run_ref:
            raise HTTPException(status_code=409, detail="observation does not belong to this pilot authority")
        session.commit()
        session.refresh(observation)
        return {"observation": observation_dict(observation), "command": command_state(session, row)}
    except Exception as exc:
        session.rollback()
        raise _translate(exc) from exc
