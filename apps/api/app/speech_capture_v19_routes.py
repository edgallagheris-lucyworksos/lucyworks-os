from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, SENIOR_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.detailed_hospital_models import ClinicalNoteV8
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState
from app.medication_foundation_v18_models import MedicationProtocolV18, VeterinaryProductV18
from app.models import WorkItem
from app.speech_capture_v19_models import SpeechCaptureV19, SpeechDraftV19, SpeechPhrasePackV19

router = APIRouter(prefix="/api/v19/speech", tags=["veterinary-speech-structured-capture-v19"])
CAPTURE_ROLES = ("admin", "ops_manager", "clinician", "clinical_director", "senior_clinician", "supervisor", "nurse")
CAPTURE_MODES = {"clinical_dictation", "consultation_transcription", "voice_command", "typed_predictive"}
SECTION_KEYS = ("presenting_complaint", "history", "examination", "assessment", "plan", "owner_discussion")
BASE_TERMS = (
    "presenting complaint", "history", "examination", "assessment", "plan", "owner concern",
    "mucous membranes", "capillary refill time", "heart rate", "respiratory rate", "temperature",
    "body condition score", "pain score", "neurological examination", "thoracic auscultation",
    "abdominal palpation", "anaesthesia", "recovery", "discharge", "referring veterinary surgeon",
)


class CaptureCreate(BaseModel):
    episodeRef: str
    captureMode: str = "clinical_dictation"
    sourceType: str = "typed"
    transcript: str = PydanticField(min_length=1, max_length=50000)
    language: str = "en-GB"
    noticeVersion: str = "v19-default"
    noticeAcknowledged: bool = False
    rawAudioRetained: bool = False


class CaptureConfirm(BaseModel):
    expectedCaptureVersion: int
    expectedDraftVersion: int
    finalSections: dict[str, str] = PydanticField(default_factory=dict)
    acceptedSuggestionIds: list[str] = PydanticField(default_factory=list)
    rejectedSuggestionIds: list[str] = PydanticField(default_factory=list)
    acceptedTaskIds: list[str] = PydanticField(default_factory=list)
    createClinicalNote: bool = True
    noteType: str = "consultation"
    noteTitle: str = "Reviewed speech capture"
    reason: str


class CaptureReject(BaseModel):
    expectedCaptureVersion: int
    expectedDraftVersion: int
    reason: str


class PhrasePackCreate(BaseModel):
    organisationRef: str = "reference"
    name: str
    terms: list[str] = PydanticField(default_factory=list)
    replacements: dict[str, str] = PydanticField(default_factory=dict)


class VersionedReason(BaseModel):
    expectedVersion: int
    reason: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def record_event(
    session: Session,
    auth: AuthContext,
    *,
    action: str,
    entity_type: str,
    entity_ref: str,
    episode_ref: str,
    patient_ref: str,
    previous: Any,
    current: Any,
    reason: str,
    risk: str = "amber",
) -> str:
    event, _ = create_evidence_event(
        session,
        event_type=f"v19_speech_{action}",
        action=action,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        patient_case_id=patient_ref,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        justification="Governed veterinary speech capture and human confirmation",
        evidence_links=[{"type": entity_type, "id": entity_ref}],
        compliance_domain="clinical_records",
        risk_level=risk,
        source_module="speech-capture-v19",
        source_record_ref=entity_ref,
        correlation_id=episode_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v19:speech:{entity_type}:{entity_ref}:{action}:{current.get('version', 'event') if isinstance(current, dict) else 'event'}",
    )
    return event.event_ref


