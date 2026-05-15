from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.dashboard_routes import _episode_bundle, _episode_pressures
from app.database import get_session
from app.main_fixed import alerts_for, compute_conflicts
from app.models import Episode, ScheduleBlock, WorkItem

router = APIRouter()


def _to_iso(dt):
    return dt.isoformat() if dt else None


def _rank_item(item: dict):
    urgency_score = {"red": 3, "amber": 2, "green": 1}.get(item.get("urgency"), 1)
    type_score = {
        "ethics": 5,
        "red_work": 5,
        "blocker": 4,
        "pharmacy": 4,
        "discharge": 4,
        "stock": 3,
        "decision": 3,
        "result_review": 2,
        "owner_comms": 2,
        "triage": 2,
        "work": 1,
    }.get(item.get("type"), 1)
    return urgency_score * 10 + type_score


def _case_item(episode, pressure_item):
    return {
        "episode": episode,
        "type": pressure_item.get("type"),
        "section": pressure_item.get("section"),
        "detail": pressure_item.get("detail"),
        "owner_role": pressure_item.get("owner_role"),
        "urgency": pressure_item.get("urgency"),
        "score": _rank_item(pressure_item),
    }


@router.get("/api/dashboard/clinical-director")
def clinical_director_read(session: Session = Depends(get_session)):
    now = datetime.now()
    next_hour = now + timedelta(minutes=60)
    episodes = session.exec(select(Episode)).all()
    schedule_blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
    alerts = alerts_for(session)
    conflicts = compute_conflicts(session)
    unsafe_now = []
    flow_blockers = []
    decision_required = []
    owner_failures = []
    next_60_minutes = []

    for episode in episodes:
        bundle = _episode_bundle(session, episode)
        pressure = _episode_pressures(session, episode)
        for item in pressure.get("hard_blocks", []):
            row = _case_item(bundle, item)
            unsafe_now.append(row)
            flow_blockers.append(row)
            if not item.get("owner_role") or item.get("owner_role") == "unowned":
                owner_failures.append(row)
        for item in pressure.get("warnings", []):
            row = _case_item(bundle, item)
            if item.get("type") in {"decision", "result_review", "owner_comms", "triage"}:
                decision_required.append(row)
            if not item.get("owner_role") or item.get("owner_role") == "unowned":
                owner_failures.append(row)

    for block in schedule_blocks:
        if block.starts_at <= next_hour and block.ends_at >= now:
            episode = session.get(Episode, block.episode_id)
            bundle = _episode_bundle(session, episode)
            pressure = _episode_pressures(session, episode)
            next_60_minutes.append({
                "starts_at": _to_iso(block.starts_at),
                "ends_at": _to_iso(block.ends_at),
                "block_type": block.block_type,
                "room_name": block.room_name,
                "owner_role": block.owner_role,
                "episode": bundle,
                "hard_block_count": len(pressure.get("hard_blocks", [])),
                "warning_count": len(pressure.get("warnings", [])),
                "next_action": pressure.get("next_action"),
            })

    unsafe_now = sorted(unsafe_now, key=lambda x: x["score"], reverse=True)
    flow_blockers = sorted(flow_blockers, key=lambda x: x["score"], reverse=True)
    decision_required = sorted(decision_required, key=lambda x: x["score"], reverse=True)
    owner_failures = sorted(owner_failures, key=lambda x: x["score"], reverse=True)
    next_60_minutes = sorted(next_60_minutes, key=lambda x: x["starts_at"] or "")

    red_count = len(unsafe_now) + len([a for a in alerts if a.get("severity") == "high"])
    amber_count = len(decision_required) + len(conflicts)
    hospital_state = "red" if red_count else "amber" if amber_count else "green"
    top_risks = []
    if unsafe_now:
        top_risks.append(f"{len(unsafe_now)} hard blocker(s) affecting live flow")
    if decision_required:
        top_risks.append(f"{len(decision_required)} decision/comms/result item(s) need ownership")
    if conflicts:
        top_risks.append(f"{len(conflicts)} operational conflict(s) detected")
    if alerts:
        top_risks.append(f"{len(alerts)} alert(s), including {len([a for a in alerts if a.get('severity') == 'high'])} high")

    next_action = unsafe_now[0] if unsafe_now else decision_required[0] if decision_required else flow_blockers[0] if flow_blockers else None
    reason_for_state = top_risks[0] if top_risks else "No red/amber command pressure detected in current data."
    ignored_risk = "Delays compound into missed handoffs, unsafe movement, owner-update failure or blocked discharge." if hospital_state != "green" else "Maintain flow and prevent small blockers becoming red work."

    return {
        "generated_at": _to_iso(now),
        "hospital_state": hospital_state,
        "reason_for_state": reason_for_state,
        "top_risks": top_risks,
        "next_action": next_action,
        "ignored_risk": ignored_risk,
        "lanes": {
            "unsafe_now": unsafe_now[:10],
            "flow_blockers": flow_blockers[:10],
            "decision_required": decision_required[:10],
            "owner_failures": owner_failures[:10],
            "next_60_minutes": next_60_minutes[:16],
        },
        "counts": {
            "unsafe_now": len(unsafe_now),
            "flow_blockers": len(flow_blockers),
            "decision_required": len(decision_required),
            "owner_failures": len(owner_failures),
            "next_60_minutes": len(next_60_minutes),
            "conflicts": len(conflicts),
            "alerts": len(alerts),
        },
    }
