from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, ALL_AUTHENTICATED_ROLES, SENIOR_ROLES, require_roles
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState
from app.operational_context_v26_models import SiteMembershipV26
from app.organisation_onboarding_v27_models import OnboardingSiteV27
from app.real_hospital_connection_v28_models import (
    IntegrationConnectorV28,
    IntegrationEventV28,
    IntegrationPromotionV28,
    ReconciliationItemV28,
    SpeechProviderV28,
    SpeechSegmentV28,
    SpeechSessionV28,
    utc_now,
)
from app.speech_capture_v19_routes import CaptureCreate, create_capture

router = APIRouter(prefix="/api/v28/deployment", tags=["real-hospital-connection-speech-v28"])
CAPTURE_ROLES = ("admin", "ops_manager", "clinician", "clinical_director", "senior_clinician", "supervisor", "nurse")
CONNECTOR_TYPES = {"identity", "patient_management", "laboratory", "imaging", "pharmacy", "insurance", "communications"}
PROVIDER_TYPES = {"browser", "cloud", "private"}
PROMOTABLE_MODES = {"shadow", "read_only"}


class SpeechProviderCreate(BaseModel):
    organisationRef: str
    siteRef: str
    name: str
    providerType: str = "browser"
    endpointHost: str | None = None
    processingRegion: str = "GB"
    language: str = "en-GB"
    supportsStreaming: bool = True
    supportsDiarization: bool = False
    supportsWordTimestamps: bool = False
    supportsWordConfidence: bool = False
    rawAudioRetention: bool = False
    secretEnv: str | None = None
    configuration: dict[str, Any] = PydanticField(default_factory=dict)


class SpeechSessionStart(BaseModel):
    providerRef: str
    siteRef: str
    episodeRef: str
    captureMode: str = "clinical_dictation"
    language: str = "en-GB"
    noticeVersion: str = "v28-default"
    noticeAcknowledged: bool = False
    rawAudioRetained: bool = False
    deviceDiagnostics: dict[str, Any] = PydanticField(default_factory=dict)


class SpeechSegmentAppend(BaseModel):
    expectedVersion: int
    sequence: int = PydanticField(ge=1)
    text: str = PydanticField(min_length=1, max_length=10000)
    confidence: float | None = PydanticField(default=None, ge=0, le=1)
    startedMs: int | None = PydanticField(default=None, ge=0)
    endedMs: int | None = PydanticField(default=None, ge=0)
    speakerLabel: str | None = None
    isFinal: bool = True
    source: str = "browser"
    words: list[dict[str, Any]] = PydanticField(default_factory=list)


class VersionedReason(BaseModel):
    expectedVersion: int
    reason: str = PydanticField(min_length=3, max_length=2000)


class ConnectorCreate(BaseModel):
    organisationRef: str
    siteRef: str
    connectorType: str
    vendorName: str
    environment: str = "sandbox"
    endpointHost: str | None = None
    secretEnv: str | None = None
    staleAfterSeconds: int = PydanticField(default=900, ge=60, le=86400)
    configuration: dict[str, Any] = PydanticField(default_factory=dict)


class PromotionRequest(BaseModel):
    expectedVersion: int
    requestedMode: str
    reason: str = PydanticField(min_length=5, max_length=2000)
    evidenceRefs: list[str] = PydanticField(default_factory=list)


class PromotionDecision(BaseModel):
    expectedVersion: int
    reason: str = PydanticField(min_length=5, max_length=2000)


class IntegrationEventIngest(BaseModel):
    externalEventId: str
    eventType: str
    payloadSummary: dict[str, Any] = PydanticField(default_factory=dict)
    patientRef: str | None = None
    episodeRef: str | None = None
    occurredAt: datetime | None = None


