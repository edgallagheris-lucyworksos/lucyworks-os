from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.evidence_event_models import EvidenceEvent
from app.patient_care_models import PatientCase, PatientWorkflowEvent, ReferralEpisode
from app.schedule_state_models import ScheduleStateBlock

router = APIRouter(prefix="/api/patient-care", tags=["patient-care"])

STAGE_ORDER = ["intake", "admin", "procedure", "recovery", "closure"]
STAGE_TERMS = {
    "intake": {"arrival", "triage", "check-in", "intake"},
    "admin": {"consent", "estimate", "insurance", "payment", "admin"},
    "procedure": {"mri", "ct", "procedure", "surgery", "theatre", "consult", "workup"},
    "recovery": {"recovery", "handover", "ward", "nursing"},
    "closure": {"owner", "client", "referring vet", "report", "discharge", "close"},
}


class EpisodeStatePatch(BaseModel):
    stage: str | None = None
    ownerRole: str | None = None
    ownerName: str | None = None
    currentLocation: str | None = None
    nextAction: str | None = None
    blocker: str | None = None
    status: str | None = None
    consentStatus: str | None = None
    estimateStatus: str | None = None
    insuranceStatus: str | None = None
    pharmacyReady: bool | None = None
    ownerUpdated: bool | None = None
    referringVetReportSent: bool | None = None
    dischargeClear: bool | None = None
    actor: str = "frontend"
    note: str | None = None


class WorkflowEventCreate(BaseModel):
    eventType: str = "manual"
    action: str
    actor: str = "frontend"
    note: str | None = None
    sourceBlockId: str | None = None
    atTime: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_ref() -> str:
    return f"patient-care-evidence-{int(_now().timestamp() * 1000)}"


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "case"


def _text(row: ScheduleStateBlock) -> str:
    return f"{row.lane or ''} {row.what or ''} {row.how or ''} {row.where or ''} {row.next or ''} {row.blocker or ''}".lower()


def _case_key(row: ScheduleStateBlock) -> str:
    return row.episode_ref or row.subject or row.id


def _patient_name(rows: list[ScheduleStateBlock], fallback: str) -> str:
    for row in rows:
        if row.subject:
            return row.subject
    return fallback


def _stage_for(rows: list[ScheduleStateBlock]) -> str:
    open_rows = [row for row in rows if row.status != "green" or (row.blocker and row.blocker != "none")]
    source = open_rows or rows
    text = " ".join(_text(row) for row in source)
    for stage in STAGE_ORDER:
        if any(term in text for term in STAGE_TERMS[stage]):
            return stage
    return "intake"


def _owner_role(rows: list[ScheduleStateBlock]) -> str:
    for row in rows:
        if row.assigned_role:
            return row.assigned_role
    for row in rows:
        if row.who:
            return row.who
    return "unassigned"


def _owner_name(rows: list[ScheduleStateBlock]) -> str | None:
    for row in rows:
        if row.assigned_staff_name:
            return row.assigned_staff_name
    return None


def _location(rows: list[ScheduleStateBlock]) -> str | None:
    for row in rows:
        if row.where:
            return row.where
    return None


def _blocker(rows: list[ScheduleStateBlock]) -> str:
    for row in rows:
        if row.blocker and row.blocker != "none":
            return row.blocker
    return "none"


def _next_action(rows: list[ScheduleStateBlock]) -> str:
    blocked = next((row for row in rows if row.blocker and row.blocker != "none"), None)
    if blocked:
        return f"{blocked.time} · clear blocker: {blocked.blocker}"
    open_row = next((row for row in rows if row.status != "green"), None)
    if open_row:
        return f"{open_row.time} · {open_row.next}"
    return rows[-1].next if rows else "no next action"


def _first_status(rows: list[ScheduleStateBlock], attr: str) -> Any:
    for row in rows:
        value = getattr(row, attr)
        if value is not None:
            return value
    return None


def _risk_level(rows: list[ScheduleStateBlock]) -> str:
    if any(row.status == "red" or (row.blocker and row.blocker != "none") for row in rows):
        return "red"
    if any(row.status == "amber" for row in rows):
        return "amber"
    return "green"


def _fill_if_missing(row: ReferralEpisode, attr: str, value: Any) -> None:
    if getattr(row, attr) is None and value is not None:
        setattr(row, attr, value)