def require_episode(session: Session, episode_ref: str) -> CanonicalEpisodeState:
    episode = session.exec(
        select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    if not episode.patient_ref:
        raise HTTPException(status_code=409, detail="canonical episode is not linked to a patient")
    return episode


def approved_phrase_packs(session: Session) -> list[SpeechPhrasePackV19]:
    return session.exec(
        select(SpeechPhrasePackV19).where(SpeechPhrasePackV19.status == "approved")
    ).all()


def apply_phrase_packs(transcript: str, packs: list[SpeechPhrasePackV19]) -> str:
    value = transcript
    for pack in packs:
        for source, replacement in pack.replacements.items():
            value = re.sub(rf"\b{re.escape(source)}\b", replacement, value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def sentences(transcript: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", transcript) if part.strip()]


def section_for(sentence: str) -> str:
    lower = sentence.lower()
    if re.match(r"^(presenting complaint|complaint)\s*[:\-]", lower):
        return "presenting_complaint"
    if re.match(r"^(history|hx)\s*[:\-]", lower) or any(token in lower for token in ("owner reports", "presented with", "since yesterday", "since this morning")):
        return "history"
    if re.match(r"^(examination|exam|o/e)\s*[:\-]", lower) or any(token in lower for token in ("on examination", "heart rate", "respiratory rate", "temperature", "mucous membrane", "capillary refill")):
        return "examination"
    if re.match(r"^(assessment|impression|diagnosis)\s*[:\-]", lower) or any(token in lower for token in ("suspect", "most likely", "differential", "consistent with")):
        return "assessment"
    if re.match(r"^(plan|recommendation)\s*[:\-]", lower) or any(token in lower for token in ("plan to", "recommend", "arrange", "will recheck", "will repeat")):
        return "plan"
    if any(token in lower for token in ("owner advised", "owner understands", "discussed with owner", "consent", "estimate")):
        return "owner_discussion"
    return "history"


def strip_section_label(value: str) -> str:
    return re.sub(r"^(presenting complaint|complaint|history|hx|examination|exam|o/e|assessment|impression|diagnosis|plan|recommendation)\s*[:\-]\s*", "", value, flags=re.IGNORECASE).strip()


def make_suggestion(kind: str, value: Any, source: str, confidence: float = 0.9, **extra: Any) -> dict[str, Any]:
    return {
        "id": new_ref("speech-suggestion"),
        "type": kind,
        "value": value,
        "sourceText": source,
        "confidence": confidence,
        **extra,
    }


def extract_negations(transcript: str) -> list[dict[str, Any]]:
    rows = []
    pattern = re.compile(r"\b(no|not|without|denies|negative for)\s+([^.;,]{1,90})", re.IGNORECASE)
    for match in pattern.finditer(transcript):
        rows.append(make_suggestion("negation", match.group(0).strip(), match.group(0).strip(), 0.98))
    return rows


def extract_uncertainties(transcript: str) -> list[dict[str, Any]]:
    rows = []
    pattern = re.compile(r"\b(possible|possibly|maybe|may be|suspect|suspected|likely|appears|unclear|uncertain|cannot exclude|probably)\b[^.;,]{0,90}", re.IGNORECASE)
    for match in pattern.finditer(transcript):
        rows.append(make_suggestion("uncertainty", match.group(0).strip(), match.group(0).strip(), 0.7))
    return rows


def extract_observations(transcript: str) -> list[dict[str, Any]]:
    patterns = (
        ("temperature_c", r"\b(?:temperature|temp)\s*(?:is|was|of|:)??\s*(\d{2}(?:\.\d+)?)\s*(?:°?c|celsius)?\b", "°C"),
        ("heart_rate_bpm", r"\b(?:heart rate|hr)\s*(?:is|was|of|:)??\s*(\d{2,3})\s*(?:bpm)?\b", "bpm"),
        ("respiratory_rate_bpm", r"\b(?:respiratory rate|rr)\s*(?:is|was|of|:)??\s*(\d{1,3})\s*(?:bpm|breaths per minute)?\b", "breaths/min"),
        ("weight_kg", r"\b(?:weight|weighs|weighed)\s*(?:is|was|of|:)??\s*(\d+(?:\.\d+)?)\s*kg\b", "kg"),
        ("pain_score", r"\b(?:pain score)\s*(?:is|was|of|:)??\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?\b", "/10"),
    )
    rows: list[dict[str, Any]] = []
    for kind, pattern, unit in patterns:
        for match in re.finditer(pattern, transcript, re.IGNORECASE):
            rows.append(make_suggestion("observation", {"kind": kind, "value": float(match.group(1)), "unit": unit}, match.group(0), 0.96))
    return rows


def medicine_catalogue(session: Session) -> list[dict[str, Any]]:
    products = session.exec(
        select(VeterinaryProductV18).where(VeterinaryProductV18.authorisation_status == "current")
    ).all()
    protocols = session.exec(
        select(MedicationProtocolV18).where(MedicationProtocolV18.status == "approved")
    ).all()
    rows: list[dict[str, Any]] = []
    for product in products:
        terms = [product.product_name, *product.active_substances]
        rows.append({
            "productRef": product.product_ref,
            "productName": product.product_name,
            "terms": sorted({term.strip() for term in terms if term and term.strip()}, key=len, reverse=True),
            "routes": product.routes,
            "concentrationMgPerMl": product.concentration_mg_per_ml,
        })
    for protocol in protocols:
        if any(row["productRef"] == protocol.product_ref for row in rows if protocol.product_ref):
            continue
        rows.append({
            "productRef": protocol.product_ref,
            "productName": protocol.generic_name,
            "terms": [protocol.generic_name],
            "routes": [protocol.route],
            "concentrationMgPerMl": protocol.concentration_override_mg_per_ml,
        })
    return rows


def extract_medications(session: Session, transcript: str) -> list[dict[str, Any]]:
    lower = transcript.lower()
    dose_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(micrograms?/kg|mcg/kg|mg/kg|micrograms?|mcg|mg|ml)\b", re.IGNORECASE)
    route_pattern = re.compile(r"\b(iv|intravenous|im|intramuscular|sc|subcutaneous|po|oral|topical|otic|ophthalmic)\b", re.IGNORECASE)
    frequency_pattern = re.compile(r"\b(q\d+h|once daily|twice daily|three times daily|every \d+ hours?|sid|bid|tid|qid)\b", re.IGNORECASE)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in medicine_catalogue(session):
        matched_term = next((term for term in item["terms"] if term.lower() in lower), None)
        if not matched_term:
            continue
        index = lower.find(matched_term.lower())
        window = transcript[max(0, index - 90): min(len(transcript), index + len(matched_term) + 160)]
        dose = dose_pattern.search(window)
        route = route_pattern.search(window)
        frequency = frequency_pattern.search(window)
        key = f"{item['productRef']}:{dose.group(0).lower() if dose else ''}:{route.group(0).lower() if route else ''}"
        if key in seen:
            continue
        seen.add(key)
        proposal = {
            "productRef": item["productRef"],
            "productName": item["productName"],
            "matchedTerm": matched_term,
            "doseExpression": dose.group(0) if dose else None,
            "routeExpression": route.group(0) if route else None,
            "frequencyExpression": frequency.group(0) if frequency else None,
            "concentrationMgPerMl": item["concentrationMgPerMl"],
            "calculationPerformed": False,
            "boundary": "Proposal only. Medication Foundation v18 must calculate and verify before review or prescribing.",
        }
        rows.append(make_suggestion("medication_proposal", proposal, window.strip(), 0.92 if dose else 0.78))
    return rows


def task_owner(sentence: str) -> tuple[str, str, str]:
    lower = sentence.lower()
    if any(token in lower for token in ("owner", "client", "call", "contact", "update")):
        return "admin", "Owner Comms", "amber"
    if any(token in lower for token in ("medication", "dispense", "pharmacy", "stock")):
        return "nurse", "Pharmacy", "amber"
    if any(token in lower for token in ("mri", "ct", "radiograph", "ultrasound", "imaging")):
        return "clinician", "Imaging", "amber"
    if any(token in lower for token in ("urgent", "immediately", "stat", "emergency")):
        return "clinician", "Triage / Consult", "red"
    return "clinician", "Triage / Consult", "amber"


def extract_tasks(transcript: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sentence in sentences(transcript):
        lower = sentence.lower()
        if not any(token in lower for token in ("need to", "please", "arrange", "book", "call", "contact", "update", "repeat", "recheck", "review", "monitor", "handover", "send", "schedule")):
            continue
        owner, section, urgency = task_owner(sentence)
        due_minutes = 15 if urgency == "red" else 60 if "today" in lower or "urgent" in lower else 240
        rows.append(make_suggestion(
            "task",
            {
                "title": sentence[:120],
                "description": sentence,
                "ownerRole": owner,
                "sectionName": section,
                "urgency": urgency,
                "dueAt": (utc_now() + timedelta(minutes=due_minutes)).isoformat(),
            },
            sentence,
            0.82,
        ))
    return rows


def extract_sections(transcript: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {key: [] for key in SECTION_KEYS}
    for sentence in sentences(transcript):
        buckets[section_for(sentence)].append(strip_section_label(sentence))
    return {key: " ".join(values).strip() for key, values in buckets.items()}


def extract_draft(session: Session, transcript: str) -> dict[str, Any]:
    sections = extract_sections(transcript)
    negations = extract_negations(transcript)
    uncertainties = extract_uncertainties(transcript)
    observations = extract_observations(transcript)
    medications = extract_medications(session, transcript)
    tasks = extract_tasks(transcript)
    suggestions: list[dict[str, Any]] = []
    for key, value in sections.items():
        if value:
            suggestions.append(make_suggestion("section", {"section": key, "text": value}, value, 0.88))
    suggestions.extend(observations)
    suggestions.extend(medications)
    suggestions.extend(tasks)
    return {
        "sections": sections,
        "suggestions": suggestions,
        "negations": negations,
        "uncertainties": uncertainties,
        "observations": observations,
        "medications": medications,
        "tasks": tasks,
    }


def final_note_text(sections: dict[str, str]) -> str:
    labels = {
        "presenting_complaint": "Presenting complaint",
        "history": "History",
        "examination": "Examination",
        "assessment": "Assessment",
        "plan": "Plan",
        "owner_discussion": "Owner discussion",
    }
    parts = [f"{labels[key]}\n{sections[key].strip()}" for key in SECTION_KEYS if sections.get(key, "").strip()]
    return "\n\n".join(parts)


@router.post("/captures")
def create_capture(
    payload: CaptureCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    if payload.captureMode not in CAPTURE_MODES:
        raise HTTPException(status_code=422, detail="unsupported capture mode")
    if not payload.noticeAcknowledged:
        raise HTTPException(status_code=409, detail="recording/privacy notice must be acknowledged before capture")
    if payload.rawAudioRetained:
        raise HTTPException(status_code=409, detail="raw-audio retention is disabled in this deployment profile")
    transcript = payload.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="transcript is required")
    episode = require_episode(session, payload.episodeRef)
    normalised = apply_phrase_packs(transcript, approved_phrase_packs(session))
    capture = SpeechCaptureV19(
        capture_ref=new_ref("speech-capture"),
        episode_ref=episode.episode_ref,
        patient_ref=episode.patient_ref or "",
        capture_mode=payload.captureMode,
        source_type=payload.sourceType,
        language=payload.language,
        transcript_text=transcript,
        redacted_transcript_text=normalised if normalised != transcript else None,
        raw_audio_retained=False,
        notice_version=payload.noticeVersion,
        notice_acknowledged=True,
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
        created_by_role=auth.role,
    )
    session.add(capture)
    session.flush()
    extracted = extract_draft(session, normalised)
    draft = SpeechDraftV19(
        draft_ref=new_ref("speech-draft"),
        capture_ref=capture.capture_ref,
        episode_ref=episode.episode_ref,
        patient_ref=episode.patient_ref or "",
        proposed_sections=extracted["sections"],
        suggestions=extracted["suggestions"],
        uncertainties=extracted["uncertainties"],
        negations=extracted["negations"],
        medication_proposals=extracted["medications"],
        observations=extracted["observations"],
        task_proposals=extracted["tasks"],
    )
    session.add(draft)
    session.flush()
    capture.evidence_event_ref = record_event(
        session, auth,
        action="captured",
        entity_type="speech_capture",
        entity_ref=capture.capture_ref,
        episode_ref=capture.episode_ref,
        patient_ref=capture.patient_ref,
        previous=None,
        current={
            "capture": row_dict(capture),
            "draftRef": draft.draft_ref,
            "suggestionCount": len(draft.suggestions),
            "rawAudioRetained": False,
        },
        reason="Transcript captured; proposed structured draft created for human review",
    )
    draft.evidence_event_ref = capture.evidence_event_ref
    session.add(capture)
    session.add(draft)
    session.commit()
    session.refresh(capture)
    session.refresh(draft)
    return {
        "capture": row_dict(capture),
        "draft": row_dict(draft),
        "context": {
            "episodeRef": episode.episode_ref,
            "patientRef": episode.patient_ref,
            "patientName": episode.patient_name,
            "phase": episode.phase,
        },
        "medicationFoundationLink": f"/medications?episode={episode.episode_ref}&speech={draft.draft_ref}",
        "boundary": "Transcript and proposals are not the verified clinical record until an authorised reviewer confirms them.",
    }


@router.get("/captures/{capture_ref}")
def get_capture(
    capture_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    capture = session.exec(select(SpeechCaptureV19).where(SpeechCaptureV19.capture_ref == capture_ref)).first()
    if not capture:
        raise HTTPException(status_code=404, detail="speech capture not found")
    draft = session.exec(select(SpeechDraftV19).where(SpeechDraftV19.capture_ref == capture_ref)).first()
    episode = require_episode(session, capture.episode_ref)
    return {
        "capture": row_dict(capture),
        "draft": row_dict(draft) if draft else None,
        "context": {
            "episodeRef": episode.episode_ref,
            "patientRef": episode.patient_ref,
            "patientName": episode.patient_name,
            "phase": episode.phase,
        },
    }


@router.post("/captures/{capture_ref}/confirm")
def confirm_capture(
    capture_ref: str,
    payload: CaptureConfirm,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    capture_query = select(SpeechCaptureV19).where(SpeechCaptureV19.capture_ref == capture_ref)
    draft_query = select(SpeechDraftV19).where(SpeechDraftV19.capture_ref == capture_ref)
    if session.get_bind().dialect.name == "postgresql":
        capture_query = capture_query.with_for_update()
        draft_query = draft_query.with_for_update()
    capture = session.exec(capture_query).first()
    draft = session.exec(draft_query).first()
    if not capture or not draft:
        raise HTTPException(status_code=404, detail="speech capture or draft not found")
    if capture.version != payload.expectedCaptureVersion or draft.version != payload.expectedDraftVersion:
        raise HTTPException(status_code=409, detail={
            "message": "stale speech review",
            "currentCaptureVersion": capture.version,
            "currentDraftVersion": draft.version,
        })
    if capture.status != "draft" or draft.status != "proposed":
        raise HTTPException(status_code=409, detail="only an unconfirmed proposed draft can be confirmed")
    if payload.createClinicalNote and auth.role not in set(CLINICAL_ROLES):
        raise HTTPException(status_code=403, detail="a verified clinical role must confirm a clinical note")
    unknown_sections = set(payload.finalSections) - set(SECTION_KEYS)
    if unknown_sections:
        raise HTTPException(status_code=422, detail=f"unsupported final sections: {sorted(unknown_sections)}")
    final_sections = {key: payload.finalSections.get(key, "").strip() for key in SECTION_KEYS}
    final_text = final_note_text(final_sections)
    if payload.createClinicalNote and not final_text:
        raise HTTPException(status_code=422, detail="final reviewed clinical note is empty")

    known_ids = {row["id"] for row in draft.suggestions}
    accepted = set(payload.acceptedSuggestionIds)
    rejected = set(payload.rejectedSuggestionIds)
    if accepted & rejected:
        raise HTTPException(status_code=422, detail="a suggestion cannot be both accepted and rejected")
    unknown_ids = (accepted | rejected) - known_ids
    if unknown_ids:
        raise HTTPException(status_code=422, detail={"message": "unknown suggestion ids", "ids": sorted(unknown_ids)})
    task_by_id = {row["id"]: row for row in draft.task_proposals}
    unknown_tasks = set(payload.acceptedTaskIds) - set(task_by_id)
    if unknown_tasks:
        raise HTTPException(status_code=422, detail={"message": "unknown task ids", "ids": sorted(unknown_tasks)})

    previous = {"capture": row_dict(capture), "draft": row_dict(draft)}
    note = None
    if payload.createClinicalNote:
        note = ClinicalNoteV8(
            note_ref=new_ref("clinical-note"),
            patient_ref=capture.patient_ref,
            episode_ref=capture.episode_ref,
            note_type=payload.noteType,
            title=payload.noteTitle.strip() or "Reviewed speech capture",
            body=final_text,
            status="signed",
            author_subject=auth.subject,
            author_name=auth.actor_name,
        )
        session.add(note)
        session.flush()

    work_items: list[WorkItem] = []
    episode = require_episode(session, capture.episode_ref)
    for task_id in payload.acceptedTaskIds:
        proposal = task_by_id[task_id]["value"]
        due_at = datetime.fromisoformat(proposal["dueAt"]) if proposal.get("dueAt") else None
        if due_at and due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        item = WorkItem(
            title=str(proposal.get("title") or "Speech-captured task")[:200],
            input_type="speech_capture_v19",
            source="reviewed_speech",
            category="clinical" if payload.createClinicalNote else "ops",
            description=str(proposal.get("description") or ""),
            urgency=str(proposal.get("urgency") or "amber"),
            owner_role=str(proposal.get("ownerRole") or "clinician"),
            section_name=proposal.get("sectionName"),
            linked_patient_name=episode.patient_name,
            linked_episode_ref=episode.episode_ref,
            status="new",
            due_at=due_at,
        )
        session.add(item)
        session.flush()
        work_items.append(item)

    capture.status = "confirmed"
    capture.reviewed_by_subject = auth.subject
    capture.reviewed_by_name = auth.actor_name
    capture.reviewed_by_role = auth.role
    capture.confirmed_at = utc_now()
    capture.version += 1
    capture.updated_at = utc_now()
    draft.status = "confirmed"
    draft.reviewer_edits = final_sections
    draft.accepted_suggestion_ids = sorted(accepted)
    draft.rejected_suggestion_ids = sorted(rejected)
    draft.final_text = final_text or None
    draft.clinical_note_ref = note.note_ref if note else None
    draft.work_item_ids = [item.id for item in work_items if item.id is not None]
    draft.version += 1
    draft.updated_at = utc_now()
    session.add(capture)
    session.add(draft)
    session.flush()

    current = {
        "capture": row_dict(capture),
        "draft": row_dict(draft),
        "clinicalNoteRef": note.note_ref if note else None,
        "workItemIds": draft.work_item_ids,
    }
    evidence_ref = record_event(
        session, auth,
        action="confirmed",
        entity_type="speech_capture",
        entity_ref=capture.capture_ref,
        episode_ref=capture.episode_ref,
        patient_ref=capture.patient_ref,
        previous=previous,
        current=current,
        reason=payload.reason,
        risk="green",
    )
    capture.evidence_event_ref = evidence_ref
    draft.evidence_event_ref = evidence_ref
    if note:
        note.evidence_event_ref = evidence_ref
        session.add(note)
    session.add(capture)
    session.add(draft)
    session.commit()
    return {
        "capture": row_dict(capture),
        "draft": row_dict(draft),
        "clinicalNote": row_dict(note) if note else None,
        "workItems": [row_dict(item) for item in work_items],
        "evidenceEventRef": evidence_ref,
    }


@router.post("/captures/{capture_ref}/reject")
def reject_capture(
    capture_ref: str,
    payload: CaptureReject,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    capture = session.exec(select(SpeechCaptureV19).where(SpeechCaptureV19.capture_ref == capture_ref)).first()
    draft = session.exec(select(SpeechDraftV19).where(SpeechDraftV19.capture_ref == capture_ref)).first()
    if not capture or not draft:
        raise HTTPException(status_code=404, detail="speech capture or draft not found")
    if capture.version != payload.expectedCaptureVersion or draft.version != payload.expectedDraftVersion:
        raise HTTPException(status_code=409, detail="stale speech review")
    if capture.status != "draft" or draft.status != "proposed":
        raise HTTPException(status_code=409, detail="speech capture is no longer reviewable")
    previous = {"capture": row_dict(capture), "draft": row_dict(draft)}
    capture.status = "rejected"
    capture.reviewed_by_subject = auth.subject
    capture.reviewed_by_name = auth.actor_name
    capture.reviewed_by_role = auth.role
    capture.version += 1
    capture.updated_at = utc_now()
    draft.status = "rejected"
    draft.rejected_suggestion_ids = [row["id"] for row in draft.suggestions]
    draft.version += 1
    draft.updated_at = utc_now()
    session.add(capture)
    session.add(draft)
    session.flush()
    evidence_ref = record_event(
        session, auth,
        action="rejected",
        entity_type="speech_capture",
        entity_ref=capture.capture_ref,
        episode_ref=capture.episode_ref,
        patient_ref=capture.patient_ref,
        previous=previous,
        current={"capture": row_dict(capture), "draft": row_dict(draft)},
        reason=payload.reason,
        risk="amber",
    )
    capture.evidence_event_ref = evidence_ref
    draft.evidence_event_ref = evidence_ref
    session.add(capture)
    session.add(draft)
    session.commit()
    return {"capture": row_dict(capture), "draft": row_dict(draft), "evidenceEventRef": evidence_ref}


@router.get("/terms")
def terminology(
    q: str = Query(min_length=2, max_length=80),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = q.strip().lower()
    results: list[dict[str, Any]] = []
    for term in BASE_TERMS:
        if query in term.lower():
            results.append({"term": term, "type": "veterinary_term", "source": "LucyWorks v19"})
    for pack in approved_phrase_packs(session):
        for term in pack.terms:
            if query in term.lower():
                results.append({"term": term, "type": "organisation_phrase", "source": pack.name})
    for product in session.exec(select(VeterinaryProductV18).where(VeterinaryProductV18.authorisation_status == "current")).all():
        for term in [product.product_name, *product.active_substances]:
            if query in term.lower():
                results.append({"term": term, "type": "medicine", "source": product.source_name, "productRef": product.product_ref})
    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in results:
        key = row["term"].lower()
        if key not in seen:
            seen.add(key)
            deduplicated.append(row)
    return {"query": q, "items": deduplicated[:30]}


@router.get("/phrase-packs")
def list_phrase_packs(
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(SpeechPhrasePackV19).order_by(SpeechPhrasePackV19.created_at.desc())).all()
    return {"items": [row_dict(row) for row in rows]}


@router.post("/phrase-packs")
def create_phrase_pack(
    payload: PhrasePackCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="phrase-pack name is required")
    row = SpeechPhrasePackV19(
        phrase_pack_ref=new_ref("speech-phrase-pack"),
        organisation_ref=payload.organisationRef,
        name=name,
        terms=sorted({term.strip() for term in payload.terms if term.strip()}),
        replacements={key.strip(): value.strip() for key, value in payload.replacements.items() if key.strip() and value.strip()},
        created_by_subject=auth.subject,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth,
        action="phrase_pack_created",
        entity_type="speech_phrase_pack",
        entity_ref=row.phrase_pack_ref,
        episode_ref="organisation",
        patient_ref="none",
        previous=None,
        current=row_dict(row),
        reason="Organisation veterinary phrase pack created for governed review",
        risk="amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"phrasePack": row_dict(row)}


@router.patch("/phrase-packs/{phrase_pack_ref}/approve")
def approve_phrase_pack(
    phrase_pack_ref: str,
    payload: VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    query = select(SpeechPhrasePackV19).where(SpeechPhrasePackV19.phrase_pack_ref == phrase_pack_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="phrase pack not found")
    if row.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale phrase pack", "currentVersion": row.version})
    previous = row_dict(row)
    row.status = "approved"
    row.approved_by_subject = auth.subject
    row.approved_at = utc_now()
    row.version += 1
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth,
        action="phrase_pack_approved",
        entity_type="speech_phrase_pack",
        entity_ref=row.phrase_pack_ref,
        episode_ref="organisation",
        patient_ref="none",
        previous=previous,
        current=row_dict(row),
        reason=payload.reason,
        risk="green",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"phrasePack": row_dict(row)}