class ReconciliationResolve(BaseModel):
    expectedVersion: int
    resolution: str = PydanticField(min_length=3, max_length=2000)
    resolvedRef: str | None = None


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def normalised_host(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    if not parsed.hostname:
        raise HTTPException(status_code=422, detail="endpoint host is invalid")
    return parsed.hostname.lower()


def require_site_access(session: Session, auth: AuthContext, site_ref: str) -> SiteMembershipV26:
    membership = session.exec(select(SiteMembershipV26).where(
        SiteMembershipV26.subject == auth.subject,
        SiteMembershipV26.site_ref == site_ref,
        SiteMembershipV26.status == "active",
    )).first()
    if not membership:
        raise HTTPException(status_code=403, detail={"code": "site_access_required", "siteRef": site_ref})
    if membership.role != auth.role:
        raise HTTPException(status_code=403, detail={
            "code": "site_role_mismatch", "siteRef": site_ref,
            "membershipRole": membership.role, "tokenRole": auth.role,
        })
    return membership


def configured_site(session: Session, site_ref: str) -> OnboardingSiteV27:
    site = session.exec(select(OnboardingSiteV27).where(
        OnboardingSiteV27.site_ref == site_ref,
        OnboardingSiteV27.active_release_ref != None,  # noqa: E711
        OnboardingSiteV27.status.in_(["approved", "changes_pending"]),
    )).first()
    if not site:
        raise HTTPException(status_code=409, detail={"code": "approved_site_configuration_required", "siteRef": site_ref})
    return site


def record_event(
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
        event_type=f"v28_{action}",
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
        justification="Governed real-hospital connection and resumable speech control",
        evidence_links=[{"type": entity_type, "id": entity_ref}],
        compliance_domain="clinical_records" if patient_ref else "information_governance",
        risk_level=risk,
        source_module="real-hospital-connection-v28",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or entity_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v28:{entity_type}:{entity_ref}:{action}:{digest(new_state)[:20]}",
    )
    return event.event_ref


@router.get("/control-centre")
def control_centre(
    siteRef: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_AUTHENTICATED_ROLES)),
) -> dict[str, Any]:
    require_site_access(session, auth, siteRef)
    now = utc_now()
    providers = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.site_ref == siteRef)).all()
    connectors = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.site_ref == siteRef)).all()
    reconciliations = session.exec(select(ReconciliationItemV28).where(
        ReconciliationItemV28.connector_ref.in_([row.connector_ref for row in connectors]),
        ReconciliationItemV28.status == "open",
    )).all() if connectors else []
    active_sessions = session.exec(select(SpeechSessionV28).where(
        SpeechSessionV28.site_ref == siteRef,
        SpeechSessionV28.status.in_(["active", "interrupted", "ready_for_review"]),
    )).all()
    connector_rows = []
    for connector in connectors:
        stale = bool(
            connector.status == "active" and connector.last_event_at and
            (now - connector.last_event_at).total_seconds() > connector.stale_after_seconds
        )
        connector_rows.append({**row_dict(connector), "stale": stale})
    return {
        "siteRef": siteRef,
        "speechProviders": [row_dict(item) for item in providers],
        "speechSessions": [row_dict(item) for item in active_sessions],
        "connectors": connector_rows,
        "openReconciliation": [row_dict(item) for item in reconciliations],
        "summary": {
            "approvedSpeechProviders": len([item for item in providers if item.status == "approved"]),
            "activeConnectors": len([item for item in connectors if item.status == "active"]),
            "degradedConnectors": len([item for item in connector_rows if item["status"] == "degraded" or item["stale"]]),
            "openReconciliation": len(reconciliations),
            "interruptedSpeechSessions": len([item for item in active_sessions if item.status == "interrupted"]),
        },
        "boundary": "Connections remain shadow or read-only. No v28 route performs external-system write-back.",
    }