def _has_manual_episode_events(session: Session, episode_id: str) -> bool:
    return session.exec(select(PatientWorkflowEvent).where(PatientWorkflowEvent.episode_id == episode_id)).first() is not None


def _case_dict(row: PatientCase) -> dict[str, Any]:
    return {
        "id": row.id,
        "patientName": row.patient_name,
        "species": row.species,
        "breed": row.breed,
        "ownerName": row.owner_name,
        "referralReason": row.referral_reason,
        "riskLevel": row.risk_level,
        "status": row.status,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _episode_dict(row: ReferralEpisode) -> dict[str, Any]:
    return {
        "id": row.id,
        "patientCaseId": row.patient_case_id,
        "episodeRef": row.episode_ref,
        "stage": row.stage,
        "ownerRole": row.owner_role,
        "ownerName": row.owner_name,
        "currentLocation": row.current_location,
        "nextAction": row.next_action,
        "blocker": row.blocker,
        "status": row.status,
        "consentStatus": row.consent_status,
        "estimateStatus": row.estimate_status,
        "insuranceStatus": row.insurance_status,
        "pharmacyReady": row.pharmacy_ready,
        "ownerUpdated": row.owner_updated,
        "referringVetReportSent": row.referring_vet_report_sent,
        "dischargeClear": row.discharge_clear,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _event_dict(row: PatientWorkflowEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "episodeId": row.episode_id,
        "patientCaseId": row.patient_case_id,
        "eventType": row.event_type,
        "action": row.action,
        "actor": row.actor,
        "note": row.note,
        "sourceBlockId": row.source_block_id,
        "atTime": row.at_time,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _record_evidence(session: Session, episode: ReferralEpisode, action: str, actor: str, previous: dict[str, Any] | None, new: dict[str, Any] | None, note: str | None = None) -> None:
    session.add(EvidenceEvent(
        event_ref=_event_ref(),
        event_type="patient_workflow_state",
        patient_case_id=episode.patient_case_id,
        referral_episode_id=episode.id,
        actor_name=actor,
        actor_role="workflow_user",
        action=action,
        previous_state_json=_json(previous),
        new_state_json=_json(new),
        reason=note,
        compliance_domain="clinical_governance",
        risk_level="red" if episode.blocker != "none" or episode.status == "blocked" else "amber",
        source_module="patient-care",
    ))


def _sync_from_blocks(session: Session) -> None:
    rows = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    grouped: dict[str, list[ScheduleStateBlock]] = defaultdict(list)
    for row in rows:
        if row.lane == "breaks":
            continue
        grouped[_case_key(row)].append(row)

    for key, blocks in grouped.items():
        if not blocks:
            continue
        blocks = sorted(blocks, key=lambda item: (item.time, item.lane, item.what))
        slug = _slug(key)
        case_id = f"case-{slug}"
        episode_id = f"episode-{slug}"
        patient = session.get(PatientCase, case_id)
        if not patient:
            patient = PatientCase(id=case_id, patient_name=_patient_name(blocks, key))
        patient.patient_name = _patient_name(blocks, key)
        patient.referral_reason = blocks[0].what
        patient.risk_level = _risk_level(blocks)
        patient.status = "active"
        patient.updated_at = _now()
        session.add(patient)

        episode = session.get(ReferralEpisode, episode_id)
        is_new_episode = episode is None
        if not episode:
            episode = ReferralEpisode(id=episode_id, patient_case_id=case_id, episode_ref=key)
        has_manual_state = False if is_new_episode else _has_manual_episode_events(session, episode_id)
        episode.patient_case_id = case_id
        episode.episode_ref = key

        if is_new_episode or not has_manual_state:
            episode.stage = _stage_for(blocks)
            episode.owner_role = _owner_role(blocks)
            episode.owner_name = _owner_name(blocks)
            episode.current_location = _location(blocks)
            episode.next_action = _next_action(blocks)
            episode.blocker = _blocker(blocks)
            episode.status = "blocked" if episode.blocker != "none" else "active"
        else:
            episode.owner_role = episode.owner_role or _owner_role(blocks)
            episode.owner_name = episode.owner_name or _owner_name(blocks)
            episode.current_location = episode.current_location or _location(blocks)

        _fill_if_missing(episode, "consent_status", _first_status(blocks, "consent_status"))
        _fill_if_missing(episode, "estimate_status", _first_status(blocks, "estimate_status"))
        _fill_if_missing(episode, "insurance_status", _first_status(blocks, "insurance_status"))
        _fill_if_missing(episode, "pharmacy_ready", _first_status(blocks, "pharmacy_ready"))
        _fill_if_missing(episode, "owner_updated", _first_status(blocks, "owner_updated"))
        _fill_if_missing(episode, "referring_vet_report_sent", _first_status(blocks, "referring_vet_report_sent"))
        _fill_if_missing(episode, "discharge_clear", _first_status(blocks, "discharge_clear"))
        episode.updated_at = _now()
        session.add(episode)
    session.commit()


def _cases_payload(session: Session) -> dict[str, Any]:
    cases = session.exec(select(PatientCase).order_by(PatientCase.patient_name)).all()
    episodes = session.exec(select(ReferralEpisode).order_by(ReferralEpisode.updated_at.desc())).all()
    events = session.exec(select(PatientWorkflowEvent).order_by(PatientWorkflowEvent.created_at.desc())).all()
    by_case: dict[str, list[ReferralEpisode]] = defaultdict(list)
    by_episode: dict[str, list[PatientWorkflowEvent]] = defaultdict(list)
    for episode in episodes:
        by_case[episode.patient_case_id].append(episode)
    for event in events:
        by_episode[event.episode_id].append(event)
    payload = []
    for case in cases:
        payload.append({
            **_case_dict(case),
            "episodes": [{**_episode_dict(episode), "events": [_event_dict(event) for event in by_episode.get(episode.id, [])]} for episode in by_case.get(case.id, [])],
        })
    return {"cases": payload, "count": len(payload)}


@router.get("/cases")
def list_patient_cases(sync: bool = True, session: Session = Depends(get_session)) -> dict[str, Any]:
    if sync:
        _sync_from_blocks(session)
    return _cases_payload(session)


@router.post("/sync-from-day-control")
def sync_from_day_control(session: Session = Depends(get_session)) -> dict[str, Any]:
    _sync_from_blocks(session)
    return _cases_payload(session)


@router.patch("/episodes/{episode_id}/state")
def update_episode_state(episode_id: str, payload: EpisodeStatePatch, session: Session = Depends(get_session)) -> dict[str, Any]:
    episode = session.get(ReferralEpisode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="episode not found")
    before = _episode_dict(episode)
    updates = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    mapping = {
        "ownerRole": "owner_role",
        "ownerName": "owner_name",
        "currentLocation": "current_location",
        "nextAction": "next_action",
        "consentStatus": "consent_status",
        "estimateStatus": "estimate_status",
        "insuranceStatus": "insurance_status",
        "pharmacyReady": "pharmacy_ready",
        "ownerUpdated": "owner_updated",
        "referringVetReportSent": "referring_vet_report_sent",
        "dischargeClear": "discharge_clear",
    }
    for key, value in updates.items():
        if key in {"actor", "note"}:
            continue
        setattr(episode, mapping.get(key, key), value)
    episode.updated_at = _now()
    session.add(episode)
    event = PatientWorkflowEvent(episode_id=episode.id, patient_case_id=episode.patient_case_id, event_type="state_change", action="update_episode_state", actor=payload.actor, note=payload.note or "episode state updated")
    session.add(event)
    after = _episode_dict(episode)
    _record_evidence(session, episode, "update_episode_state", payload.actor, before, after, payload.note)
    session.commit()
    session.refresh(episode)
    return {"episode": _episode_dict(episode), "event": _event_dict(event)}


@router.post("/episodes/{episode_id}/events")
def create_workflow_event(episode_id: str, payload: WorkflowEventCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    episode = session.get(ReferralEpisode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="episode not found")
    before = _episode_dict(episode)
    event = PatientWorkflowEvent(episode_id=episode.id, patient_case_id=episode.patient_case_id, event_type=payload.eventType, action=payload.action, actor=payload.actor, note=payload.note, source_block_id=payload.sourceBlockId, at_time=payload.atTime)
    episode.next_action = payload.note or payload.action.replace("_", " ")
    episode.updated_at = _now()
    session.add(episode)
    session.add(event)
    after = _episode_dict(episode)
    _record_evidence(session, episode, payload.action, payload.actor, before, after, payload.note)
    session.commit()
    session.refresh(event)
    return {"episode": _episode_dict(episode), "event": _event_dict(event)}
