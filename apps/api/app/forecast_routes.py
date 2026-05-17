from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.database import get_session
from app.flow_state_models import DischargeBlocker, OccupancyRecord, StaffAssignmentRisk
from app.inpatient_models import InpatientStay, MedicationDue, ObservationTask
from app.models import ResultReview, Room, RoomState, ScheduleBlock

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def overlap_minutes(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> int:
    start = max(start_a, start_b)
    end = min(end_a, end_b)
    seconds = (end - start).total_seconds()
    return max(0, int(seconds // 60))


def risk_from_ratio(ratio: float) -> str:
    if ratio >= 0.9:
        return "red"
    if ratio >= 0.7:
        return "amber"
    return "green"


def room_group(room_type: str | None, room_name: str | None = None) -> str:
    value = f"{room_type or ''} {room_name or ''}".lower()
    if any(x in value for x in ["mri", "ct", "x-ray", "xray", "ultrasound", "imaging"]):
        return "imaging"
    if any(x in value for x in ["ward", "kennel", "cat", "dog"]):
        return "ward"
    if "icu" in value or "high" in value:
        return "icu"
    if "recovery" in value:
        return "recovery"
    if "resus" in value or "ecc" in value:
        return "ecc"
    return "theatre"


@router.get("/api/forecast/hospital")
def hospital_forecast(
    hours: int = Query(default=24, ge=1, le=72),
    slot_minutes: int = Query(default=60, ge=15, le=240),
    session: Session = Depends(get_session),
):
    now = utc_now()
    end = now + timedelta(hours=hours)

    rooms = session.exec(select(Room).where(Room.active == True)).all()
    room_states = session.exec(select(RoomState)).all()
    schedule = session.exec(select(ScheduleBlock).where(ScheduleBlock.ends_at >= now, ScheduleBlock.starts_at <= end)).all()
    inpatients = session.exec(select(InpatientStay).where(InpatientStay.status == "active")).all()
    occupancy = session.exec(select(OccupancyRecord).where(OccupancyRecord.status != "released")).all()
    obs_due = session.exec(select(ObservationTask).where(ObservationTask.status != "done", ObservationTask.due_at <= end)).all()
    meds_due = session.exec(select(MedicationDue).where(MedicationDue.status != "done", MedicationDue.due_at <= end)).all()
    blockers = session.exec(select(DischargeBlocker).where(DischargeBlocker.status == "open")).all()
    results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()
    staff_risk = session.exec(select(StaffAssignmentRisk).where(StaffAssignmentRisk.status != "approved")).all()

    capacity = defaultdict(int)
    for room in rooms:
        capacity[room_group(room.room_type, room.name)] += 1
    for key in ["theatre", "imaging", "ward", "icu", "recovery", "ecc"]:
        capacity.setdefault(key, 0)

    state_by_room = {x.room_name: x for x in room_states}
    blocked_rooms = [x for x in room_states if x.state in {"blocked", "out_of_service", "cleaning"}]

    slots = []
    cursor = now.replace(second=0, microsecond=0)
    while cursor < end:
        slot_end = cursor + timedelta(minutes=slot_minutes)
        group_load = {"theatre": 0, "imaging": 0, "ward": 0, "icu": 0, "recovery": 0, "ecc": 0}
        risks: list[str] = []
        events: list[dict] = []

        for block in schedule:
            minutes = overlap_minutes(block.starts_at, block.ends_at, cursor, slot_end)
            if minutes <= 0:
                continue
            group = room_group(None, block.room_name)
            if block.block_type in {"imaging", "diagnostic"}:
                group = "imaging"
            if block.block_type in {"recovery"}:
                group = "recovery"
            group_load[group] = group_load.get(group, 0) + 1
            events.append({"type": "schedule", "id": block.id, "episode_id": block.episode_id, "block_type": block.block_type, "room_name": block.room_name, "status": block.status})
            if block.room_name and block.room_name in state_by_room and state_by_room[block.room_name].state in {"blocked", "out_of_service", "cleaning"}:
                risks.append(f"{block.room_name} is {state_by_room[block.room_name].state}")

        due_obs = [x for x in obs_due if cursor <= x.due_at < slot_end]
        due_meds = [x for x in meds_due if cursor <= x.due_at < slot_end]
        if len(due_obs) >= 5:
            risks.append(f"{len(due_obs)} observations due")
        if len(due_meds) >= 5:
            risks.append(f"{len(due_meds)} medication tasks due")

        open_discharge_blockers = len(blockers)
        pending_results = len(results)
        open_staff_risks = len(staff_risk)
        if open_discharge_blockers:
            risks.append(f"{open_discharge_blockers} open discharge blocker(s)")
        if pending_results:
            risks.append(f"{pending_results} pending result review(s)")
        if open_staff_risks:
            risks.append(f"{open_staff_risks} staff assignment risk(s)")

        group_ratios = {}
        worst_ratio = 0.0
        for group, load in group_load.items():
            cap = max(capacity.get(group, 0), 1)
            ratio = load / cap
            group_ratios[group] = round(ratio, 2)
            worst_ratio = max(worst_ratio, ratio)

        risk = risk_from_ratio(worst_ratio)
        if any("blocked" in r or "out_of_service" in r or "staff assignment" in r for r in risks):
            risk = "red"
        elif risks and risk == "green":
            risk = "amber"

        slots.append({
            "starts_at": cursor,
            "ends_at": slot_end,
            "risk": risk,
            "capacity": dict(capacity),
            "load": group_load,
            "ratios": group_ratios,
            "risks": risks,
            "events": events[:20],
            "obs_due": len(due_obs),
            "meds_due": len(due_meds),
        })
        cursor = slot_end

    group_summary = defaultdict(lambda: {"load_blocks": 0, "capacity": 0, "risk": "green"})
    for group, cap in capacity.items():
        group_summary[group]["capacity"] = cap
    for block in schedule:
        group = room_group(None, block.room_name)
        if block.block_type in {"imaging", "diagnostic"}:
            group = "imaging"
        if block.block_type == "recovery":
            group = "recovery"
        group_summary[group]["load_blocks"] += 1
    for group, row in group_summary.items():
        cap = max(row["capacity"], 1)
        row["risk"] = risk_from_ratio(row["load_blocks"] / max(cap * max(hours / 4, 1), 1))

    return {
        "window": {"starts_at": now, "ends_at": end, "hours": hours, "slot_minutes": slot_minutes},
        "summary": {
            "rooms": len(rooms),
            "blocked_or_cleaning_rooms": len(blocked_rooms),
            "schedule_blocks": len(schedule),
            "active_inpatients": len(inpatients),
            "active_occupancy": len(occupancy),
            "open_discharge_blockers": len(blockers),
            "pending_results": len(results),
            "staff_risks": len(staff_risk),
            "obs_due": len(obs_due),
            "meds_due": len(meds_due),
            "red_slots": len([s for s in slots if s["risk"] == "red"]),
            "amber_slots": len([s for s in slots if s["risk"] == "amber"]),
        },
        "groups": dict(group_summary),
        "blocked_rooms": blocked_rooms,
        "slots": slots,
        "next_actions": [
            "resolve red room/state blockers",
            "review pending diagnostics/results",
            "clear discharge blockers to release beds",
            "approve or reassign staff-risk items",
            "protect recovery and ICU capacity before theatre starts",
        ],
    }
