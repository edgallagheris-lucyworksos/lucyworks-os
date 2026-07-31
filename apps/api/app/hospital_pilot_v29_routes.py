from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlalchemy import text
from sqlmodel import Session, select

from app.auth import ALL_AUTHENTICATED_ROLES, AuthContext, require_roles
from app.database import get_session
from app.evidence_service import create_evidence_event, verify_event_chain
from app.hospital_pilot_v29_models import (
    ExportArtifactV29,
    HospitalPilotV29,
    IntegrationSimulatorV29,
    PilotApprovalV29,
    PilotIncidentV29,
    PilotMeasurementV29,
    ReadinessAssessmentV29,
    SimulatorRunV29,
    SimulatorScenarioV29,
    SpeechAdapterV29,
    VeterinaryTerminologyPackV29,
    utc_now,
)
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.pilot_control_v24_models import PilotAuthorityV24
from app.real_hospital_connection_v28_models import (
    IntegrationConnectorV28,
    IntegrationEventV28,
    ReconciliationItemV28,
    SpeechProviderV28,
)
from app.real_hospital_connection_v28_routes import (
    CONNECTOR_TYPES,
    configured_site,
    require_site_access,
)

router = APIRouter(prefix="/api/v29/pilot-lab", tags=["hospital-pilot-integration-simulator-v29"])
OPS_ROLES = ("admin", "ops_manager", "hospital_director", "governance_lead")
CLINICAL_ROLES = ("admin", "clinical_director", "senior_clinician")
PILOT_CONTROL_ROLES = tuple(sorted(set(OPS_ROLES + CLINICAL_ROLES + ("supervisor",))))
ADAPTER_TYPES = {"browser", "cloud", "private"}
PROCESSING_LOCATIONS = {"device", "cloud", "hospital"}
FAULT_TYPES = {"delay", "outage", "duplicate", "conflict", "missing_fields", "incorrect_identifier", "out_of_order", "none"}
PILOT_MODES = {"synthetic", "shadow"}
APPROVAL_TYPES = {"operations", "clinical"}