@router.post("/speech/providers")
def create_speech_provider(
    payload: SpeechProviderCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    membership = require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    if membership.organisation_ref != payload.organisationRef or site.organisation_ref != payload.organisationRef:
        raise HTTPException(status_code=409, detail="organisation and site context do not match")
    if payload.providerType not in PROVIDER_TYPES:
        raise HTTPException(status_code=422, detail="unsupported speech provider type")
    if payload.rawAudioRetention:
        raise HTTPException(status_code=409, detail="raw-audio retention is disabled for v28")
    provider = SpeechProviderV28(
        provider_ref=new_ref("speech-provider"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        name=payload.name.strip(),
        provider_type=payload.providerType,
        endpoint_host=normalised_host(payload.endpointHost),
        processing_region=payload.processingRegion.strip().upper(),
        language=payload.language,
        supports_streaming=payload.supportsStreaming,
        supports_diarization=payload.supportsDiarization,
        supports_word_timestamps=payload.supportsWordTimestamps,
        supports_word_confidence=payload.supportsWordConfidence,
        raw_audio_retention=False,
        secret_env=payload.secretEnv.strip() if payload.secretEnv else None,
        configuration=payload.configuration,
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(provider)
    session.flush()
    record_event(session, auth, action="speech_provider_created", entity_type="speech_provider", entity_ref=provider.provider_ref, new_state=row_dict(provider), reason="Speech provider configured in draft state")
    session.commit()
    session.refresh(provider)
    return {"provider": row_dict(provider)}


@router.post("/speech/providers/{provider_ref}/test")
def test_speech_provider(
    provider_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    provider = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.provider_ref == provider_ref)).first()
    if not provider:
        raise HTTPException(status_code=404, detail="speech provider not found")
    require_site_access(session, auth, provider.site_ref)
    if provider.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale provider", "currentVersion": provider.version})
    previous = row_dict(provider)
    failures = []
    if provider.provider_type != "browser" and not provider.endpoint_host:
        failures.append("endpoint host missing")
    if provider.provider_type != "browser" and provider.secret_env and not os.getenv(provider.secret_env, ""):
        failures.append(f"secret environment variable {provider.secret_env} is not loaded")
    if provider.raw_audio_retention:
        failures.append("raw-audio retention must remain disabled")
    provider.last_test_status = "failed" if failures else "passed"
    provider.last_test_detail = "; ".join(failures) if failures else "Configuration, privacy boundary and credential presence checks passed. No patient audio was transmitted."
    provider.last_test_at = utc_now()
    provider.status = "test_failed" if failures else "tested"
    provider.version += 1
    provider.updated_by_subject = auth.subject
    provider.updated_at = utc_now()
    session.add(provider)
    record_event(session, auth, action="speech_provider_tested", entity_type="speech_provider", entity_ref=provider.provider_ref, previous_state=previous, new_state=row_dict(provider), reason=payload.reason, risk="red" if failures else "green")
    session.commit()
    session.refresh(provider)
    return {"provider": row_dict(provider), "passed": not failures, "failures": failures}


@router.post("/speech/providers/{provider_ref}/approve")
def approve_speech_provider(
    provider_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    provider = session.exec(select(SpeechProviderV28).where(SpeechProviderV28.provider_ref == provider_ref)).first()
    if not provider:
        raise HTTPException(status_code=404, detail="speech provider not found")
    require_site_access(session, auth, provider.site_ref)
    if provider.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale provider", "currentVersion": provider.version})
    if provider.last_test_status != "passed":
        raise HTTPException(status_code=409, detail="provider must pass configuration testing before approval")
    if provider.provider_type != "browser" and provider.created_by_subject == auth.subject:
        raise HTTPException(status_code=409, detail="an external speech provider requires independent approval")
    previous = row_dict(provider)
    provider.status = "approved"
    provider.approved_by_subject = auth.subject
    provider.approved_at = utc_now()
    provider.version += 1
    provider.updated_by_subject = auth.subject
    provider.updated_at = utc_now()
    session.add(provider)
    record_event(session, auth, action="speech_provider_approved", entity_type="speech_provider", entity_ref=provider.provider_ref, previous_state=previous, new_state=row_dict(provider), reason=payload.reason, risk="green")
    session.commit()
    session.refresh(provider)
    return {"provider": row_dict(provider)}


@router.post("/speech/sessions")
def start_speech_session(
    payload: SpeechSessionStart,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    membership = require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    if not payload.noticeAcknowledged:
        raise HTTPException(status_code=409, detail="recording/privacy notice must be acknowledged")
    if payload.rawAudioRetained:
        raise HTTPException(status_code=409, detail="raw-audio retention is disabled")
    provider = session.exec(select(SpeechProviderV28).where(
        SpeechProviderV28.provider_ref == payload.providerRef,
        SpeechProviderV28.site_ref == payload.siteRef,
        SpeechProviderV28.status == "approved",
    )).first()
    if not provider:
        raise HTTPException(status_code=409, detail="an approved site speech provider is required")
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == payload.episodeRef)).first()
    if not episode or not episode.patient_ref:
        raise HTTPException(status_code=404, detail="canonical patient episode not found")
    if episode.premises_ref != site.premises_ref or membership.premises_ref != site.premises_ref:
        raise HTTPException(status_code=409, detail="episode, site and premises context do not match")
    speech_session = SpeechSessionV28(
        session_ref=new_ref("speech-session"),
        provider_ref=provider.provider_ref,
        organisation_ref=site.organisation_ref,
        site_ref=site.site_ref,
        premises_ref=site.premises_ref,
        episode_ref=episode.episode_ref,
        patient_ref=episode.patient_ref,
        capture_mode=payload.captureMode,
        language=payload.language,
        device_diagnostics=payload.deviceDiagnostics,
        notice_version=payload.noticeVersion,
        notice_acknowledged=True,
        raw_audio_retained=False,
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
        created_by_role=auth.role,
    )
    session.add(speech_session)
    session.flush()
    record_event(session, auth, action="speech_session_started", entity_type="speech_session", entity_ref=speech_session.session_ref, new_state=row_dict(speech_session), reason="Approved provider session started with governed patient context", patient_ref=episode.patient_ref, episode_ref=episode.episode_ref)
    session.commit()
    session.refresh(speech_session)
    return {"session": row_dict(speech_session), "provider": row_dict(provider), "patient": {"patientRef": episode.patient_ref, "patientName": episode.patient_name}}


@router.post("/speech/sessions/{session_ref}/segments")
def append_speech_segment(
    session_ref: str,
    payload: SpeechSegmentAppend,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    speech_session = session.exec(select(SpeechSessionV28).where(SpeechSessionV28.session_ref == session_ref)).first()
    if not speech_session:
        raise HTTPException(status_code=404, detail="speech session not found")
    require_site_access(session, auth, speech_session.site_ref)
    if speech_session.created_by_subject != auth.subject and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="only the session owner or a senior role may append")
    if speech_session.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale speech session", "currentVersion": speech_session.version})
    if speech_session.status != "active":
        raise HTTPException(status_code=409, detail=f"session is {speech_session.status}; resume it before appending")
    content_hash = digest({
        "sequence": payload.sequence, "text": payload.text.strip(), "confidence": payload.confidence,
        "startedMs": payload.startedMs, "endedMs": payload.endedMs, "speakerLabel": payload.speakerLabel,
        "isFinal": payload.isFinal, "source": payload.source, "words": payload.words,
    })
    existing = session.exec(select(SpeechSegmentV28).where(
        SpeechSegmentV28.session_ref == session_ref,
        SpeechSegmentV28.sequence == payload.sequence,
    )).first()
    if existing:
        if existing.payload_hash == content_hash:
            return {"session": row_dict(speech_session), "segment": row_dict(existing), "idempotent": True}
        raise HTTPException(status_code=409, detail="sequence already exists with different content")
    segment = SpeechSegmentV28(
        segment_ref=new_ref("speech-segment"),
        session_ref=session_ref,
        sequence=payload.sequence,
        text=payload.text.strip(),
        confidence=payload.confidence,
        started_ms=payload.startedMs,
        ended_ms=payload.endedMs,
        speaker_label=payload.speakerLabel.strip() if payload.speakerLabel else None,
        is_final=payload.isFinal,
        source=payload.source,
        words=payload.words,
        payload_hash=content_hash,
    )
    session.add(segment)
    session.flush()
    final_segments = session.exec(select(SpeechSegmentV28).where(
        SpeechSegmentV28.session_ref == session_ref,
        SpeechSegmentV28.is_final == True,  # noqa: E712
    ).order_by(SpeechSegmentV28.sequence)).all()
    speech_session.transcript_text = " ".join(item.text.strip() for item in final_segments if item.text.strip()).strip()
    speech_session.segment_count = len(final_segments)
    speech_session.version += 1
    speech_session.updated_at = utc_now()
    session.add(speech_session)
    session.commit()
    session.refresh(speech_session)
    session.refresh(segment)
    return {"session": row_dict(speech_session), "segment": row_dict(segment), "idempotent": False}


@router.post("/speech/sessions/{session_ref}/interrupt")
def interrupt_speech_session(
    session_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    speech_session = session.exec(select(SpeechSessionV28).where(SpeechSessionV28.session_ref == session_ref)).first()
    if not speech_session:
        raise HTTPException(status_code=404, detail="speech session not found")
    require_site_access(session, auth, speech_session.site_ref)
    if speech_session.version != payload.expectedVersion or speech_session.status != "active":
        raise HTTPException(status_code=409, detail={"message": "session cannot be interrupted", "currentVersion": speech_session.version, "status": speech_session.status})
    previous = row_dict(speech_session)
    speech_session.status = "interrupted"
    speech_session.interrupted_at = utc_now()
    speech_session.version += 1
    speech_session.updated_at = utc_now()
    session.add(speech_session)
    record_event(session, auth, action="speech_session_interrupted", entity_type="speech_session", entity_ref=session_ref, previous_state=previous, new_state=row_dict(speech_session), reason=payload.reason, patient_ref=speech_session.patient_ref, episode_ref=speech_session.episode_ref)
    session.commit()
    session.refresh(speech_session)
    return {"session": row_dict(speech_session)}


@router.post("/speech/sessions/{session_ref}/resume")
def resume_speech_session(
    session_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    speech_session = session.exec(select(SpeechSessionV28).where(SpeechSessionV28.session_ref == session_ref)).first()
    if not speech_session:
        raise HTTPException(status_code=404, detail="speech session not found")
    require_site_access(session, auth, speech_session.site_ref)
    if speech_session.version != payload.expectedVersion or speech_session.status != "interrupted":
        raise HTTPException(status_code=409, detail={"message": "session cannot be resumed", "currentVersion": speech_session.version, "status": speech_session.status})
    previous = row_dict(speech_session)
    speech_session.status = "active"
    speech_session.resumed_at = utc_now()
    speech_session.version += 1
    speech_session.updated_at = utc_now()
    session.add(speech_session)
    record_event(session, auth, action="speech_session_resumed", entity_type="speech_session", entity_ref=session_ref, previous_state=previous, new_state=row_dict(speech_session), reason=payload.reason, patient_ref=speech_session.patient_ref, episode_ref=speech_session.episode_ref, risk="green")
    session.commit()
    session.refresh(speech_session)
    return {"session": row_dict(speech_session)}


@router.post("/speech/sessions/{session_ref}/complete")
def complete_speech_session(
    session_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    speech_session = session.exec(select(SpeechSessionV28).where(SpeechSessionV28.session_ref == session_ref)).first()
    if not speech_session:
        raise HTTPException(status_code=404, detail="speech session not found")
    require_site_access(session, auth, speech_session.site_ref)
    if speech_session.version != payload.expectedVersion or speech_session.status not in {"active", "interrupted"}:
        raise HTTPException(status_code=409, detail={"message": "session cannot be completed", "currentVersion": speech_session.version, "status": speech_session.status})
    if not speech_session.transcript_text.strip():
        raise HTTPException(status_code=422, detail="a final transcript segment is required")
    segments = session.exec(select(SpeechSegmentV28).where(
        SpeechSegmentV28.session_ref == session_ref,
        SpeechSegmentV28.is_final == True,  # noqa: E712
    ).order_by(SpeechSegmentV28.sequence)).all()
    confidence_values = [item.confidence for item in segments if item.confidence is not None]
    low = [item.sequence for item in segments if item.confidence is not None and item.confidence < 0.75]
    previous = row_dict(speech_session)
    speech_session.status = "ready_for_review"
    speech_session.completed_at = utc_now()
    speech_session.quality_summary = {
        "averageConfidence": round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None,
        "lowConfidenceSequences": low,
        "wordTimestampSegments": len([item for item in segments if item.words]),
        "speakerLabels": sorted({item.speaker_label for item in segments if item.speaker_label}),
    }
    speech_session.version += 1
    speech_session.updated_at = utc_now()
    session.add(speech_session)
    session.commit()
    capture_result = create_capture(CaptureCreate(
        episodeRef=speech_session.episode_ref,
        captureMode=speech_session.capture_mode,
        sourceType="speech_session_v28",
        transcript=speech_session.transcript_text,
        language=speech_session.language,
        noticeVersion=speech_session.notice_version,
        noticeAcknowledged=True,
        rawAudioRetained=False,
    ), session, auth)
    speech_session.linked_capture_ref = capture_result["capture"]["capture_ref"]
    session.add(speech_session)
    record_event(session, auth, action="speech_session_completed", entity_type="speech_session", entity_ref=session_ref, previous_state=previous, new_state={"session": row_dict(speech_session), "captureRef": speech_session.linked_capture_ref}, reason=payload.reason, patient_ref=speech_session.patient_ref, episode_ref=speech_session.episode_ref, risk="green")
    session.commit()
    session.refresh(speech_session)
    return {
        "session": row_dict(speech_session),
        "capture": capture_result["capture"],
        "draft": capture_result["draft"],
        "boundary": "The completed transcript is still a v19 proposed draft and requires explicit human review before a signed record or task is created.",
    }


@router.post("/connectors")
def create_connector(
    payload: ConnectorCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    membership = require_site_access(session, auth, payload.siteRef)
    site = configured_site(session, payload.siteRef)
    if payload.connectorType not in CONNECTOR_TYPES:
        raise HTTPException(status_code=422, detail="unsupported connector type")
    if membership.organisation_ref != payload.organisationRef or site.organisation_ref != payload.organisationRef:
        raise HTTPException(status_code=409, detail="organisation and site context do not match")
    connector = IntegrationConnectorV28(
        connector_ref=new_ref("connector"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        premises_ref=site.premises_ref,
        connector_type=payload.connectorType,
        vendor_name=payload.vendorName.strip(),
        environment=payload.environment,
        endpoint_host=normalised_host(payload.endpointHost),
        secret_env=payload.secretEnv.strip() if payload.secretEnv else None,
        stale_after_seconds=payload.staleAfterSeconds,
        configuration=payload.configuration,
        created_by_subject=auth.subject,
        updated_by_subject=auth.subject,
    )
    session.add(connector)
    session.flush()
    record_event(session, auth, action="connector_created", entity_type="integration_connector", entity_ref=connector.connector_ref, new_state=row_dict(connector), reason="Connector registered disabled and without write authority")
    session.commit()
    session.refresh(connector)
    return {"connector": row_dict(connector)}


@router.post("/connectors/{connector_ref}/test")
def test_connector(
    connector_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == connector_ref)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    require_site_access(session, auth, connector.site_ref)
    if connector.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale connector", "currentVersion": connector.version})
    previous = row_dict(connector)
    failures = []
    if not connector.endpoint_host:
        failures.append("endpoint host missing")
    if connector.secret_env and not os.getenv(connector.secret_env, ""):
        failures.append(f"secret environment variable {connector.secret_env} is not loaded")
    if connector.environment == "production" and connector.endpoint_host in {"localhost", "127.0.0.1"}:
        failures.append("production connector cannot target a local host")
    connector.last_test_status = "failed" if failures else "passed"
    connector.last_test_detail = "; ".join(failures) if failures else "Configuration, secret presence and endpoint policy checks passed. No external write was attempted."
    connector.last_test_at = utc_now()
    connector.status = "test_failed" if failures else "tested"
    connector.version += 1
    connector.updated_by_subject = auth.subject
    connector.updated_at = utc_now()
    session.add(connector)
    record_event(session, auth, action="connector_tested", entity_type="integration_connector", entity_ref=connector_ref, previous_state=previous, new_state=row_dict(connector), reason=payload.reason, risk="red" if failures else "green")
    session.commit()
    session.refresh(connector)
    return {"connector": row_dict(connector), "passed": not failures, "failures": failures}


@router.post("/connectors/{connector_ref}/promotions")
def request_connector_promotion(
    connector_ref: str,
    payload: PromotionRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == connector_ref)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    require_site_access(session, auth, connector.site_ref)
    if connector.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale connector", "currentVersion": connector.version})
    if payload.requestedMode not in PROMOTABLE_MODES:
        raise HTTPException(status_code=409, detail="v28 permits shadow or read-only promotion only; external write-back requires a later separately governed release")
    if connector.last_test_status != "passed":
        raise HTTPException(status_code=409, detail="connector must pass testing before promotion")
    promotion = IntegrationPromotionV28(
        promotion_ref=new_ref("connector-promotion"),
        connector_ref=connector_ref,
        requested_mode=payload.requestedMode,
        reason=payload.reason,
        evidence_refs=payload.evidenceRefs,
        requested_by_subject=auth.subject,
        requested_by_name=auth.actor_name,
    )
    session.add(promotion)
    session.flush()
    connector.status = "promotion_pending"
    connector.version += 1
    connector.updated_by_subject = auth.subject
    connector.updated_at = utc_now()
    session.add(connector)
    record_event(session, auth, action="connector_promotion_requested", entity_type="integration_promotion", entity_ref=promotion.promotion_ref, new_state={"promotion": row_dict(promotion), "connector": row_dict(connector)}, reason=payload.reason)
    session.commit()
    session.refresh(promotion)
    session.refresh(connector)
    return {"promotion": row_dict(promotion), "connector": row_dict(connector)}


@router.post("/promotions/{promotion_ref}/approve")
def approve_connector_promotion(
    promotion_ref: str,
    payload: PromotionDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    promotion = session.exec(select(IntegrationPromotionV28).where(IntegrationPromotionV28.promotion_ref == promotion_ref)).first()
    if not promotion:
        raise HTTPException(status_code=404, detail="promotion not found")
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == promotion.connector_ref)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    require_site_access(session, auth, connector.site_ref)
    if promotion.version != payload.expectedVersion or promotion.status != "requested":
        raise HTTPException(status_code=409, detail={"message": "promotion cannot be approved", "currentVersion": promotion.version, "status": promotion.status})
    if promotion.requested_by_subject == auth.subject:
        raise HTTPException(status_code=409, detail="connector promotion requires an independent second approver")
    if promotion.requested_mode not in PROMOTABLE_MODES:
        raise HTTPException(status_code=409, detail="external write promotion is not supported in v28")
    previous = {"promotion": row_dict(promotion), "connector": row_dict(connector)}
    promotion.status = "approved"
    promotion.approved_by_subject = auth.subject
    promotion.approved_by_name = auth.actor_name
    promotion.approved_at = utc_now()
    promotion.version += 1
    connector.mode = promotion.requested_mode
    connector.status = "active"
    connector.version += 1
    connector.updated_by_subject = auth.subject
    connector.updated_at = utc_now()
    session.add(promotion)
    session.add(connector)
    record_event(session, auth, action="connector_promotion_approved", entity_type="integration_promotion", entity_ref=promotion_ref, previous_state=previous, new_state={"promotion": row_dict(promotion), "connector": row_dict(connector)}, reason=payload.reason, risk="green")
    session.commit()
    session.refresh(promotion)
    session.refresh(connector)
    return {"promotion": row_dict(promotion), "connector": row_dict(connector)}


@router.post("/connectors/{connector_ref}/events")
def ingest_integration_event(
    connector_ref: str,
    payload: IntegrationEventIngest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == connector_ref)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    require_site_access(session, auth, connector.site_ref)
    if connector.status != "active" or connector.mode not in PROMOTABLE_MODES:
        raise HTTPException(status_code=409, detail="connector must be independently approved in shadow or read-only mode")
    existing = session.exec(select(IntegrationEventV28).where(
        IntegrationEventV28.connector_ref == connector_ref,
        IntegrationEventV28.external_event_id == payload.externalEventId,
    )).first()
    payload_hash = digest(payload.model_dump(mode="json"))
    if existing:
        if existing.payload_hash == payload_hash:
            return {"event": row_dict(existing), "idempotent": True}
        raise HTTPException(status_code=409, detail="external event id already exists with different content")
    episode = None
    if payload.episodeRef:
        episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == payload.episodeRef)).first()
    patient_ref = payload.patientRef or (episode.patient_ref if episode else None)
    needs_reconciliation = not patient_ref or (payload.episodeRef and not episode)
    event = IntegrationEventV28(
        event_ref=new_ref("integration-event"),
        connector_ref=connector_ref,
        external_event_id=payload.externalEventId,
        event_type=payload.eventType,
        status="reconciliation_required" if needs_reconciliation else "processed",
        patient_ref=patient_ref,
        episode_ref=episode.episode_ref if episode else None,
        payload_hash=payload_hash,
        payload_summary=payload.payloadSummary,
        occurred_at=payload.occurredAt,
        processed_at=None if needs_reconciliation else utc_now(),
    )
    session.add(event)
    session.flush()
    reconciliation = None
    if needs_reconciliation:
        reconciliation = ReconciliationItemV28(
            item_ref=new_ref("reconciliation"),
            connector_ref=connector_ref,
            event_ref=event.event_ref,
            entity_type="patient_episode",
            external_ref=payload.episodeRef or payload.patientRef or payload.externalEventId,
            reason="Inbound event could not be bound to a verified canonical patient episode.",
            severity="red" if payload.eventType in {"critical_result", "medication", "patient_update"} else "amber",
        )
        session.add(reconciliation)
        session.flush()
    connector.last_event_at = utc_now()
    if not needs_reconciliation:
        connector.last_success_at = utc_now()
    connector.updated_at = utc_now()
    session.add(connector)
    event.evidence_ref = record_event(session, auth, action="integration_event_received", entity_type="integration_event", entity_ref=event.event_ref, new_state={"event": row_dict(event), "reconciliation": row_dict(reconciliation) if reconciliation else None}, reason="Inbound event recorded without external write-back", patient_ref=patient_ref, episode_ref=event.episode_ref, risk="red" if reconciliation and reconciliation.severity == "red" else "amber")
    session.add(event)
    session.commit()
    session.refresh(event)
    return {"event": row_dict(event), "reconciliation": row_dict(reconciliation) if reconciliation else None, "idempotent": False}


@router.post("/reconciliation/{item_ref}/resolve")
def resolve_reconciliation(
    item_ref: str,
    payload: ReconciliationResolve,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    item = session.exec(select(ReconciliationItemV28).where(ReconciliationItemV28.item_ref == item_ref)).first()
    if not item:
        raise HTTPException(status_code=404, detail="reconciliation item not found")
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == item.connector_ref)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    require_site_access(session, auth, connector.site_ref)
    if item.version != payload.expectedVersion or item.status != "open":
        raise HTTPException(status_code=409, detail={"message": "reconciliation item cannot be resolved", "currentVersion": item.version, "status": item.status})
    event = session.exec(select(IntegrationEventV28).where(IntegrationEventV28.event_ref == item.event_ref)).first()
    previous = {"item": row_dict(item), "event": row_dict(event) if event else None}
    item.status = "resolved"
    item.resolution = payload.resolution
    item.resolved_ref = payload.resolvedRef
    item.resolved_by_subject = auth.subject
    item.resolved_by_name = auth.actor_name
    item.resolved_at = utc_now()
    item.version += 1
    item.updated_at = utc_now()
    session.add(item)
    if event:
        if payload.resolvedRef and payload.resolvedRef.startswith("EP-"):
            episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == payload.resolvedRef)).first()
            if not episode or not episode.patient_ref:
                raise HTTPException(status_code=409, detail="resolved episode reference is not canonical")
            event.episode_ref = episode.episode_ref
            event.patient_ref = episode.patient_ref
        elif payload.resolvedRef:
            event.patient_ref = payload.resolvedRef
        event.status = "processed"
        event.processed_at = utc_now()
        event.failure_code = None
        event.failure_detail = None
        session.add(event)
    record_event(session, auth, action="reconciliation_resolved", entity_type="reconciliation_item", entity_ref=item_ref, previous_state=previous, new_state={"item": row_dict(item), "event": row_dict(event) if event else None}, reason=payload.resolution, patient_ref=event.patient_ref if event else None, episode_ref=event.episode_ref if event else None, risk="green")
    session.commit()
    session.refresh(item)
    return {"item": row_dict(item), "event": row_dict(event) if event else None}


@router.post("/events/{event_ref}/replay")
def replay_integration_event(
    event_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    original = session.exec(select(IntegrationEventV28).where(IntegrationEventV28.event_ref == event_ref)).first()
    if not original:
        raise HTTPException(status_code=404, detail="integration event not found")
    connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == original.connector_ref)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="connector not found")
    require_site_access(session, auth, connector.site_ref)
    if connector.status != "active" or connector.mode not in PROMOTABLE_MODES:
        raise HTTPException(status_code=409, detail="connector is not active in shadow/read-only mode")
    replay = IntegrationEventV28(
        event_ref=new_ref("integration-event"),
        connector_ref=original.connector_ref,
        external_event_id=f"{original.external_event_id}:replay:{uuid4().hex}",
        event_type=original.event_type,
        direction="replay",
        status="processed" if original.patient_ref else "reconciliation_required",
        patient_ref=original.patient_ref,
        episode_ref=original.episode_ref,
        payload_hash=original.payload_hash,
        payload_summary=original.payload_summary,
        occurred_at=original.occurred_at,
        processed_at=utc_now() if original.patient_ref else None,
        retry_count=original.retry_count + 1,
        replay_of_event_ref=original.event_ref,
    )
    session.add(replay)
    session.flush()
    replay.evidence_ref = record_event(session, auth, action="integration_event_replayed", entity_type="integration_event", entity_ref=replay.event_ref, new_state=row_dict(replay), reason=payload.reason, patient_ref=replay.patient_ref, episode_ref=replay.episode_ref)
    session.add(replay)
    session.commit()
    session.refresh(replay)
    return {"event": row_dict(replay), "boundary": "Replay reprocesses LucyWorks' recorded shadow/read-only event only; it does not write to the external system."}
