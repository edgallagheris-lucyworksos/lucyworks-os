from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, Episode, Patient, StaffMember, WorkItem, PharmacyRequest

router = APIRouter()


def now():
    return datetime.now(timezone.utc)


class V3CaseCreate(BaseModel):
    patient_name: str
    species: str
    owner_name: str = "Unknown owner"
    signalment: Optional[str] = None
    presenting_problem: str
    symptoms_text: str = ""
    pain_score: Optional[int] = None
    repeat_sedation_6mo: int = 0
    consent_obtained: bool = True
    financial_constraint: bool = False
    actor_name: str = "V3 Operational Board"


class V3AssignPayload(BaseModel):
    required_skills: list[str] = []
    actor_name: str = "V3 Operational Board"


class V3TimelinePayload(BaseModel):
    note: str
    actor_name: str = "V3 Operational Board"


class V3PharmacyPayload(BaseModel):
    episode_ref: Optional[str] = None
    medication_name: str
    value_gbp: float = 0
    followed_protocol: bool = True
    actor_name: str = "V3 Operational Board"


def audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
    session.commit()


def triage(payload: V3CaseCreate):
    text = f"{payload.presenting_problem} {payload.symptoms_text}".lower()
    reasons = []
    actions = []
    flags = []
    urgency = "green"
    confidence = 0.65
    handoff = "advise_only"

    red_terms = ["collapse", "unresponsive", "blocked", "nonproductive", "retching", "distended", "paralysis", "severe back pain", "severe pain"]
    amber_terms = ["vomiting", "lethargy", "pain", "not eating", "limping"]

    if any(term in text for term in red_terms):
        urgency = "red"
        confidence = 0.9
        handoff = "required"
        reasons.append("RED triage trigger found")
        actions.append("Vet handoff required")
    elif any(term in text for term in amber_terms):
        urgency = "amber"
        confidence = 0.75
        handoff = "vet_review"
        reasons.append("AMBER triage trigger found")
        actions.append("Vet review required")

    if payload.pain_score is not None:
        if payload.pain_score >= 8:
            urgency = "red"
            confidence = max(confidence, 0.9)
            handoff = "required"
            reasons.append("Severe pain score")
        elif payload.pain_score >= 5 and urgency == "green":
            urgency = "amber"
            confidence = max(confidence, 0.75)
            handoff = "vet_review"
            reasons.append("Moderate pain score")

    if payload.repeat_sedation_6mo >= 2:
        flags.append("REPEAT_SEDATION")
    if not payload.consent_obtained:
        flags.append("CONSENT_GAP")
        urgency = "red"
        handoff = "required"
        reasons.append("Consent gap hard stop")
        actions.append("Consent required before clinical progression")
    if payload.financial_constraint:
        flags.append("FINANCIAL_CONSTRAINT")
        actions.append("Senior vet review of plan/costs")

    return {
        "urgency": urgency,
        "confidence": confidence,
        "handoff": handoff,
        "reasons": list(dict.fromkeys(reasons)),
        "actions": list(dict.fromkeys(actions)),
        "ethics_flags": list(dict.fromkeys(flags)),
    }


def score_staff(staff: StaffMember, required: list[str]) -> float:
    skills = {s.strip().lower() for s in (staff.skills or "").split(",") if s.strip()}
    req = {s.lower() for s in required if s}
    if not req:
        overlap = 1.0
    else:
        overlap = len(skills & req) / max(1, len(req))
    role_boost = 0.25 if staff.role.lower() in {"vet", "clinician", "specialist", "anaesthetist"} else 0
    return overlap + role_boost


@router.get("/api/v3/board")
def v3_board(session: Session = Depends(get_session)):
    episodes = session.exec(select(Episode).order_by(Episode.created_at.desc()).limit(30)).all()
    work = session.exec(select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.created_at.desc()).limit(50)).all()
    audits = session.exec(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(50)).all()
    staff = session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()
    pharmacy = session.exec(select(PharmacyRequest).order_by(PharmacyRequest.created_at.desc()).limit(20)).all()
    return {
        "summary": {
            "active_episodes": len(episodes),
            "open_work_items": len(work),
            "red_items": len([w for w in work if w.urgency == "red"]),
            "amber_items": len([w for w in work if w.urgency == "amber"]),
            "staff_on_system": len(staff),
            "pharmacy_requests": len(pharmacy),
        },
        "episodes": episodes,
        "work_items": work,
        "audit": audits,
        "staff": staff,
        "pharmacy": pharmacy,
    }


