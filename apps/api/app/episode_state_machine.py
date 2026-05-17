from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models import (
    AuditEvent,
    Blocker,
    DecisionRecord,
    DischargeReadiness,
    Episode,
    EthicsFlag,
    OwnerCommsRequirement,
    PharmacyRequest,
    ResultReview,
    ScheduleBlock,
    StockOrder,
    TriageAssessment,
)

EPISODE_STATES = [
    "intake",
    "triage",
    "consult",
    "admitted",
    "diagnostics",
    "awaiting_results",
    "awaiting_consent",
    "scheduled",
    "prep",
    "anaesthesia",
    "procedure",
    "recovery",
    "ward",
    "icu",
    "discharge_ready",
    "discharged",
    "closed",
]

ALLOWED_TRANSITIONS = {
    "intake": ["triage", "consult", "admitted", "closed"],
    "triage": ["consult", "admitted", "diagnostics", "closed"],
    "consult": ["admitted", "diagnostics", "awaiting_consent", "discharge_ready", "closed"],
    "admitted": ["diagnostics", "awaiting_consent", "scheduled", "ward", "icu"],
    "diagnostics": ["awaiting_results", "awaiting_consent", "scheduled", "ward", "icu"],
    "awaiting_results": ["awaiting_consent", "scheduled", "ward", "icu", "discharge_ready"],
    "awaiting_consent": ["scheduled", "ward", "icu", "discharge_ready"],
    "scheduled": ["prep", "anaesthesia", "procedure", "ward", "icu"],
    "prep": ["anaesthesia", "procedure", "scheduled"],
    "anaesthesia": ["procedure", "recovery"],
    "procedure": ["recovery", "ward", "icu"],
    "recovery": ["ward", "icu", "discharge_ready"],
    "ward": ["diagnostics", "scheduled", "icu", "discharge_ready"],
    "icu": ["diagnostics", "scheduled", "ward", "discharge_ready"],
    "discharge_ready": ["discharged", "ward", "icu"],
    "discharged": ["closed"],
    "closed": [],
}

STATE_OWNERS = {
    "intake": "admin",
    "triage": "clinician",
    "consult": "clinician",
    "admitted": "clinician",
    "diagnostics": "clinician",
    "awaiting_results": "clinician",
    "awaiting_consent": "clinician",
    "scheduled": "ops_manager",
    "prep": "nurse",
    "anaesthesia": "anaesthetist",
    "procedure": "clinician",
    "recovery": "nurse",
    "ward": "nurse",
    "icu": "nurse",
    "discharge_ready": "clinician",
    "discharged": "admin",
    "closed": "admin",
}


def _open_triage(session: Session, episode_id: int):
    return session.exec(select(TriageAssessment).where(TriageAssessment.episode_id == episode_id, TriageAssessment.status != "resolved")).all()


def _open_ethics(session: Session, episode_id: int):
    return session.exec(select(EthicsFlag).where(EthicsFlag.episode_id == episode_id, EthicsFlag.status != "resolved")).all()


def _open_decisions(session: Session, episode_id: int):
    return session.exec(select(DecisionRecord).where(DecisionRecord.episode_id == episode_id, DecisionRecord.status != "resolved")).all()


def _open_blockers(session: Session, episode_id: int):
    return session.exec(select(Blocker).where(Blocker.episode_id == episode_id, Blocker.status != "resolved")).all()


def _open_pharmacy(session: Session, episode_id: int):
    return session.exec(select(PharmacyRequest).where(PharmacyRequest.episode_id == episode_id, PharmacyRequest.status != "complete")).all()


def _open_stock(session: Session, episode_id: int):
    return session.exec(select(StockOrder).where(StockOrder.episode_id == episode_id, StockOrder.status != "complete")).all()


def _open_results(session: Session, episode_id: int):
    return session.exec(select(ResultReview).where(ResultReview.episode_id == episode_id, ResultReview.status == "pending_review")).all()


def _open_owner_comms(session: Session, episode_id: int):
    return session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.episode_id == episode_id, OwnerCommsRequirement.status != "complete")).all()


def _discharge_blocks(session: Session, episode_id: int):
    return session.exec(select(DischargeReadiness).where(DischargeReadiness.episode_id == episode_id)).all()


def _schedule_blocks(session: Session, episode_id: int):
    return session.exec(select(ScheduleBlock).where(ScheduleBlock.episode_id == episode_id)).all()


