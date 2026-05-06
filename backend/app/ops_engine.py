from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import (
    AuditEvent,
    Blocker,
    Episode,
    EthicsFlag,
    ResultReview,
    RoomState,
    ScheduleBlock,
    WorkItem,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


WORKFLOW: dict[str, list[str]] = {
    "reception_intake": [
        "contact_received",
        "referral_captured",
        "case_created",
        "awaiting_triage",
        "booked",
        "arrived",
        "waiting",
        "handed_to_clinical_team",
    ],
    "triage_consult": [
        "awaiting_triage",
        "in_consult",
        "awaiting_diagnostics",
        "awaiting_treatment_decision",
        "sent_to_next_stage",
    ],
    "imaging": [
        "requested",
        "booked",
        "waiting",
        "in_scan",
        "reporting",
        "result_returned",
        "reviewed",
        "actioned",
    ],
    "surgery_theatre": [
        "waiting_for_theatre",
        "in_prep",
        "anaesthesia_start",
        "procedure_in_progress",
        "recovery",
        "cleaning",
        "ready_again",
    ],
    "icu": [
        "admitted",
        "stable",
        "unstable",
        "escalated",
        "transfer_pending",
        "discharged_to_ward",
        "discharged_from_hospital",
    ],
}

PHASE_TO_DEPARTMENT = {
    "intake": "reception_intake",
    "awaiting_triage": "triage_consult",
    "triage": "triage_consult",
    "consult": "triage_consult",
    "imaging": "imaging",
    "diagnostics": "imaging",
    "procedure": "surgery_theatre",
    "surgery": "surgery_theatre",
    "theatre": "surgery_theatre",
    "critical_care": "icu",
    "icu": "icu",
}


def department_for_episode(episode: Episode) -> str:
    phase = (episode.current_phase or "intake").lower()
    section = (episode.current_section_name or "").lower()
    if "imaging" in section or "mri" in section or "ct" in section or "x-ray" in section:
        return "imaging"
    if "icu" in section or "ecc" in section or "resus" in section:
        return "icu"
    if "theatre" in section or "surgery" in section or "prep" in section:
        return "surgery_theatre"
    return PHASE_TO_DEPARTMENT.get(phase, "reception_intake")


def open_blockers(session: Session, episode_id: int) -> list[Blocker]:
    return session.exec(select(Blocker).where(Blocker.episode_id == episode_id, Blocker.status == "open")).all()


def open_ethics(session: Session, episode_id: int) -> list[EthicsFlag]:
    return session.exec(select(EthicsFlag).where(EthicsFlag.episode_id == episode_id, EthicsFlag.status == "open")).all()


def pending_results(session: Session, episode_id: int) -> list[ResultReview]:
    return session.exec(select(ResultReview).where(ResultReview.episode_id == episode_id, ResultReview.status == "pending_review")).all()


def planned_blocks(session: Session, episode_id: int) -> list[ScheduleBlock]:
    return session.exec(select(ScheduleBlock).where(ScheduleBlock.episode_id == episode_id, ScheduleBlock.status != "done")).all()


def room_state(session: Session, room_name: str | None) -> RoomState | None:
    if not room_name:
        return None
    return session.exec(select(RoomState).where(RoomState.room_name == room_name)).first()


def next_allowed(current: str, target: str, states: list[str]) -> bool:
    if target not in states:
        return False
    if current not in states:
        return target == states[0]
    return states.index(target) <= states.index(current) + 1


def evaluate_transition(session: Session, episode: Episode, target_state: str) -> dict[str, Any]:
    department = department_for_episode(episode)
    states = WORKFLOW[department]
    current = episode.current_phase or states[0]
    reasons: list[str] = []
    warnings: list[str] = []

    if not next_allowed(current, target_state, states):
        reasons.append(f"Illegal transition for {department}: {current} -> {target_state}")

    blockers = open_blockers(session, episode.id or 0)
    ethics = open_ethics(session, episode.id or 0)
    results = pending_results(session, episode.id or 0)
    blocks = planned_blocks(session, episode.id or 0)

    if target_state in {"handed_to_clinical_team", "sent_to_next_stage", "actioned", "procedure_in_progress", "discharged_to_ward", "discharged_from_hospital"}:
        if blockers:
            reasons.append(f"{len(blockers)} open blocker(s) must be resolved first")
        if ethics:
            reasons.append(f"{len(ethics)} open ethics/safeguarding flag(s) need review")

    if target_state in {"reviewed", "actioned", "sent_to_next_stage", "discharged_from_hospital"} and results:
        reasons.append(f"{len(results)} pending result review(s)")

    if target_state in {"in_scan", "anaesthesia_start", "procedure_in_progress"}:
        active_blocks = [b for b in blocks if b.block_type in {"procedure", "anaesthesia", "imaging", "diagnostic", "prep"}]
        if not active_blocks:
            reasons.append("No active schedule block found for this movement")
        for block in active_blocks:
            state = room_state(session, block.room_name)
            if state and state.state in {"blocked", "out_of_service", "cleaning"}:
                reasons.append(f"Room {block.room_name} is {state.state}")
            if not block.owner_role:
                reasons.append(f"Schedule block {block.id} has no owner role")
            if not block.assigned_staff_member_id:
                warnings.append(f"Schedule block {block.id} has no assigned staff member")

    if target_state == "ready_again":
        dirty_rooms = [b.room_name for b in blocks if b.block_type == "cleaning" and b.status not in {"done", "complete", "completed"}]
        if dirty_rooms:
            reasons.append(f"Cleaning not completed for: {', '.join([x for x in dirty_rooms if x])}")

    return {
        "allowed": not reasons,
        "department": department,
        "current_state": current,
        "target_state": target_state,
        "reasons": reasons,
        "warnings": warnings,
    }


def transition_episode(session: Session, episode_ref: str, target_state: str, actor_name: str, note: str | None = None) -> dict[str, Any]:
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        return {"allowed": False, "reasons": ["Episode not found"], "episode_ref": episode_ref}

    verdict = evaluate_transition(session, episode, target_state)
    if not verdict["allowed"]:
        session.add(AuditEvent(actor_name=actor_name, action="transition_blocked", entity_type="episode", entity_id=episode.id or 0, summary=f"Blocked {episode_ref}: {verdict['current_state']} -> {target_state}; {' | '.join(verdict['reasons'])}"))
        session.commit()
        return {**verdict, "episode_ref": episode_ref}

    previous = episode.current_phase
    episode.current_phase = target_state
    if target_state in {"in_scan", "reporting", "result_returned", "reviewed"}:
        episode.current_section_name = "Imaging"
    elif target_state in {"in_prep", "anaesthesia_start", "procedure_in_progress", "recovery", "cleaning"}:
        episode.current_section_name = "Theatres"
    elif target_state in {"admitted", "stable", "unstable", "escalated", "transfer_pending"}:
        episode.current_section_name = "ICU"
    elif target_state in {"awaiting_triage", "in_consult", "awaiting_treatment_decision"}:
        episode.current_section_name = "Triage"
    session.add(episode)
    session.add(AuditEvent(actor_name=actor_name, action="transitioned", entity_type="episode", entity_id=episode.id or 0, summary=f"{episode_ref}: {previous} -> {target_state}. {note or ''}".strip()))
    session.add(WorkItem(title=f"State changed: {episode_ref} -> {target_state}", input_type="system_event", source="ops_engine", category="workflow", description=f"Episode {episode_ref} moved from {previous} to {target_state}", urgency="green", owner_role="ops_manager", section_name=episode.current_section_name, room_name=episode.current_room_name, linked_episode_ref=episode_ref, status="done"))
    session.commit()
    session.refresh(episode)
    return {**verdict, "episode_ref": episode_ref, "episode": episode}