DEFAULT_TERMINOLOGY: dict[str, list[str]] = {
    "species": ["canine", "feline", "equine", "rabbit", "avian", "reptile"],
    "anatomy": ["stifle", "tarsus", "carpus", "thoracolumbar", "lumbosacral", "brachial plexus", "tympanic bulla"],
    "procedures": ["hemilaminectomy", "ventral slot", "TPLO", "arthroscopy", "MRI", "CT", "echocardiography"],
    "diagnostics": ["intervertebral disc extrusion", "cranial cruciate ligament disease", "pyometra", "haemangiosarcoma", "azotaemia"],
    "medicines": ["meloxicam", "metacam", "gabapentin", "prednisolone", "methadone", "propofol", "alfaxalone", "amoxicillin clavulanate"],
    "units": ["milligram per kilogram", "microgram per kilogram", "millilitres", "international units", "every twelve hours"],
    "record_phrases": ["owner reports", "on examination", "differential diagnosis", "informed consent", "discharge instructions"],
}
DEFAULT_CORRECTIONS: list[dict[str, Any]] = [
    {"heard": "meta cam", "proposed": "Metacam", "category": "medicine"},
    {"heard": "meloxicom", "proposed": "meloxicam", "category": "medicine"},
    {"heard": "gabba pentin", "proposed": "gabapentin", "category": "medicine"},
    {"heard": "hemi laminectomy", "proposed": "hemilaminectomy", "category": "procedure"},
    {"heard": "ventral slots", "proposed": "ventral slot", "category": "procedure"},
    {"heard": "tee pee el oh", "proposed": "TPLO", "category": "procedure"},
    {"heard": "inter vertebral disk extrusion", "proposed": "intervertebral disc extrusion", "category": "diagnostic"},
]
DEFAULT_ABBREVIATIONS = {
    "BID": "twice daily",
    "TID": "three times daily",
    "SID": "once daily",
    "PRN": "when required",
    "IV": "intravenous",
    "IM": "intramuscular",
    "SC": "subcutaneous",
    "MRI": "magnetic resonance imaging",
    "CT": "computed tomography",
    "TPLO": "tibial plateau levelling osteotomy",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpeechAdapterCreate(StrictModel):
    organisationRef: str
    siteRef: str
    providerRef: str
    name: str
    adapterType: str = "browser"
    processingLocation: str = "device"
    protocol: str = "browser_recognition"
    reconnectEnabled: bool = True
    maxReconnectAttempts: int = PydanticField(default=5, ge=0, le=20)
    reconnectBackoffMs: int = PydanticField(default=1000, ge=100, le=30000)
    fallbackProviderRef: str | None = None
    minimumConfidence: float = PydanticField(default=0.78, ge=0, le=1)
    maximumLatencyMs: int = PydanticField(default=2000, ge=100, le=30000)
    networkRequirements: dict[str, Any] = PydanticField(default_factory=dict)
    configuration: dict[str, Any] = PydanticField(default_factory=dict)


class AdapterTest(StrictModel):
    expectedVersion: int
    deviceDiagnostics: dict[str, Any] = PydanticField(default_factory=dict)
    measuredLatencyMs: int | None = PydanticField(default=None, ge=0, le=120000)
    reason: str = PydanticField(min_length=5, max_length=2000)


class TerminologyPackCreate(StrictModel):
    organisationRef: str
    siteRef: str
    name: str = "UK referral veterinary terminology"
    releaseLabel: str = "v1"
    language: str = "en-GB"
    categories: dict[str, list[str]] = PydanticField(default_factory=dict)
    correctionRules: list[dict[str, Any]] = PydanticField(default_factory=list)
    abbreviations: dict[str, str] = PydanticField(default_factory=dict)
    siteTerms: list[str] = PydanticField(default_factory=list)
    evidenceRefs: list[str] = PydanticField(default_factory=list)


class VersionedReason(StrictModel):
    expectedVersion: int
    reason: str = PydanticField(min_length=5, max_length=2000)


class TerminologyNormalise(StrictModel):
    siteRef: str
    text: str = PydanticField(min_length=1, max_length=20000)


class SimulatorCreate(StrictModel):
    organisationRef: str
    siteRef: str
    connectorType: str
    name: str
    seed: int = 29
    defaultLatencyMs: int = PydanticField(default=50, ge=0, le=120000)
    configuration: dict[str, Any] = PydanticField(default_factory=dict)


class ScenarioCreate(StrictModel):
    scenarioCode: str
    title: str
    faultType: str
    eventType: str = "synthetic_update"
    eventCount: int = PydanticField(default=1, ge=1, le=20)
    parameters: dict[str, Any] = PydanticField(default_factory=dict)
    expectedDetection: str
    critical: bool = True


class ScenarioRun(StrictModel):
    pilotRef: str | None = None
    reason: str = PydanticField(min_length=5, max_length=2000)


class ReadinessRequest(StrictModel):
    siteRef: str
    pilotRef: str | None = None
    deviceDiagnostics: dict[str, Any] = PydanticField(default_factory=dict)
    backupVerified: bool = False
    restoreVerified: bool = False


class PilotCreate(StrictModel):
    organisationRef: str
    siteRef: str
    name: str
    department: str = "referral"
    serviceLine: str = "referral"
    mode: str = "synthetic"
    caseLimit: int = PydanticField(default=25, ge=1, le=1000)
    startAt: datetime | None = None
    endAt: datetime | None = None
    allowedDeviceRefs: list[str] = PydanticField(default_factory=list)
    allowedProviderRefs: list[str] = PydanticField(default_factory=list)
    allowedSimulatorRefs: list[str] = PydanticField(default_factory=list)
    successCriteria: dict[str, Any] = PydanticField(default_factory=dict)
    stopCriteria: dict[str, Any] = PydanticField(default_factory=dict)
    rollbackPlan: dict[str, Any] = PydanticField(default_factory=dict)
    clinicalOwnerSubject: str | None = None
    clinicalOwnerName: str | None = None


class PilotApproval(StrictModel):
    expectedVersion: int
    approvalType: str
    reason: str = PydanticField(min_length=5, max_length=2000)


class PilotActivate(StrictModel):
    expectedVersion: int
    readinessAssessmentRef: str
    restrictionsAcknowledged: bool = False
    reason: str = PydanticField(min_length=5, max_length=2000)


class PilotCaseStart(StrictModel):
    expectedVersion: int
    episodeRef: str
    patientRef: str
    urgentAccess: bool = False


class IncidentCreate(StrictModel):
    severity: str
    category: str
    patientRef: str | None = None
    episodeRef: str | None = None
    synthetic: bool = True
    description: str = PydanticField(min_length=5, max_length=5000)
    immediateAction: str = PydanticField(min_length=3, max_length=5000)


class MeasurementCreate(StrictModel):
    episodeRef: str | None = None
    synthetic: bool = True
    metricType: str
    value: float
    unit: str
    baselineValue: float | None = None
    metadata: dict[str, Any] = PydanticField(default_factory=dict)


class ExportRequest(StrictModel):
    siteRef: str
    pilotRef: str | None = None


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def require_version(row: Any, expected: int) -> None:
    if row.version != expected:
        raise HTTPException(status_code=409, detail={"code": "stale_version", "currentVersion": row.version})


def record_v29(
    session: Session,
    auth: AuthContext,
    *,
    action: str,
    entity_type: str,
    entity_ref: str,
    new_state: Any,
    reason: str,
    previous_state: Any = None,
    patient_ref: str | None = None,
    episode_ref: str | None = None,
    risk: str = "amber",
) -> str:
    event, _ = create_evidence_event(
        session,
        event_type=f"v29_{action}",
        action=action,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        patient_case_id=patient_ref,
        referral_episode_id=episode_ref,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        justification="Governed hospital pilot, simulator, readiness and veterinary speech validation",
        evidence_links=[{"type": entity_type, "id": entity_ref}],
        compliance_domain="clinical_governance" if patient_ref or episode_ref else "information_governance",
        risk_level=risk,
        source_module="hospital-pilot-integration-simulator-v29",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or entity_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v29:{entity_type}:{entity_ref}:{action}:{digest(new_state)[:20]}",
    )
    return event.event_ref


def get_pilot(session: Session, pilot_ref: str) -> HospitalPilotV29:
    pilot = session.exec(select(HospitalPilotV29).where(HospitalPilotV29.pilot_ref == pilot_ref)).first()
    if not pilot:
        raise HTTPException(status_code=404, detail="pilot not found")
    return pilot


def stop_pilot(session: Session, auth: AuthContext, pilot: HospitalPilotV29, reason: str) -> None:
    if pilot.status not in {"stopped", "completed"}:
        previous = row_dict(pilot)
        pilot.status = "stopped"
        pilot.stopped_reason = reason
        pilot.stopped_at = utc_now()
        pilot.version += 1
        pilot.updated_by_subject = auth.subject
        pilot.updated_at = utc_now()
        session.add(pilot)
        record_v29(
            session,
            auth,
            action="pilot_auto_stopped",
            entity_type="hospital_pilot",
            entity_ref=pilot.pilot_ref,
            previous_state=previous,
            new_state=row_dict(pilot),
            reason=reason,
            risk="red",
        )
        authority = session.exec(select(PilotAuthorityV24).where(PilotAuthorityV24.authority_ref == pilot.authority_ref)).first()
        if authority:
            authority.status = "stopped"
            authority.stopped_at = utc_now()
            authority.version += 1
            authority.updated_at = utc_now()
            session.add(authority)


def pilot_stop_reasons(session: Session, pilot: HospitalPilotV29) -> list[str]:
    criteria = pilot.stop_criteria or {}
    reasons: list[str] = []
    red_incidents = session.exec(select(PilotIncidentV29).where(
        PilotIncidentV29.pilot_ref == pilot.pilot_ref,
        PilotIncidentV29.severity == "red",
        PilotIncidentV29.status == "open",
    )).all()
    max_red = int(criteria.get("maxRedIncidents", 0))
    if len(red_incidents) > max_red:
        reasons.append(f"red incident threshold exceeded ({len(red_incidents)} > {max_red})")

    accuracy_rows = session.exec(select(PilotMeasurementV29).where(
        PilotMeasurementV29.pilot_ref == pilot.pilot_ref,
        PilotMeasurementV29.metric_type == "transcription_accuracy",
    )).all()
    min_samples = int(criteria.get("minimumAccuracySamples", 5))
    minimum_accuracy = float(criteria.get("minimumAccuracy", 0.75))
    if len(accuracy_rows) >= min_samples:
        average = sum(row.value for row in accuracy_rows) / len(accuracy_rows)
        if average < minimum_accuracy:
            reasons.append(f"transcription accuracy below threshold ({average:.3f} < {minimum_accuracy:.3f})")

    simulator_refs = pilot.allowed_simulator_refs or []
    connectors = session.exec(select(IntegrationSimulatorV29).where(
        IntegrationSimulatorV29.simulator_ref.in_(simulator_refs)
    )).all() if simulator_refs else []
    connector_refs = [row.connector_ref for row in connectors]
    open_reconciliation = session.exec(select(ReconciliationItemV28).where(
        ReconciliationItemV28.connector_ref.in_(connector_refs),
        ReconciliationItemV28.status == "open",
    )).all() if connector_refs else []
    max_open = int(criteria.get("maxOpenReconciliation", 3))
    if len(open_reconciliation) > max_open:
        reasons.append(f"open reconciliation threshold exceeded ({len(open_reconciliation)} > {max_open})")
    return reasons


def evaluate_and_stop(session: Session, auth: AuthContext, pilot: HospitalPilotV29) -> list[str]:
    reasons = pilot_stop_reasons(session, pilot)
    if reasons and pilot.auto_stop_enabled:
        stop_pilot(session, auth, pilot, "; ".join(reasons))
    return reasons


@router.get("/control-centre")
def control_centre(
    siteRef: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    require_site_access(session, auth, siteRef)
    adapters = session.exec(select(SpeechAdapterV29).where(SpeechAdapterV29.site_ref == siteRef)).all()
    packs = session.exec(select(VeterinaryTerminologyPackV29).where(VeterinaryTerminologyPackV29.site_ref == siteRef)).all()
    simulators = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.site_ref == siteRef)).all()
    simulator_refs = [row.simulator_ref for row in simulators]
    scenarios = session.exec(select(SimulatorScenarioV29).where(SimulatorScenarioV29.simulator_ref.in_(simulator_refs))).all() if simulator_refs else []
    runs = session.exec(select(SimulatorRunV29).where(SimulatorRunV29.simulator_ref.in_(simulator_refs)).order_by(SimulatorRunV29.started_at.desc())).all() if simulator_refs else []
    pilots = session.exec(select(HospitalPilotV29).where(HospitalPilotV29.site_ref == siteRef).order_by(HospitalPilotV29.created_at.desc())).all()
    pilot_refs = [row.pilot_ref for row in pilots]
    incidents = session.exec(select(PilotIncidentV29).where(
        PilotIncidentV29.pilot_ref.in_(pilot_refs),
        PilotIncidentV29.status == "open",
    )).all() if pilot_refs else []
    assessments = session.exec(select(ReadinessAssessmentV29).where(
        ReadinessAssessmentV29.site_ref == siteRef
    ).order_by(ReadinessAssessmentV29.assessed_at.desc())).all()
    artifacts = session.exec(select(ExportArtifactV29).where(
        ExportArtifactV29.site_ref == siteRef
    ).order_by(ExportArtifactV29.generated_at.desc())).all()
    return {
        "siteRef": siteRef,
        "speechAdapters": [row_dict(row) for row in adapters],
        "terminologyPacks": [row_dict(row) for row in packs],
        "simulators": [row_dict(row) for row in simulators],
        "scenarios": [row_dict(row) for row in scenarios],
        "recentRuns": [row_dict(row) for row in runs[:20]],
        "pilots": [row_dict(row) for row in pilots],
        "openIncidents": [row_dict(row) for row in incidents],
        "readinessAssessments": [row_dict(row) for row in assessments[:10]],
        "artifacts": [row_dict(row) for row in artifacts[:10]],
        "summary": {
            "testedAdapters": len([row for row in adapters if row.last_test_status == "passed"]),
            "approvedTerminologyPacks": len([row for row in packs if row.status == "approved"]),
            "testedSimulators": len([row for row in simulators if row.last_test_status == "passed"]),
            "activePilots": len([row for row in pilots if row.status == "active"]),
            "stoppedPilots": len([row for row in pilots if row.status == "stopped"]),
            "openIncidents": len(incidents),
            "latestReadiness": assessments[0].overall_status if assessments else "NOT_ASSESSED",
        },
        "boundary": "Synthetic data remains visibly synthetic and reconciled. V29 performs no vendor write-back, clinical signing, prescribing or dose authorisation.",
    }


