from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.inpatient_models import (
    FinancialConsentStatus,
    InpatientStay,
    MedicationDue,
    NightHandover,
    ObservationTask,
    OvernightEvent,
)
from app.models import Episode, Patient, RoomState, WorkItem

router = APIRouter()


def _iso(value):
    return value.isoformat() if value else None


def _patient_for(session: Session, episode: Episode | None):
    if not episode:
        return None
    patient = session.get(Patient, episode.patient_id)
    if not patient:
        return None
    return {
        "name": patient.patient_name,
        "species": patient.species,
        "owner_name": patient.owner_name,
        "owner_phone": patient.owner_phone,
        "weight_kg": patient.weight_kg,
    }


def _risk_from(stay: InpatientStay, handovers, obs, meds, finance, events):
    if stay.acuity == "critical":
        return "red"
    if any(not h.acknowledged for h in handovers):
        return "red"
    if any(e.severity == "high" and e.status != "resolved" for e in events):
        return "red"
    if finance and (finance.pharmacy_blocked or finance.discharge_blocked or finance.owner_financial_constraint):
        return "amber"
    if any(t.status != "done" for t in obs) or any(m.status != "done" for m in meds):
        return "amber"
    return "green"


@router.get("/api/inpatients")
def list_inpatients(session: Session = Depends(get_session)):
    rows = session.exec(select(InpatientStay).where(InpatientStay.status == "active").order_by(InpatientStay.location_room, InpatientStay.bed_label)).all()
    out = []
    for stay in rows:
        ep = session.get(Episode, stay.episode_id)
        obs = session.exec(select(ObservationTask).where(ObservationTask.inpatient_stay_id == stay.id).order_by(ObservationTask.due_at)).all()
        meds = session.exec(select(MedicationDue).where(MedicationDue.inpatient_stay_id == stay.id).order_by(MedicationDue.due_at)).all()
        handovers = session.exec(select(NightHandover).where(NightHandover.inpatient_stay_id == stay.id).order_by(NightHandover.created_at.desc())).all()
        events = session.exec(select(OvernightEvent).where(OvernightEvent.inpatient_stay_id == stay.id).order_by(OvernightEvent.occurred_at.desc())).all()
        finance = session.exec(select(FinancialConsentStatus).where(FinancialConsentStatus.episode_id == stay.episode_id)).first()
        out.append({
            "stay": stay,
            "episode": ep,
            "patient": _patient_for(session, ep),
            "risk": _risk_from(stay, handovers, obs, meds, finance, events),
            "open_obs": len([x for x in obs if x.status != "done"]),
            "open_meds": len([x for x in meds if x.status != "done"]),
            "unacknowledged_handovers": len([x for x in handovers if not x.acknowledged]),
            "open_events": len([x for x in events if x.status != "resolved"]),
            "finance": finance,
        })
    return out


@router.get("/api/overnight-board")
def overnight_board(session: Session = Depends(get_session)):
    stays = session.exec(select(InpatientStay).where(InpatientStay.status == "active").order_by(InpatientStay.location_room, InpatientStay.bed_label)).all()
    room_states = session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()
    room_groups = []
    for room in sorted({stay.location_room for stay in stays}):
        group_stays = [stay for stay in stays if stay.location_room == room]
        cards = []
        for stay in group_stays:
            ep = session.get(Episode, stay.episode_id)
            obs = session.exec(select(ObservationTask).where(ObservationTask.inpatient_stay_id == stay.id).order_by(ObservationTask.due_at)).all()
            meds = session.exec(select(MedicationDue).where(MedicationDue.inpatient_stay_id == stay.id).order_by(MedicationDue.due_at)).all()
            handovers = session.exec(select(NightHandover).where(NightHandover.inpatient_stay_id == stay.id).order_by(NightHandover.created_at.desc())).all()
            events = session.exec(select(OvernightEvent).where(OvernightEvent.inpatient_stay_id == stay.id).order_by(OvernightEvent.occurred_at.desc())).all()
            finance = session.exec(select(FinancialConsentStatus).where(FinancialConsentStatus.episode_id == stay.episode_id)).first()
            risk = _risk_from(stay, handovers, obs, meds, finance, events)
            next_obs = next((x for x in obs if x.status != "done"), None)
            next_med = next((x for x in meds if x.status != "done"), None)
            next_action = None
            if handovers and any(not h.acknowledged for h in handovers):
                next_action = "Acknowledge night handover"
            elif next_obs:
                next_action = f"Obs due: {next_obs.task_type} at {_iso(next_obs.due_at)}"
            elif next_med:
                next_action = f"Medication due: {next_med.medication_name} at {_iso(next_med.due_at)}"
            elif finance and finance.discharge_blocked:
                next_action = "Clear finance/insurance/discharge blocker"
            cards.append({
                "stay": stay,
                "episode": ep,
                "patient": _patient_for(session, ep),
                "risk": risk,
                "next_action": next_action,
                "observation_tasks": obs,
                "medications_due": meds,
                "handovers": handovers,
                "overnight_events": events,
                "financial_consent_status": finance,
            })
        room_groups.append({
            "room_name": room,
            "active": len(cards),
            "red": len([c for c in cards if c["risk"] == "red"]),
            "amber": len([c for c in cards if c["risk"] == "amber"]),
            "cards": cards,
        })
    open_work = session.exec(select(WorkItem).where(WorkItem.status != "done")).all()
    finance_rows = session.exec(select(FinancialConsentStatus)).all()
    return {
        "summary": {
            "active_inpatients": len(stays),
            "icu_or_high_dependency": len([s for s in stays if s.acuity in {"critical", "high_dependency"}]),
            "overnight_required": len([s for s in stays if s.overnight_required]),
            "unacknowledged_handovers": sum(len([h for h in session.exec(select(NightHandover).where(NightHandover.inpatient_stay_id == s.id)).all() if not h.acknowledged]) for s in stays),
            "open_overnight_work": len([w for w in open_work if w.category == "overnight" or w.input_type == "overnight_care"]),
            "finance_or_insurance_blocks": len([f for f in finance_rows if f.pharmacy_blocked or f.discharge_blocked or f.owner_financial_constraint or f.pre_authorisation_status == "pending"]),
            "rooms_tracked": len(room_states),
        },
        "room_groups": room_groups,
    }


@router.get("/api/overnight-grid")
def overnight_grid(session: Session = Depends(get_session)):
    now = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
    end = now + timedelta(hours=12)
    slots = []
    tasks = session.exec(select(ObservationTask).order_by(ObservationTask.due_at)).all()
    meds = session.exec(select(MedicationDue).order_by(MedicationDue.due_at)).all()
    index = 0
    cur = now
    while cur < end:
        slot_end = cur + timedelta(minutes=15)
        slot_tasks = [t for t in tasks if cur <= t.due_at < slot_end and t.status != "done"]
        slot_meds = [m for m in meds if cur <= m.due_at < slot_end and m.status != "done"]
        slots.append({
            "slot_index": index,
            "starts_at": _iso(cur),
            "ends_at": _iso(slot_end),
            "observation_tasks": slot_tasks,
            "medications_due": slot_meds,
            "risk": "red" if any(t.escalation_required for t in slot_tasks) else "amber" if slot_tasks or slot_meds else "green",
        })
        cur = slot_end
        index += 1
    return {"basis": "15-minute overnight inpatient grid", "slots": slots}
