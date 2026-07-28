from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, SENIOR_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.event_driven_automation_v22_models import AutomationRuntimeConfigV22, AutomationTriggerV22
from app.event_driven_automation_v22_service import (
    SUPPORTED_MODES,
    SUPPORTED_SOURCE_TYPES,
    dispatch_source,
    dry_run_episode,
    evaluate_recorded_operational_delay,
    process_trigger,
    runtime_settings,
    scan_and_dispatch,
    trigger_dict,
    utc_now,
)
from app.operational_automation_v20_routes import AUTOMATION_ROLES, AutomationEvaluate
from app.recorded_state_automation_v21_routes import RecordedAutomationRequest, guarded_generic_evaluation


generic_guard_router = APIRouter(
    prefix="/api/v20/automation",
    tags=["event-driven-automation-guard-v22"],
)
router = APIRouter(prefix="/api/v22/automation", tags=["event-driven-automation-v22"])


class RuntimeConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    enabledTriggerTypes: list[str] = PydanticField(
        default_factory=lambda: ["observation", "critical_result", "evidence_gap", "operational_delay"]
    )
    serviceSubject: str = PydanticField(default="lucyworks:automation-v22", min_length=3, max_length=200)
    serviceName: str = PydanticField(default="LucyWorks governed automation", min_length=3, max_length=200)
    serviceRole: str = PydanticField(default="senior_clinician", min_length=3, max_length=80)
    backgroundScanEnabled: bool = False
    scanIntervalSeconds: int = PydanticField(default=60, ge=30, le=3600)
    expectedVersion: int | None = PydanticField(default=None, ge=1)


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premisesRef: str = PydanticField(min_length=1, max_length=160)
    operationalDate: date | None = None
    episodeRef: str | None = PydanticField(default=None, max_length=160)
    sourceTypes: list[str] = PydanticField(default_factory=lambda: sorted(SUPPORTED_SOURCE_TYPES))


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sourceType: str
    sourceRef: str = PydanticField(min_length=1, max_length=200)


def config_dict(row: AutomationRuntimeConfigV22) -> dict[str, Any]:
    return row.model_dump(mode="json")


@generic_guard_router.post("/evaluate")
def guarded_generic_evaluation_v22(
    payload: AutomationEvaluate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    trigger_type = payload.triggerType.strip().lower()
    if payload.commitActions and trigger_type == "operational_delay":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "recorded_source_required",
                "message": "Committed operational-delay automation must use a v22 recorded-block route.",
                "triggerType": trigger_type,
            },
        )
    return guarded_generic_evaluation(payload, session=session, auth=auth)


@router.post("/operational-blocks/{block_ref}/delay/evaluate")
def evaluate_recorded_delay(
    block_ref: str,
    payload: RecordedAutomationRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    return evaluate_recorded_operational_delay(block_ref, payload, session=session, auth=auth)


@router.get("/config/{premises_ref}")
def get_runtime_config(
    premises_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    return runtime_settings(session, premises_ref)


@router.put("/config/{premises_ref}")
def put_runtime_config(
    premises_ref: str,
    payload: RuntimeConfigUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    mode = payload.mode.strip().lower()
    if mode not in SUPPORTED_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of: {', '.join(sorted(SUPPORTED_MODES))}")
    trigger_types = list(dict.fromkeys(value.strip().lower() for value in payload.enabledTriggerTypes))
    unknown = [value for value in trigger_types if value not in SUPPORTED_SOURCE_TYPES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unsupported trigger types: {', '.join(unknown)}")
    service_role = payload.serviceRole.strip().lower()
    if service_role not in AUTOMATION_ROLES:
        raise HTTPException(status_code=422, detail="serviceRole is not a permitted LucyWorks role")
    if mode == "governed_commit" and {"observation", "critical_result"} & set(trigger_types) and service_role not in CLINICAL_ROLES:
        raise HTTPException(status_code=422, detail="governed clinical automation requires a clinical serviceRole")

    row = session.exec(
        select(AutomationRuntimeConfigV22).where(AutomationRuntimeConfigV22.premises_ref == premises_ref)
    ).first()
    if row:
        if payload.expectedVersion is None:
            raise HTTPException(status_code=428, detail="expectedVersion is required to update automation configuration")
        if row.version != payload.expectedVersion:
            raise HTTPException(
                status_code=409,
                detail={"code": "stale_configuration", "currentVersion": row.version},
            )
        row.version += 1
        row.updated_at = utc_now()
    else:
        row = AutomationRuntimeConfigV22(
            config_ref=f"autoconfig-v22-{uuid4().hex}",
            premises_ref=premises_ref,
        )

    row.mode = mode
    row.enabled_trigger_types = trigger_types
    row.service_subject = payload.serviceSubject.strip()
    row.service_name = payload.serviceName.strip()
    row.service_role = service_role
    row.background_scan_enabled = payload.backgroundScanEnabled
    row.scan_interval_seconds = payload.scanIntervalSeconds
    row.updated_by_subject = auth.subject
    row.updated_by_name = auth.actor_name
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"configuration": config_dict(row)}


@router.post("/dispatch")
def dispatch_recorded_source(
    payload: DispatchRequest,
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    source_type = payload.sourceType.strip().lower()
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(status_code=422, detail="unsupported sourceType")
    row = dispatch_source(source_type, payload.sourceRef.strip(), initiated_by=auth)
    return {"trigger": trigger_dict(row)}


@router.post("/scan")
def scan_recorded_sources(
    payload: ScanRequest,
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    source_types = {value.strip().lower() for value in payload.sourceTypes}
    unknown = source_types - SUPPORTED_SOURCE_TYPES
    if unknown:
        raise HTTPException(status_code=422, detail=f"unsupported source types: {', '.join(sorted(unknown))}")
    rows = scan_and_dispatch(
        premises_ref=payload.premisesRef,
        operational_date=payload.operationalDate,
        episode_ref=payload.episodeRef,
        source_types=source_types,
        initiated_by=auth,
    )
    return {
        "triggers": [trigger_dict(row) for row in rows],
        "count": len(rows),
        "failedCount": sum(1 for row in rows if row.status == "failed"),
        "workItemCount": sum(len(row.work_item_ids) for row in rows),
    }


@router.get("/episodes/{episode_ref}/dry-run")
def episode_dry_run(
    episode_ref: str,
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    return dry_run_episode(episode_ref)


@router.get("/triggers")
def list_triggers(
    premises_ref: str | None = None,
    episode_ref: str | None = None,
    status: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(AutomationTriggerV22).order_by(AutomationTriggerV22.created_at.desc())
    if premises_ref:
        query = query.where(AutomationTriggerV22.premises_ref == premises_ref)
    if episode_ref:
        query = query.where(AutomationTriggerV22.episode_ref == episode_ref)
    if status:
        query = query.where(AutomationTriggerV22.status == status)
    rows = session.exec(query.limit(limit)).all()
    return {
        "triggers": [trigger_dict(row) for row in rows],
        "count": len(rows),
        "failedCount": sum(1 for row in rows if row.status == "failed"),
        "queuedCount": sum(1 for row in rows if row.status in {"queued", "processing"}),
    }


@router.post("/triggers/{trigger_ref}/retry")
def retry_trigger(
    trigger_ref: str,
    _: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    row = process_trigger(trigger_ref, force=True)
    return {"trigger": trigger_dict(row)}