@router.post("/speech/adapters")
def create_speech_adapter(
    payload: SpeechAdapterCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    if payload.adapterType not in ADAPTER_TYPES:
        raise HTTPException(status_code=422, detail="unsupported adapter type")
    if payload.processingLocation not in PROCESSING_LOCATIONS:
        raise HTTPException(status_code=422, detail="unsupported processing location")
    require_site_access(session, auth, payload.siteRef)
    configured_site(session, payload.siteRef)
    provider = session.exec(select(SpeechProviderV28).where(
        SpeechProviderV28.provider_ref == payload.providerRef,
        SpeechProviderV28.site_ref == payload.siteRef,
    )).first()
    if not provider:
        raise HTTPException(status_code=404, detail="speech provider not found")
    if provider.raw_audio_retention:
        raise HTTPException(status_code=409, detail={"code": "raw_audio_retention_forbidden"})
    if payload.fallbackProviderRef:
        fallback = session.exec(select(SpeechProviderV28).where(
            SpeechProviderV28.provider_ref == payload.fallbackProviderRef,
            SpeechProviderV28.site_ref == payload.siteRef,
        )).first()
        if not fallback or fallback.raw_audio_retention:
            raise HTTPException(status_code=409, detail="safe fallback provider required")
    adapter = SpeechAdapterV29(
        adapter_ref=new_ref("speech-adapter-v29"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        provider_ref=payload.providerRef,
        name=payload.name,
        adapter_type=payload.adapterType,
        processing_location=payload.processingLocation,
        protocol=payload.protocol,
        reconnect_enabled=payload.reconnectEnabled,
        max_reconnect_attempts=payload.maxReconnectAttempts,
        reconnect_backoff_ms=payload.reconnectBackoffMs,
        fallback_provider_ref=payload.fallbackProviderRef,
        minimum_confidence=payload.minimumConfidence,
        maximum_latency_ms=payload.maximumLatencyMs,
        network_requirements=payload.networkRequirements,
        configuration=payload.configuration,
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(adapter)
    session.flush()
    record_v29(session, auth, action="speech_adapter_created", entity_type="speech_adapter", entity_ref=adapter.adapter_ref, new_state=row_dict(adapter), reason="Create provider-neutral streaming adapter without raw-audio retention")
    session.commit()
    session.refresh(adapter)
    return {"adapter": row_dict(adapter)}


@router.post("/speech/adapters/{adapter_ref}/test")
def test_speech_adapter(
    adapter_ref: str,
    payload: AdapterTest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    adapter = session.exec(select(SpeechAdapterV29).where(SpeechAdapterV29.adapter_ref == adapter_ref)).first()
    if not adapter:
        raise HTTPException(status_code=404, detail="speech adapter not found")
    require_site_access(session, auth, adapter.site_ref)
    require_version(adapter, payload.expectedVersion)
    provider = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.provider_ref == adapter.provider_ref)).first()
    checks = {
        "providerApproved": bool(provider and provider.status == "approved"),
        "providerTestPassed": bool(provider and provider.last_test_status == "passed"),
        "rawAudioRetentionDisabled": bool(provider and not provider.raw_audio_retention),
        "microphoneGranted": payload.deviceDiagnostics.get("microphonePermission") == "granted",
        "secureContext": bool(payload.deviceDiagnostics.get("secureContext", True)),
        "networkOnline": bool(payload.deviceDiagnostics.get("online", True)),
        "browserRecognition": bool(payload.deviceDiagnostics.get("speechRecognition", adapter.adapter_type != "browser")),
        "latencyWithinLimit": payload.measuredLatencyMs is None or payload.measuredLatencyMs <= adapter.maximum_latency_ms,
        "reconnectConfigured": (not adapter.reconnect_enabled) or adapter.max_reconnect_attempts > 0,
        "processingLocationDeclared": adapter.processing_location in PROCESSING_LOCATIONS,
    }
    required = ["providerApproved", "providerTestPassed", "rawAudioRetentionDisabled", "microphoneGranted", "secureContext", "latencyWithinLimit", "reconnectConfigured", "processingLocationDeclared"]
    if adapter.adapter_type == "browser":
        required.append("browserRecognition")
    if adapter.processing_location != "device":
        required.append("networkOnline")
    passed = all(checks[key] for key in required)
    previous = row_dict(adapter)
    adapter.last_test_status = "passed" if passed else "failed"
    adapter.last_test_detail = "All required streaming, device, privacy and reconnect checks passed." if passed else f"Failed checks: {[key for key in required if not checks[key]]}"
    adapter.last_test_results = {"checks": checks, "diagnostics": payload.deviceDiagnostics, "measuredLatencyMs": payload.measuredLatencyMs}
    adapter.last_test_at = utc_now()
    adapter.status = "tested" if passed else "draft"
    adapter.version += 1
    adapter.updated_by_subject = auth.subject
    adapter.updated_at = utc_now()
    session.add(adapter)
    record_v29(session, auth, action="speech_adapter_tested", entity_type="speech_adapter", entity_ref=adapter.adapter_ref, previous_state=previous, new_state=row_dict(adapter), reason=payload.reason, risk="green" if passed else "red")
    session.commit()
    session.refresh(adapter)
    return {"adapter": row_dict(adapter), "checks": checks}


@router.post("/terminology-packs")
def create_terminology_pack(
    payload: TerminologyPackCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    require_site_access(session, auth, payload.siteRef)
    configured_site(session, payload.siteRef)
    categories = payload.categories or DEFAULT_TERMINOLOGY
    corrections = payload.correctionRules or DEFAULT_CORRECTIONS
    abbreviations = payload.abbreviations or DEFAULT_ABBREVIATIONS
    pack = VeterinaryTerminologyPackV29(
        pack_ref=new_ref("vet-terms-v29"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        name=payload.name,
        release_label=payload.releaseLabel,
        language=payload.language,
        categories=categories,
        correction_rules=corrections,
        abbreviations=abbreviations,
        site_terms=payload.siteTerms,
        evidence_refs=payload.evidenceRefs,
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(pack)
    session.flush()
    record_v29(session, auth, action="terminology_pack_created", entity_type="terminology_pack", entity_ref=pack.pack_ref, new_state={"pack": row_dict(pack), "termCount": sum(len(values) for values in categories.values())}, reason="Create governed veterinary terminology and correction release")
    session.commit()
    session.refresh(pack)
    return {"pack": row_dict(pack)}


@router.post("/terminology-packs/{pack_ref}/approve")
def approve_terminology_pack(
    pack_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES)),
) -> dict[str, Any]:
    pack = session.exec(select(VeterinaryTerminologyPackV29).where(VeterinaryTerminologyPackV29.pack_ref == pack_ref)).first()
    if not pack:
        raise HTTPException(status_code=404, detail="terminology pack not found")
    require_site_access(session, auth, pack.site_ref)
    require_version(pack, payload.expectedVersion)
    if pack.created_by_subject == auth.subject:
        raise HTTPException(status_code=409, detail={"code": "independent_terminology_approval_required"})
    previous = row_dict(pack)
    pack.status = "approved"
    pack.approved_by_subject = auth.subject
    pack.approved_by_name = auth.actor_name
    pack.approved_at = utc_now()
    pack.updated_by_subject = auth.subject
    pack.updated_at = utc_now()
    pack.version += 1
    session.add(pack)
    evidence_ref = record_v29(session, auth, action="terminology_pack_approved", entity_type="terminology_pack", entity_ref=pack.pack_ref, previous_state=previous, new_state=row_dict(pack), reason=payload.reason, risk="green")
    pack.evidence_refs = list(dict.fromkeys([*pack.evidence_refs, evidence_ref]))
    session.add(pack)
    session.commit()
    session.refresh(pack)
    return {"pack": row_dict(pack)}


@router.post("/terminology/normalise")
def normalise_terminology(
    payload: TerminologyNormalise,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    require_site_access(session, auth, payload.siteRef)
    pack = session.exec(select(VeterinaryTerminologyPackV29).where(
        VeterinaryTerminologyPackV29.site_ref == payload.siteRef,
        VeterinaryTerminologyPackV29.status == "approved",
    ).order_by(VeterinaryTerminologyPackV29.approved_at.desc())).first()
    if not pack:
        raise HTTPException(status_code=409, detail={"code": "approved_terminology_pack_required"})
    proposed = payload.text
    substitutions: list[dict[str, Any]] = []
    for rule in pack.correction_rules:
        heard = str(rule.get("heard", "")).strip()
        replacement = str(rule.get("proposed", "")).strip()
        if not heard or not replacement:
            continue
        pattern = re.compile(rf"\b{re.escape(heard)}\b", re.IGNORECASE)
        if pattern.search(proposed):
            proposed = pattern.sub(replacement, proposed)
            substitutions.append({"heard": heard, "proposed": replacement, "category": rule.get("category", "general")})
    medicine_terms = {term.lower() for term in pack.categories.get("medicines", [])}
    medicine_mentions = sorted(term for term in medicine_terms if re.search(rf"\b{re.escape(term)}\b", proposed, re.IGNORECASE))
    return {
        "packRef": pack.pack_ref,
        "originalText": payload.text,
        "proposedText": proposed,
        "substitutions": substitutions,
        "medicineMentions": medicine_mentions,
        "requiresHumanReview": True,
        "warning": "Corrections are suggestions only. Medicine, dose, route and frequency wording must be checked and explicitly confirmed by an authorised clinician.",
    }


@router.post("/simulators")
def create_simulator(
    payload: SimulatorCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    if payload.connectorType not in CONNECTOR_TYPES:
        raise HTTPException(status_code=422, detail="unsupported connector type")
    require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    connector = IntegrationConnectorV28(
        connector_ref=new_ref("synthetic-connector-v29"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        premises_ref=site.premises_ref,
        connector_type=payload.connectorType,
        vendor_name=f"LucyWorks synthetic {payload.connectorType}",
        environment="simulator",
        mode="shadow",
        status="active",
        stale_after_seconds=900,
        configuration={"syntheticOnly": True, "writeBack": False, **payload.configuration},
        last_test_status="passed",
        last_test_detail="Synthetic in-process connector; no external endpoint or vendor write capability.",
        last_test_at=utc_now(),
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(connector)
    session.flush()
    simulator = IntegrationSimulatorV29(
        simulator_ref=new_ref("simulator-v29"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        premises_ref=site.premises_ref,
        connector_ref=connector.connector_ref,
        connector_type=payload.connectorType,
        name=payload.name,
        seed=payload.seed,
        default_latency_ms=payload.defaultLatencyMs,
        configuration=payload.configuration,
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(simulator)
    session.flush()
    record_v29(session, auth, action="integration_simulator_created", entity_type="integration_simulator", entity_ref=simulator.simulator_ref, new_state={"simulator": row_dict(simulator), "connector": row_dict(connector)}, reason="Create visibly synthetic no-write hospital-system simulator")
    session.commit()
    session.refresh(simulator)
    return {"simulator": row_dict(simulator), "connector": row_dict(connector)}


@router.post("/simulators/{simulator_ref}/test")
def test_simulator(
    simulator_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    simulator = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.simulator_ref == simulator_ref)).first()
    if not simulator:
        raise HTTPException(status_code=404, detail="simulator not found")
    require_site_access(session, auth, simulator.site_ref)
    require_version(simulator, payload.expectedVersion)
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == simulator.connector_ref)).first()
    checks = {
        "syntheticBanner": simulator.synthetic_banner.startswith("SYNTHETIC TEST DATA"),
        "connectorEnvironment": bool(connector and connector.environment == "simulator"),
        "shadowOnly": bool(connector and connector.mode == "shadow"),
        "externalEndpointAbsent": bool(connector and not connector.endpoint_host),
        "writeBackDisabled": bool(connector and not connector.configuration.get("writeBack", False)),
    }
    passed = all(checks.values())
    previous = row_dict(simulator)
    simulator.last_test_status = "passed" if passed else "failed"
    simulator.last_test_detail = "Synthetic isolation, banner and no-write controls passed." if passed else f"Failed checks: {[key for key, value in checks.items() if not value]}"
    simulator.last_test_at = utc_now()
    simulator.status = "tested" if passed else "draft"
    simulator.version += 1
    simulator.updated_by_subject = auth.subject
    simulator.updated_at = utc_now()
    session.add(simulator)
    record_v29(session, auth, action="integration_simulator_tested", entity_type="integration_simulator", entity_ref=simulator.simulator_ref, previous_state=previous, new_state=row_dict(simulator), reason=payload.reason, risk="green" if passed else "red")
    session.commit()
    session.refresh(simulator)
    return {"simulator": row_dict(simulator), "checks": checks}


@router.post("/simulators/{simulator_ref}/scenarios")
def create_scenario(
    simulator_ref: str,
    payload: ScenarioCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    if payload.faultType not in FAULT_TYPES:
        raise HTTPException(status_code=422, detail="unsupported fault type")
    simulator = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.simulator_ref == simulator_ref)).first()
    if not simulator:
        raise HTTPException(status_code=404, detail="simulator not found")
    require_site_access(session, auth, simulator.site_ref)
    scenario = SimulatorScenarioV29(
        scenario_ref=new_ref("scenario-v29"),
        simulator_ref=simulator_ref,
        scenario_code=payload.scenarioCode,
        title=payload.title,
        fault_type=payload.faultType,
        event_type=payload.eventType,
        event_count=payload.eventCount,
        parameters=payload.parameters,
        expected_detection=payload.expectedDetection,
        critical=payload.critical,
        created_by_subject=auth.subject,
    )
    session.add(scenario)
    session.flush()
    record_v29(session, auth, action="simulator_scenario_created", entity_type="simulator_scenario", entity_ref=scenario.scenario_ref, new_state=row_dict(scenario), reason="Define deterministic synthetic hospital-system failure scenario")
    session.commit()
    session.refresh(scenario)
    return {"scenario": row_dict(scenario)}


@router.post("/scenarios/{scenario_ref}/run")
def run_scenario(
    scenario_ref: str,
    payload: ScenarioRun,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    scenario = session.exec(select(SimulatorScenarioV29).where(SimulatorScenarioV29.scenario_ref == scenario_ref)).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario not found")
    simulator = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.simulator_ref == scenario.simulator_ref)).first()
    if not simulator:
        raise HTTPException(status_code=404, detail="simulator not found")
    require_site_access(session, auth, simulator.site_ref)
    if simulator.last_test_status != "passed":
        raise HTTPException(status_code=409, detail={"code": "tested_simulator_required"})
    pilot = get_pilot(session, payload.pilotRef) if payload.pilotRef else None
    if pilot and simulator.simulator_ref not in pilot.allowed_simulator_refs:
        raise HTTPException(status_code=409, detail={"code": "simulator_not_in_pilot_scope"})
    run = SimulatorRunV29(
        run_ref=new_ref("sim-run-v29"),
        scenario_ref=scenario.scenario_ref,
        simulator_ref=simulator.simulator_ref,
        pilot_ref=payload.pilotRef,
        started_by_subject=auth.subject,
        started_by_name=auth.actor_name,
    )
    session.add(run)
    session.flush()
    injected: list[str] = []
    affected: list[str] = []
    reconciliation_refs: list[str] = []
    duplicate_detected = 0
    detection_status = "passed"
    now = utc_now()

    if scenario.fault_type == "outage":
        result = {"fault": "outage", "detectedAs": "connector_unavailable", "eventsInjected": 0, "silentSubstitution": False}
    else:
        for index in range(scenario.event_count):
            synthetic_ref = f"SYNTHETIC-{simulator.seed}-{scenario.scenario_code}-{index + 1}"
            affected.append(synthetic_ref)
            external_event_id = f"{run.run_ref}:{index + 1}"
            occurred_at = now
            payload_summary: dict[str, Any] = {
                "synthetic": True,
                "banner": simulator.synthetic_banner,
                "syntheticRef": synthetic_ref,
                "scenarioCode": scenario.scenario_code,
                "faultType": scenario.fault_type,
                "sequence": index + 1,
                "total": scenario.event_count,
            }
            if scenario.fault_type == "delay":
                delay_seconds = int(scenario.parameters.get("delaySeconds", 3600))
                occurred_at = now - timedelta(seconds=delay_seconds)
                payload_summary["delaySeconds"] = delay_seconds
            elif scenario.fault_type == "missing_fields":
                payload_summary["missingFields"] = scenario.parameters.get("missingFields", ["patientId", "episodeId"])
            elif scenario.fault_type == "incorrect_identifier":
                payload_summary["externalPatientId"] = "SYNTHETIC-UNKNOWN-PATIENT"
            elif scenario.fault_type == "conflict":
                payload_summary["conflict"] = {"field": scenario.parameters.get("field", "appointmentTime"), "external": "10:30", "canonical": "11:00"}
            elif scenario.fault_type == "out_of_order":
                payload_summary["sequence"] = scenario.event_count - index
            event = IntegrationEventV28(
                event_ref=new_ref("synthetic-event-v29"),
                connector_ref=simulator.connector_ref,
                external_event_id=external_event_id,
                event_type=scenario.event_type,
                direction="simulated_inbound",
                status="reconciliation_required",
                patient_ref=None,
                episode_ref=None,
                payload_hash=digest(payload_summary),
                payload_summary=payload_summary,
                occurred_at=occurred_at,
                received_at=now,
                failure_code=f"synthetic_{scenario.fault_type}" if scenario.fault_type != "none" else "synthetic_isolation",
                failure_detail="Synthetic event is isolated from canonical patient records and requires reconciliation.",
            )
            session.add(event)
            session.flush()
            injected.append(event.event_ref)
            item = ReconciliationItemV28(
                item_ref=new_ref("synthetic-reconcile-v29"),
                connector_ref=simulator.connector_ref,
                event_ref=event.event_ref,
                entity_type="synthetic_test_entity",
                external_ref=synthetic_ref,
                candidate_refs=[],
                status="open",
                severity="red" if scenario.critical else "amber",
                reason=f"Synthetic {scenario.fault_type} scenario must never attach automatically to a patient or episode.",
                assigned_role="ops_manager",
            )
            session.add(item)
            session.flush()
            reconciliation_refs.append(item.item_ref)
            if scenario.fault_type == "duplicate":
                duplicate_detected += 1
        result = {
            "fault": scenario.fault_type,
            "eventsInjected": len(injected),
            "reconciliationCreated": len(reconciliation_refs),
            "duplicatesDetected": duplicate_detected,
            "silentSubstitution": False,
            "canonicalAttachmentCount": 0,
        }
    run.status = "completed"
    run.detection_status = detection_status
    run.injected_event_refs = injected
    run.affected_synthetic_refs = affected
    run.result = result
    run.completed_at = utc_now()
    session.add(run)
    run.evidence_ref = record_v29(session, auth, action="simulator_scenario_run", entity_type="simulator_run", entity_ref=run.run_ref, new_state=row_dict(run), reason=payload.reason, risk="red" if scenario.critical else "amber")
    session.add(run)
    if pilot:
        evaluate_and_stop(session, auth, pilot)
    session.commit()
    session.refresh(run)
    return {"run": row_dict(run), "reconciliationRefs": reconciliation_refs}


def readiness_check(key: str, title: str, passed: bool, detail: str, severity: str = "failure") -> dict[str, Any]:
    return {"key": key, "title": title, "passed": passed, "detail": detail, "severity": "pass" if passed else severity}


@router.post("/readiness/assess")
def assess_readiness(
    payload: ReadinessRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    membership = require_site_access(session, auth, payload.siteRef)
    site = session.exec(select(OnboardingSiteV27).where(OnboardingSiteV27.site_ref == payload.siteRef)).first()
    providers = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.site_ref == payload.siteRef)).all()
    adapters = session.exec(select(SpeechAdapterV29).where(SpeechAdapterV29.site_ref == payload.siteRef)).all()
    packs = session.exec(select(VeterinaryTerminologyPackV29).where(VeterinaryTerminologyPackV29.site_ref == payload.siteRef)).all()
    simulators = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.site_ref == payload.siteRef)).all()
    connectors = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.site_ref == payload.siteRef)).all()
    migration_head: str | None = None
    try:
        migration_head = session.connection().execute(text("select version_num from alembic_version")).scalar_one_or_none()
    except Exception:
        migration_head = None
    chain = verify_event_chain(session)
    device = payload.deviceDiagnostics
    approved_providers = [row for row in providers if row.status == "approved" and row.last_test_status == "passed" and not row.raw_audio_retention]
    tested_adapters = [row for row in adapters if row.last_test_status == "passed"]
    approved_packs = [row for row in packs if row.status == "approved"]
    tested_simulators = [row for row in simulators if row.last_test_status == "passed"]
    unsafe_connectors = [row.connector_ref for row in connectors if row.status == "active" and row.mode not in {"shadow", "read_only"}]
    missing_secrets = [row.connector_ref for row in connectors if row.status == "active" and row.secret_env and not os.getenv(row.secret_env)]
    checks = [
        readiness_check("site.configuration", "Approved site configuration", bool(site and site.status in {"approved", "changes_pending"} and site.active_release_ref), "Site lacks an active approved configuration release."),
        readiness_check("identity.membership", "Authenticated site membership", membership.status == "active", "Current user lacks active site membership."),
        readiness_check("database.connection", "Database connectivity", True, "Current transaction can read and write the governed database."),
        readiness_check("migration.head", "Current migration head", migration_head == "0023_hospital_pilot_v29", f"Current migration head is {migration_head or 'unavailable'}; expected 0023_hospital_pilot_v29."),
        readiness_check("speech.provider", "Approved speech provider", bool(approved_providers), "No tested approved speech provider with raw-audio retention disabled."),
        readiness_check("speech.adapter", "Tested streaming speech adapter", bool(tested_adapters), "No adapter has passed provider, device, privacy, latency and reconnect tests."),
        readiness_check("terminology.pack", "Approved veterinary terminology release", bool(approved_packs), "No independently approved veterinary terminology pack."),
        readiness_check("simulator.coverage", "Tested external-system simulator", bool(tested_simulators), "No tested integration simulator is available.", "warning"),
        readiness_check("device.microphone", "Microphone permission", device.get("microphonePermission") == "granted", "Microphone permission is not confirmed."),
        readiness_check("device.secure_context", "Secure browser context", bool(device.get("secureContext", False)), "Browser is not using a secure context."),
        readiness_check("network.online", "Network available", bool(device.get("online", False)), "Device reports no network connectivity.", "warning"),
        readiness_check("connector.safe_modes", "Connector modes are no-write", not unsafe_connectors, f"Unsafe active connector modes: {unsafe_connectors}"),
        readiness_check("connector.secrets", "Active connector secrets loaded", not missing_secrets, f"Missing connector secrets: {missing_secrets}"),
        readiness_check("backup.verified", "Backup evidence", payload.backupVerified, "Backup verification has not been supplied."),
        readiness_check("restore.verified", "Restore rehearsal evidence", payload.restoreVerified, "Restore rehearsal verification has not been supplied."),
        readiness_check("evidence.chain", "Evidence-chain integrity", bool(chain.get("ok")), f"Evidence-chain failures: {chain.get('failures', [])}"),
    ]
    blockers = [row["title"] for row in checks if not row["passed"] and row["severity"] == "failure"]
    warnings = [row["title"] for row in checks if not row["passed"] and row["severity"] == "warning"]
    status = "NOT_READY" if blockers else ("READY_WITH_RESTRICTIONS" if warnings else "READY")
    passed_count = len([row for row in checks if row["passed"]])
    assessment = ReadinessAssessmentV29(
        assessment_ref=new_ref("readiness-v29"),
        organisation_ref=site.organisation_ref if site else "unknown",
        site_ref=payload.siteRef,
        premises_ref=site.premises_ref if site else "unknown",
        pilot_ref=payload.pilotRef,
        overall_status=status,
        score=round((passed_count / max(1, len(checks))) * 100),
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        device_diagnostics=device,
        evidence_chain_ok=bool(chain.get("ok")),
        migration_head=migration_head,
        assessed_by_subject=auth.subject,
        assessed_by_name=auth.actor_name,
        assessed_by_role=auth.role,
    )
    session.add(assessment)
    session.flush()
    assessment.evidence_ref = record_v29(session, auth, action="hospital_readiness_assessed", entity_type="readiness_assessment", entity_ref=assessment.assessment_ref, new_state=row_dict(assessment), reason=f"Hospital pilot readiness result: {status}", risk="green" if status == "READY" else ("amber" if status == "READY_WITH_RESTRICTIONS" else "red"))
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return {"assessment": row_dict(assessment)}


