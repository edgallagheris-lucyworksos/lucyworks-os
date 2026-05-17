from datetime import datetime
from sqlmodel import Session, select

from app.capability_engine import procedure_capability_profile
from app.models import (
    CaseProcedure,
    DischargeReadiness,
    Episode,
    EthicsFlag,
    OwnerCommsRequirement,
    PharmacyRequest,
    ProcedureType,
    RoomState,
    ScheduleBlock,
    StaffMember,
    StockOrder,
)


def _staff_matches_role(staff: StaffMember | None, owner_role: str | None, required_roles: list[str]):
    if not staff:
        return False
    haystack = f"{staff.role} {staff.skills}".lower()
    expected = " ".join([owner_role or "", *required_roles]).lower()
    return any(token in haystack for token in expected.replace("/", " ").replace("+", " ").split() if len(token) > 3)


def _open_pharmacy(session: Session, episode_id: int):
    return session.exec(select(PharmacyRequest).where(PharmacyRequest.episode_id == episode_id)).all()


def _open_stock(session: Session, episode_id: int):
    return session.exec(select(StockOrder).where(StockOrder.episode_id == episode_id)).all()


def _open_discharge(session: Session, episode_id: int):
    return session.exec(select(DischargeReadiness).where(DischargeReadiness.episode_id == episode_id)).all()


def slot_dependency_check(session: Session, block: ScheduleBlock):
    episode = session.get(Episode, block.episode_id)
    cp = session.get(CaseProcedure, block.case_procedure_id) if block.case_procedure_id else None
    pt = session.get(ProcedureType, cp.procedure_type_id) if cp else None
    staff = session.get(StaffMember, block.assigned_staff_member_id) if block.assigned_staff_member_id else None
    room = session.exec(select(RoomState).where(RoomState.room_name == block.room_name)).first() if block.room_name else None
    capability = procedure_capability_profile(pt.name) if pt else None

    hard = []
    warnings = []
    required_roles = capability.get("required_roles", []) if capability else []
    room_options = capability.get("room_options", []) if capability else []
    readiness_gates = capability.get("readiness_gates", []) if capability else []

    if not episode:
        hard.append({"type": "missing_episode", "detail": "Schedule block has no episode context", "owner_role": "ops_manager"})
    if not cp or not pt or not capability:
        hard.append({"type": "missing_procedure_capability", "detail": "Procedure capability profile missing", "owner_role": "ops_manager"})

    if not block.owner_role:
        hard.append({"type": "missing_owner_role", "detail": f"{block.block_type} has no owner role", "owner_role": "ops_manager"})

    if block.block_type in {"anaesthesia", "procedure", "recovery"} and not staff:
        hard.append({"type": "missing_assigned_staff", "detail": f"{block.block_type} has no assigned staff member", "owner_role": block.owner_role or "ops_manager"})
    elif staff and not _staff_matches_role(staff, block.owner_role, required_roles):
        warnings.append({"type": "staff_skill_check", "detail": f"Assigned staff {staff.name} may not match required role set", "owner_role": "ops_manager"})

    if not block.room_name:
        hard.append({"type": "missing_room", "detail": "Schedule block has no room", "owner_role": "ops_manager"})
    elif room_options and block.room_name not in room_options:
        hard.append({"type": "unsuitable_room", "detail": f"{block.room_name} is not in suitable room options: {', '.join(room_options)}", "owner_role": "ops_manager"})

    if not room:
        warnings.append({"type": "missing_room_state", "detail": f"No room state record for {block.room_name}", "owner_role": "ops_manager"})
    elif room.state in {"dirty", "cleaning", "blocked", "unavailable"} and block.block_type not in {"cleaning"}:
        hard.append({"type": "room_not_released", "detail": f"{room.room_name} is {room.state}", "owner_role": "nurse"})

    if episode:
        pharmacy = [x for x in _open_pharmacy(session, episode.id) if x.status != "complete"]
        stock = [x for x in _open_stock(session, episode.id) if x.status != "complete"]
        discharge = [x for x in _open_discharge(session, episode.id) if x.readiness_state != "ready" or x.status != "complete"]
        ethics = session.exec(select(EthicsFlag).where(EthicsFlag.episode_id == episode.id)).all()
        comms = session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.episode_id == episode.id)).all()

        if block.block_type in {"anaesthesia", "procedure", "recovery"}:
            for item in pharmacy:
                hard.append({"type": "pharmacy_open", "detail": f"{item.medication_name} is {item.status}", "owner_role": item.owner_role})
            for item in stock:
                hard.append({"type": "stock_open", "detail": f"{item.item_name}: {item.reason}", "owner_role": "nurse"})

        if block.block_type == "procedure":
            open_ethics = [x for x in ethics if x.status != "resolved"]
            for item in open_ethics:
                hard.append({"type": "ethics_open", "detail": item.detail, "owner_role": item.owner_role})
            open_comms = [x for x in comms if x.status != "complete" and x.urgency == "red"]
            for item in open_comms:
                hard.append({"type": "owner_comms_red", "detail": item.required_message, "owner_role": item.owner_role})

        if block.block_type in {"recovery", "cleaning"} and discharge:
            for item in discharge:
                warnings.append({"type": "discharge_not_ready", "detail": item.blocker_summary or "Discharge readiness incomplete", "owner_role": item.owner_role})

    now = datetime.now(block.starts_at.tzinfo) if block.starts_at.tzinfo else datetime.now()
    is_live_or_due = block.starts_at <= now <= block.ends_at or block.starts_at <= now
    can_start = len(hard) == 0
    risk = "red" if hard and is_live_or_due else "amber" if hard or warnings else "green"
    cannot_start_reason = hard[0]["detail"] if hard else None
    next_action = hard[0] if hard else warnings[0] if warnings else None

    return {
        "can_start": can_start,
        "risk": risk,
        "cannot_start_reason": cannot_start_reason,
        "hard_failures": hard,
        "warnings": warnings,
        "next_action": next_action,
        "required_roles": required_roles,
        "room_options": room_options,
        "readiness_gates": readiness_gates,
        "checks": {
            "episode_present": bool(episode),
            "procedure_capability_present": bool(capability),
            "room_suitable": bool(block.room_name and (not room_options or block.room_name in room_options)),
            "room_released": bool(room and (room.state not in {"dirty", "cleaning", "blocked", "unavailable"} or block.block_type == "cleaning")),
            "staff_assigned": bool(staff),
            "staff_skill_probable": bool(_staff_matches_role(staff, block.owner_role, required_roles)) if staff else False,
        },
    }