def transition_guard(session: Session, episode: Episode, target_state: str):
    current = episode.current_phase or "intake"
    hard = []
    warnings = []

    if current not in EPISODE_STATES:
        hard.append({"type": "unknown_current_state", "detail": f"Unknown current state {current}", "owner_role": "ops_manager"})
    if target_state not in EPISODE_STATES:
        hard.append({"type": "unknown_target_state", "detail": f"Unknown target state {target_state}", "owner_role": "ops_manager"})
    if target_state not in ALLOWED_TRANSITIONS.get(current, []):
        hard.append({"type": "blocked_transition", "detail": f"Cannot move {current} → {target_state}", "owner_role": STATE_OWNERS.get(current, "ops_manager")})

    episode_id = episode.id
    if not episode_id:
        hard.append({"type": "missing_episode_id", "detail": "Episode has no database id", "owner_role": "ops_manager"})
        return _guard_result(current, target_state, hard, warnings)

    ethics = _open_ethics(session, episode_id)
    blockers = _open_blockers(session, episode_id)
    decisions = _open_decisions(session, episode_id)
    triage = _open_triage(session, episode_id)
    pharmacy = _open_pharmacy(session, episode_id)
    stock = _open_stock(session, episode_id)
    results = _open_results(session, episode_id)
    comms = _open_owner_comms(session, episode_id)
    discharge = _discharge_blocks(session, episode_id)
    schedule = _schedule_blocks(session, episode_id)

    if target_state in {"admitted", "diagnostics", "scheduled", "prep", "anaesthesia", "procedure"}:
        for item in ethics:
            hard.append({"type": "ethics_open", "detail": item.detail, "owner_role": item.owner_role})
        red_triage = [x for x in triage if x.urgency == "red"]
        for item in red_triage:
            hard.append({"type": "red_triage_unresolved", "detail": item.reasoning, "owner_role": item.assigned_owner_role})

    if target_state in {"scheduled", "prep", "anaesthesia", "procedure"}:
        if not schedule:
            hard.append({"type": "no_schedule_blocks", "detail": "No schedule blocks exist for this episode", "owner_role": "ops_manager"})
        for item in blockers:
            hard.append({"type": "open_blocker", "detail": item.detail, "owner_role": item.owner_role})
        for item in pharmacy:
            hard.append({"type": "pharmacy_open", "detail": f"{item.medication_name} is {item.status}", "owner_role": item.owner_role})
        for item in stock:
            hard.append({"type": "stock_open", "detail": f"{item.item_name}: {item.reason}", "owner_role": "nurse"})

    if target_state in {"procedure", "recovery"}:
        anaesthesia_blocks = [x for x in schedule if x.block_type == "anaesthesia"]
        procedure_blocks = [x for x in schedule if x.block_type == "procedure"]
        if target_state == "procedure" and not procedure_blocks:
            hard.append({"type": "missing_procedure_block", "detail": "No procedure block exists", "owner_role": "ops_manager"})
        if target_state == "procedure" and anaesthesia_blocks and any(not x.assigned_staff_member_id for x in anaesthesia_blocks):
            hard.append({"type": "anaesthesia_unassigned", "detail": "Anaesthesia block has no assigned staff", "owner_role": "anaesthetist"})

    if target_state in {"discharge_ready", "discharged"}:
        for item in results:
            hard.append({"type": "results_pending", "detail": item.required_action or f"{item.result_type} pending review", "owner_role": item.review_owner})
        for item in comms:
            warnings.append({"type": "owner_comms_due", "detail": item.required_message, "owner_role": item.owner_role})
        if discharge:
            for item in discharge:
                if item.readiness_state != "ready" or item.status != "complete":
                    hard.append({"type": "discharge_not_ready", "detail": item.blocker_summary or "Discharge readiness incomplete", "owner_role": item.owner_role})
        else:
            hard.append({"type": "missing_discharge_readiness", "detail": "No discharge readiness record exists", "owner_role": "clinician"})

    if target_state == "closed":
        if current != "discharged":
            hard.append({"type": "cannot_close_before_discharge", "detail": "Episode must be discharged before closure", "owner_role": "admin"})

    return _guard_result(current, target_state, hard, warnings)


def _guard_result(current: str, target: str, hard: list[dict], warnings: list[dict]):
    return {
        "current_state": current,
        "target_state": target,
        "allowed_by_graph": target in ALLOWED_TRANSITIONS.get(current, []),
        "can_transition": len(hard) == 0,
        "hard_failures": hard,
        "warnings": warnings,
        "next_action": hard[0] if hard else warnings[0] if warnings else None,
        "owner_role": STATE_OWNERS.get(target, "ops_manager"),
    }


def transition_episode(session: Session, episode_ref: str, target_state: str, actor_name: str, reason: str = ""):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        return {"ok": False, "error": "episode_not_found", "episode_ref": episode_ref}

    guard = transition_guard(session, episode, target_state)
    if not guard["can_transition"]:
        session.add(AuditEvent(
            actor_name=actor_name,
            action="episode_transition_blocked",
            entity_type="episode",
            entity_id=episode.id or 0,
            summary=f"Blocked {episode.episode_ref}: {guard['current_state']} → {target_state}. {guard['hard_failures'][0]['detail'] if guard['hard_failures'] else 'blocked'}",
        ))
        session.commit()
        return {"ok": False, "episode_ref": episode_ref, "guard": guard}

    previous = episode.current_phase
    episode.current_phase = target_state
    episode.status = "closed" if target_state == "closed" else "active"
    if target_state in {"ward", "icu", "recovery"}:
        episode.current_section_name = target_state.upper() if target_state == "icu" else target_state
    session.add(episode)
    session.add(AuditEvent(
        actor_name=actor_name,
        action="episode_transitioned",
        entity_type="episode",
        entity_id=episode.id or 0,
        summary=f"{episode.episode_ref}: {previous} → {target_state}. {reason}",
    ))
    session.commit()
    session.refresh(episode)
    return {"ok": True, "episode_ref": episode_ref, "previous_state": previous, "new_state": target_state, "guard": guard}


def state_machine_spec():
    return {
        "states": EPISODE_STATES,
        "allowed_transitions": ALLOWED_TRANSITIONS,
        "state_owners": STATE_OWNERS,
        "invariant": "Episodes must move through guarded states; dashboard flow must not rely on loose labels.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