@router.post("/pilots")
def create_pilot(
    payload: PilotCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    if payload.mode not in PILOT_MODES:
        raise HTTPException(status_code=422, detail="pilot mode must be synthetic or shadow")
    require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    if payload.endAt and payload.startAt and payload.endAt <= payload.startAt:
        raise HTTPException(status_code=422, detail="pilot end must follow start")
    provider_refs = set(payload.allowedProviderRefs)
    simulator_refs = set(payload.allowedSimulatorRefs)
    providers = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.provider_ref.in_(provider_refs))).all() if provider_refs else []
    simulators = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.simulator_ref.in_(simulator_refs))).all() if simulator_refs else []
    if len(providers) != len(provider_refs) or any(row.site_ref != payload.siteRef for row in providers):
        raise HTTPException(status_code=409, detail="all pilot speech providers must exist at the selected site")
    if len(simulators) != len(simulator_refs) or any(row.site_ref != payload.siteRef for row in simulators):
        raise HTTPException(status_code=409, detail="all pilot simulators must exist at the selected site")
    pilot_ref = new_ref("hospital-pilot-v29")
    authority = PilotAuthorityV24(
        authority_ref=new_ref("pilot-authority-v29"),
        run_ref=pilot_ref,
        premises_ref=site.premises_ref,
        service_line=payload.serviceLine,
        requested_mode=payload.mode,
        status="draft",
        scope={"siteRef": payload.siteRef, "department": payload.department, "caseLimit": payload.caseLimit},
        success_criteria=payload.successCriteria or {"minimumAccuracy": 0.90, "minimumAverageSecondsSaved": 60, "maximumReconciliationRate": 0.10, "redIncidents": 0},
        stop_criteria=payload.stopCriteria or {"maxRedIncidents": 0, "minimumAccuracy": 0.75, "minimumAccuracySamples": 5, "maxOpenReconciliation": 3},
        rollback_plan=payload.rollbackPlan or {"action": "Stop new pilot activity and return to existing hospital workflow", "urgentAccess": "preserved"},
        integration_scope=list(simulator_refs),
        automation_mode="disabled",
        accountable_owner_subject=auth.subject,
        accountable_owner_name=auth.actor_name,
        accountable_owner_role=auth.role,
        clinical_owner_subject=payload.clinicalOwnerSubject,
        clinical_owner_name=payload.clinicalOwnerName,
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
    )
    session.add(authority)
    session.flush()
    pilot = HospitalPilotV29(
        pilot_ref=pilot_ref,
        authority_ref=authority.authority_ref,
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        premises_ref=site.premises_ref,
        name=payload.name,
        department=payload.department,
        service_line=payload.serviceLine,
        mode=payload.mode,
        case_limit=payload.caseLimit,
        start_at=payload.startAt,
        end_at=payload.endAt,
        allowed_device_refs=payload.allowedDeviceRefs,
        allowed_provider_refs=list(provider_refs),
        allowed_simulator_refs=list(simulator_refs),
        success_criteria=authority.success_criteria,
        stop_criteria=authority.stop_criteria,
        rollback_plan=authority.rollback_plan,
        accountable_owner_subject=auth.subject,
        accountable_owner_name=auth.actor_name,
        clinical_owner_subject=payload.clinicalOwnerSubject,
        clinical_owner_name=payload.clinicalOwnerName,
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(pilot)
    session.flush()
    evidence_ref = record_v29(session, auth, action="hospital_pilot_created", entity_type="hospital_pilot", entity_ref=pilot.pilot_ref, new_state={"pilot": row_dict(pilot), "authority": row_dict(authority)}, reason="Create bounded synthetic or shadow hospital pilot plan")
    authority.evidence_event_ref = evidence_ref
    session.add(authority)
    session.commit()
    session.refresh(pilot)
    return {"pilot": row_dict(pilot), "authority": row_dict(authority)}


@router.post("/pilots/{pilot_ref}/approve")
def approve_pilot(
    pilot_ref: str,
    payload: PilotApproval,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    if payload.approvalType not in APPROVAL_TYPES:
        raise HTTPException(status_code=422, detail="approval type must be operations or clinical")
    if payload.approvalType == "operations" and auth.role not in OPS_ROLES:
        raise HTTPException(status_code=403, detail="operations approval role required")
    if payload.approvalType == "clinical" and auth.role not in CLINICAL_ROLES:
        raise HTTPException(status_code=403, detail="clinical approval role required")
    pilot = get_pilot(session, pilot_ref)
    require_site_access(session, auth, pilot.site_ref)
    require_version(pilot, payload.expectedVersion)
    if payload.approvalType == "operations" and pilot.clinical_approved_by_subject == auth.subject:
        raise HTTPException(status_code=409, detail={"code": "independent_pilot_approvals_required"})
    if payload.approvalType == "clinical" and pilot.operations_approved_by_subject == auth.subject:
        raise HTTPException(status_code=409, detail={"code": "independent_pilot_approvals_required"})
    previous = row_dict(pilot)
    approval = PilotApprovalV29(
        approval_ref=new_ref("pilot-approval-v29"),
        pilot_ref=pilot.pilot_ref,
        approval_type=payload.approvalType,
        decision="approved",
        reason=payload.reason,
        pilot_version=pilot.version,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
    )
    if payload.approvalType == "operations":
        pilot.operations_approved_by_subject = auth.subject
        pilot.operations_approved_by_name = auth.actor_name
        pilot.operations_approved_at = utc_now()
    else:
        pilot.clinical_approved_by_subject = auth.subject
        pilot.clinical_approved_by_name = auth.actor_name
        pilot.clinical_approved_at = utc_now()
    pilot.status = "approved_pending_readiness" if pilot.operations_approved_by_subject and pilot.clinical_approved_by_subject else "approval_pending"
    pilot.version += 1
    pilot.updated_by_subject = auth.subject
    pilot.updated_at = utc_now()
    session.add(pilot)
    session.add(approval)
    session.flush()
    approval.evidence_ref = record_v29(session, auth, action=f"pilot_{payload.approvalType}_approved", entity_type="hospital_pilot", entity_ref=pilot.pilot_ref, previous_state=previous, new_state=row_dict(pilot), reason=payload.reason, risk="green")
    session.add(approval)
    session.commit()
    session.refresh(pilot)
    return {"pilot": row_dict(pilot), "approval": row_dict(approval)}


@router.post("/pilots/{pilot_ref}/activate")
def activate_pilot(
    pilot_ref: str,
    payload: PilotActivate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*OPS_ROLES)),
) -> dict[str, Any]:
    pilot = get_pilot(session, pilot_ref)
    require_site_access(session, auth, pilot.site_ref)
    require_version(pilot, payload.expectedVersion)
    if not pilot.operations_approved_by_subject or not pilot.clinical_approved_by_subject:
        raise HTTPException(status_code=409, detail={"code": "two_person_pilot_approval_required"})
    if pilot.operations_approved_by_subject == pilot.clinical_approved_by_subject:
        raise HTTPException(status_code=409, detail={"code": "independent_pilot_approvals_required"})
    assessment = session.exec(select(ReadinessAssessmentV29).where(
        ReadinessAssessmentV29.assessment_ref == payload.readinessAssessmentRef,
        ReadinessAssessmentV29.site_ref == pilot.site_ref,
    )).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="readiness assessment not found")
    if assessment.overall_status == "NOT_READY":
        raise HTTPException(status_code=409, detail={"code": "pilot_not_ready", "blockers": assessment.blockers})
    if assessment.overall_status == "READY_WITH_RESTRICTIONS" and not payload.restrictionsAcknowledged:
        raise HTTPException(status_code=409, detail={"code": "readiness_restrictions_acknowledgement_required", "warnings": assessment.warnings})
    previous = row_dict(pilot)
    pilot.status = "active"
    pilot.readiness_assessment_ref = assessment.assessment_ref
    pilot.activated_at = utc_now()
    pilot.version += 1
    pilot.updated_by_subject = auth.subject
    pilot.updated_at = utc_now()
    session.add(pilot)
    authority = session.exec(select(PilotAuthorityV24).where(PilotAuthorityV24.authority_ref == pilot.authority_ref)).first()
    if authority:
        authority.status = "active"
        authority.activated_at = utc_now()
        authority.version += 1
        authority.updated_at = utc_now()
        session.add(authority)
    record_v29(session, auth, action="hospital_pilot_activated", entity_type="hospital_pilot", entity_ref=pilot.pilot_ref, previous_state=previous, new_state=row_dict(pilot), reason=payload.reason, risk="amber")
    session.commit()
    session.refresh(pilot)
    return {"pilot": row_dict(pilot), "readiness": row_dict(assessment)}