@router.post("/api/v3/cases")
def create_v3_case(payload: V3CaseCreate, session: Session = Depends(get_session)):
    tri = triage(payload)
    patient = Patient(patient_name=payload.patient_name, species=payload.species.lower(), owner_name=payload.owner_name)
    session.add(patient)
    session.commit()
    session.refresh(patient)

    next_id = int(datetime.now().timestamp())
    episode_ref = f"EP-{next_id}"
    episode = Episode(
        episode_ref=episode_ref,
        patient_id=patient.id or 0,
        status="active",
        current_section_name="Reception / Intake",
        current_room_name=None,
        current_phase="awaiting_triage" if tri["urgency"] != "green" else "intake",
    )
    session.add(episode)
    session.commit()
    session.refresh(episode)

    title = f"{tri['urgency'].upper()} triage: {payload.patient_name} — {payload.presenting_problem}"
    item = WorkItem(
        title=title,
        input_type="case_intake",
        source="v3_operational_board",
        category="triage",
        description=payload.symptoms_text or payload.presenting_problem,
        urgency=tri["urgency"],
        owner_role="clinician" if tri["handoff"] != "advise_only" else "admin",
        section_name="Reception / Intake",
        linked_patient_name=payload.patient_name,
        linked_episode_ref=episode_ref,
        status="new",
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    audit(session, payload.actor_name, "case_created", "episode", episode.id or 0, f"Created {episode_ref}: {payload.patient_name}; urgency={tri['urgency']}; handoff={tri['handoff']}")
    if tri["urgency"] == "red":
        audit(session, payload.actor_name, "handoff_required", "episode", episode.id or 0, "RED triage requires vet handoff")
    for flag in tri["ethics_flags"]:
        audit(session, payload.actor_name, f"ethics_flag:{flag}", "episode", episode.id or 0, f"Ethics flag created: {flag}")

    return {"ok": True, "episode": episode, "patient": patient, "triage": tri, "work_item": item}


@router.post("/api/v3/cases/{episode_ref}/events")
def add_v3_event(episode_ref: str, payload: V3TimelinePayload, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    item = WorkItem(
        title=f"Timeline note: {episode_ref}",
        input_type="timeline_note",
        source="v3_operational_board",
        category="case_event",
        description=payload.note,
        urgency="green",
        owner_role="ops_manager",
        section_name=episode.current_section_name,
        linked_episode_ref=episode_ref,
        status="done",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    audit(session, payload.actor_name, "timeline_note", "episode", episode.id or 0, payload.note[:180])
    return {"ok": True, "event": item}


@router.post("/api/v3/cases/{episode_ref}/assign")
def assign_v3_case(episode_ref: str, payload: V3AssignPayload, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    staff = session.exec(select(StaffMember).where(StaffMember.active == True)).all()
    ranked = sorted(staff, key=lambda s: score_staff(s, payload.required_skills), reverse=True)
    chosen = ranked[0] if ranked and score_staff(ranked[0], payload.required_skills) >= 0.5 else None
    if not chosen:
        audit(session, payload.actor_name, "assignment_failed", "episode", episode.id or 0, f"No suitable staff for {payload.required_skills}")
        raise HTTPException(status_code=409, detail="No suitable active staff member found")
    item = WorkItem(
        title=f"Assigned {episode_ref} to {chosen.name}",
        input_type="assignment",
        source="v3_operational_board",
        category="staff_assignment",
        description=f"Required skills: {', '.join(payload.required_skills)}",
        urgency="green",
        owner_role=chosen.role,
        owner_user_id=chosen.user_id,
        section_name=episode.current_section_name,
        linked_episode_ref=episode_ref,
        status="done",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    audit(session, payload.actor_name, "assigned", "episode", episode.id or 0, f"Assigned {episode_ref} to {chosen.name}")
    return {"ok": True, "assigned_staff": chosen, "assignment_event": item}


@router.post("/api/v3/pharmacy/orders")
def create_v3_pharmacy_order(payload: V3PharmacyPayload, session: Session = Depends(get_session)):
    episode = None
    if payload.episode_ref:
        episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
    req = PharmacyRequest(
        episode_id=episode.id if episode else None,
        medication_name=payload.medication_name,
        request_type="dispense",
        controlled_or_legal_status="governance_check",
        authorised_supplier_required=True,
        quantity=f"£{payload.value_gbp:.2f}",
        urgency="red" if payload.value_gbp >= 5000 and not payload.followed_protocol else "amber",
        owner_role="nurse",
        status="requested",
        compliance_note="Protocol followed" if payload.followed_protocol else "Protocol not followed",
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    audit(session, payload.actor_name, "pharmacy_order", "pharmacy_request", req.id or 0, f"Pharmacy request {payload.medication_name} £{payload.value_gbp:.2f}")
    if payload.value_gbp >= 5000 and not payload.followed_protocol:
        audit(session, payload.actor_name, "medicines_governance_breach", "pharmacy_request", req.id or 0, f"High-value pharmacy order without protocol: £{payload.value_gbp:.2f}")
    return {"ok": True, "pharmacy_request": req}