@router.post("/pilots/{pilot_ref}/cases/start")
def start_pilot_case(
    pilot_ref: str,
    payload: PilotCaseStart,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    pilot = get_pilot(session, pilot_ref)
    require_site_access(session, auth, pilot.site_ref)
    require_version(pilot, payload.expectedVersion)
    now = utc_now()
    blocked_reason: str | None = None
    if pilot.status != "active":
        blocked_reason = f"pilot status is {pilot.status}"
    elif pilot.start_at and now < pilot.start_at:
        blocked_reason = "pilot has not started"
    elif pilot.end_at and now > pilot.end_at:
        blocked_reason = "pilot has ended"
    elif pilot.cases_started >= pilot.case_limit:
        blocked_reason = "pilot case limit reached"
    else:
        reasons = pilot_stop_reasons(session, pilot)
        if reasons:
            blocked_reason = "; ".join(reasons)
            if pilot.auto_stop_enabled:
                stop_pilot(session, auth, pilot, blocked_reason)
    if blocked_reason:
        session.commit()
        if payload.urgentAccess:
            return {
                "pilotApplied": False,
                "urgentAccessPreserved": True,
                "reason": blocked_reason,
                "instruction": "Continue urgent patient care through the existing non-pilot hospital workflow.",
                "pilot": row_dict(pilot),
            }
        raise HTTPException(status_code=409, detail={"code": "pilot_activity_blocked", "reason": blocked_reason})
    previous = row_dict(pilot)
    pilot.cases_started += 1
    pilot.version += 1
    pilot.updated_by_subject = auth.subject
    pilot.updated_at = utc_now()
    session.add(pilot)
    record_v29(session, auth, action="pilot_case_started", entity_type="hospital_pilot", entity_ref=pilot.pilot_ref, previous_state=previous, new_state={"pilot": row_dict(pilot), "patientRef": payload.patientRef, "episodeRef": payload.episodeRef}, reason="Begin bounded pilot activity for an explicitly selected case", patient_ref=payload.patientRef, episode_ref=payload.episodeRef, risk="amber")
    session.commit()
    session.refresh(pilot)
    return {"pilotApplied": True, "urgentAccessPreserved": True, "pilot": row_dict(pilot)}


@router.post("/pilots/{pilot_ref}/incidents")
def create_incident(
    pilot_ref: str,
    payload: IncidentCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    if payload.severity not in {"green", "amber", "red"}:
        raise HTTPException(status_code=422, detail="severity must be green, amber or red")
    pilot = get_pilot(session, pilot_ref)
    require_site_access(session, auth, pilot.site_ref)
    incident = PilotIncidentV29(
        incident_ref=new_ref("pilot-incident-v29"),
        pilot_ref=pilot_ref,
        severity=payload.severity,
        category=payload.category,
        patient_ref=payload.patientRef,
        episode_ref=payload.episodeRef,
        synthetic=payload.synthetic,
        description=payload.description,
        immediate_action=payload.immediateAction,
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
    )
    session.add(incident)
    session.flush()
    incident.evidence_ref = record_v29(session, auth, action="pilot_incident_recorded", entity_type="pilot_incident", entity_ref=incident.incident_ref, new_state=row_dict(incident), reason=payload.immediateAction, patient_ref=payload.patientRef, episode_ref=payload.episodeRef, risk=payload.severity)
    session.add(incident)
    reasons = evaluate_and_stop(session, auth, pilot)
    session.commit()
    session.refresh(incident)
    session.refresh(pilot)
    return {"incident": row_dict(incident), "pilot": row_dict(pilot), "stopReasons": reasons}


@router.post("/pilots/{pilot_ref}/measurements")
def create_measurement(
    pilot_ref: str,
    payload: MeasurementCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    pilot = get_pilot(session, pilot_ref)
    require_site_access(session, auth, pilot.site_ref)
    measurement = PilotMeasurementV29(
        measurement_ref=new_ref("pilot-measure-v29"),
        pilot_ref=pilot_ref,
        episode_ref=payload.episodeRef,
        synthetic=payload.synthetic,
        metric_type=payload.metricType,
        value=payload.value,
        unit=payload.unit,
        baseline_value=payload.baselineValue,
        metadata_payload=payload.metadata,
        recorded_by_subject=auth.subject,
        recorded_by_name=auth.actor_name,
    )
    session.add(measurement)
    session.flush()
    measurement.evidence_ref = record_v29(session, auth, action="pilot_measurement_recorded", entity_type="pilot_measurement", entity_ref=measurement.measurement_ref, new_state=row_dict(measurement), reason="Record bounded pilot accuracy, time, correction or safety measurement", episode_ref=payload.episodeRef, risk="green")
    session.add(measurement)
    reasons = evaluate_and_stop(session, auth, pilot)
    session.commit()
    session.refresh(measurement)
    session.refresh(pilot)
    return {"measurement": row_dict(measurement), "pilot": row_dict(pilot), "stopReasons": reasons}


@router.get("/pilots/{pilot_ref}/dashboard")
def pilot_dashboard(
    pilot_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    pilot = get_pilot(session, pilot_ref)
    require_site_access(session, auth, pilot.site_ref)
    measurements = session.exec(select(PilotMeasurementV29).where(PilotMeasurementV29.pilot_ref == pilot_ref)).all()
    incidents = session.exec(select(PilotIncidentV29).where(PilotIncidentV29.pilot_ref == pilot_ref)).all()
    runs = session.exec(select(SimulatorRunV29).where(SimulatorRunV29.pilot_ref == pilot_ref)).all()
    by_type: dict[str, list[PilotMeasurementV29]] = {}
    for row in measurements:
        by_type.setdefault(row.metric_type, []).append(row)
    averages = {key: sum(row.value for row in rows) / len(rows) for key, rows in by_type.items()}
    saved_values = [row.baseline_value - row.value for row in measurements if row.baseline_value is not None]
    average_saved = sum(saved_values) / len(saved_values) if saved_values else 0.0
    reasons = pilot_stop_reasons(session, pilot)
    return {
        "pilot": row_dict(pilot),
        "summary": {
            "casesStarted": pilot.cases_started,
            "caseLimit": pilot.case_limit,
            "measurementCount": len(measurements),
            "averageTranscriptionAccuracy": averages.get("transcription_accuracy"),
            "averageSecondsSaved": average_saved,
            "openIncidents": len([row for row in incidents if row.status == "open"]),
            "redIncidents": len([row for row in incidents if row.severity == "red"]),
            "simulatorRuns": len(runs),
            "failedSimulatorRuns": len([row for row in runs if row.detection_status != "passed"]),
        },
        "metricAverages": averages,
        "measurements": [row_dict(row) for row in measurements],
        "incidents": [row_dict(row) for row in incidents],
        "simulatorRuns": [row_dict(row) for row in runs],
        "currentStopReasons": reasons,
        "successCriteria": pilot.success_criteria,
        "stopCriteria": pilot.stop_criteria,
    }


def latest_readiness(session: Session, site_ref: str, pilot_ref: str | None) -> ReadinessAssessmentV29 | None:
    statement = select(ReadinessAssessmentV29).where(ReadinessAssessmentV29.site_ref == site_ref)
    if pilot_ref:
        statement = statement.where(ReadinessAssessmentV29.pilot_ref == pilot_ref)
    return session.exec(statement.order_by(ReadinessAssessmentV29.assessed_at.desc())).first()


def create_artifact(session: Session, auth: AuthContext, site: OnboardingSiteV27, pilot_ref: str | None, artifact_type: str, content: dict[str, Any]) -> ExportArtifactV29:
    artifact = ExportArtifactV29(
        artifact_ref=new_ref(f"{artifact_type}-v29"),
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        pilot_ref=pilot_ref,
        artifact_type=artifact_type,
        content=content,
        generated_by_subject=auth.subject,
        generated_by_name=auth.actor_name,
    )
    session.add(artifact)
    session.flush()
    artifact.evidence_ref = record_v29(session, auth, action=f"{artifact_type}_generated", entity_type="export_artifact", entity_ref=artifact.artifact_ref, new_state={"artifactRef": artifact.artifact_ref, "artifactType": artifact_type, "contentHash": digest(content)}, reason=f"Generate exportable {artifact_type.replace('_', ' ')}")
    session.add(artifact)
    return artifact


@router.post("/exports/vendor-spec")
def export_vendor_spec(
    payload: ExportRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    connectors = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.site_ref == payload.siteRef)).all()
    simulators = session.exec(select(IntegrationSimulatorV29).where(IntegrationSimulatorV29.site_ref == payload.siteRef)).all()
    adapters = session.exec(select(SpeechAdapterV29).where(SpeechAdapterV29.site_ref == payload.siteRef)).all()
    content = {
        "title": f"LucyWorks vendor integration specification - {site.name}",
        "version": "v29",
        "site": {"siteRef": site.site_ref, "premisesRef": site.premises_ref, "organisationRef": site.organisation_ref},
        "safetyBoundary": {"writeBack": False, "modes": ["shadow", "read_only"], "syntheticDataMarked": True, "uncertainMatches": "reconciliation_required"},
        "connectorContracts": [
            {
                "connectorType": row.connector_type,
                "vendorName": row.vendor_name,
                "environment": row.environment,
                "authentication": "secret reference supplied out of band; least privilege; read-only",
                "requiredEnvelope": ["externalEventId", "eventType", "occurredAt", "payloadSummary"],
                "patientMatching": "No automatic attachment when identifiers are missing, conflicting or uncertain",
                "health": {"staleAfterSeconds": row.stale_after_seconds, "failureMustSurface": True},
                "writeOperations": [],
            }
            for row in connectors if row.environment != "simulator"
        ],
        "simulatorCoverage": [{"type": row.connector_type, "name": row.name, "faults": sorted(FAULT_TYPES - {"none"})} for row in simulators],
        "speechAdapters": [{"name": row.name, "type": row.adapter_type, "processingLocation": row.processing_location, "protocol": row.protocol, "rawAudioRetention": False, "reconnect": row.reconnect_enabled} for row in adapters],
        "errorContract": {"stale": "visible", "delayed": "visible", "duplicate": "idempotent", "conflict": "reconciliation", "outage": "no silent substitute"},
        "acceptanceTests": ["configuration", "secret presence", "read-only permission", "health check", "duplicate event", "delayed event", "incorrect identifier", "out-of-order event", "reconciliation", "restore"],
    }
    artifact = create_artifact(session, auth, site, payload.pilotRef, "vendor_specification", content)
    session.commit()
    session.refresh(artifact)
    return {"artifact": row_dict(artifact)}


@router.post("/exports/deployment-pack")
def export_deployment_pack(
    payload: ExportRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PILOT_CONTROL_ROLES)),
) -> dict[str, Any]:
    require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    pilot = get_pilot(session, payload.pilotRef) if payload.pilotRef else None
    readiness = latest_readiness(session, payload.siteRef, payload.pilotRef)
    content = {
        "title": f"LucyWorks hospital deployment pack - {site.name}",
        "version": "v29",
        "site": {"siteRef": site.site_ref, "premisesRef": site.premises_ref, "organisationRef": site.organisation_ref, "address": site.address},
        "readiness": row_dict(readiness) if readiness else {"overall_status": "NOT_ASSESSED"},
        "pilot": row_dict(pilot) if pilot else None,
        "preStartChecklist": ["Named users and roles", "Approved devices", "Microphone test", "Network test", "Approved speech provider", "Approved terminology release", "Tested simulators", "Backup evidence", "Restore rehearsal", "Incident route", "Rollback owner"],
        "dailyChecklist": ["Review readiness warnings", "Review open reconciliation", "Review incidents", "Confirm connector freshness", "Confirm pilot case count", "Record accuracy and time measurements"],
        "stopProcedure": {"newPilotActivity": "blocked", "urgentPatientAccess": "preserved through existing workflow", "externalWriteBack": "not available", "rollback": pilot.rollback_plan if pilot else {"action": "Return to existing hospital workflow"}},
        "training": ["Synthetic banner recognition", "Speech correction and confirmation", "Medicine wording review", "Reconciliation", "Incident creation", "Urgent-care bypass", "Pilot stop and rollback"],
        "dataProtection": {"rawAudioRetention": False, "syntheticData": "clearly marked", "patientAttachment": "explicit reconciliation only", "vendorSecrets": "environment references only"},
        "successMeasures": pilot.success_criteria if pilot else {},
        "stopMeasures": pilot.stop_criteria if pilot else {},
    }
    artifact = create_artifact(session, auth, site, payload.pilotRef, "hospital_deployment_pack", content)
    session.commit()
    session.refresh(artifact)
    return {"artifact": row_dict(artifact)}


@router.get("/exports/{artifact_ref}")
def get_export_artifact(
    artifact_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    artifact = session.exec(select(ExportArtifactV29).where(ExportArtifactV29.artifact_ref == artifact_ref)).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="artifact not found")
    require_site_access(session, auth, artifact.site_ref)
    return {"artifact": row_dict(artifact)}
