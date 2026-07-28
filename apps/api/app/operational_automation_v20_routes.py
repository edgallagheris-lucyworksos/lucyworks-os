from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState
from app.models import WorkItem
from app.operational_automation_v20_models import AutomationDecisionV20


router = APIRouter(prefix="/api/v20/automation", tags=["governed-operational-automation-v20"])

AUTOMATION_ROLES = (
    "admin",
    "ops_manager",
    "clinician",
    "clinical_director",
    "governance_lead",
    "hospital_director",
    "senior_clinician",
    "supervisor",
    "nurse",
)
CLINICAL_TRIGGER_TYPES = {"observation", "critical_result"}
SUPPORTED_TRIGGER_TYPES = CLINICAL_TRIGGER_TYPES | {"operational_delay", "evidence_gap"}
EVIDENCE_GAP_RULES = {
    "consent": {
        "title": "Resolve consent evidence gap",
        "ownerRole": "clinician",
        "urgency": "red",
        "dueMinutes": 10,
        "category": "consent_evidence",
    },
    "estimate_authority": {
        "title": "Resolve estimate or financial-authority gap",
        "ownerRole": "ops_manager",
        "urgency": "amber",
        "dueMinutes": 30,
        "category": "financial_authority",
    },
    "handover": {
        "title": "Complete accountable handover",
        "ownerRole": "clinician",
        "urgency": "red",
        "dueMinutes": 10,
        "category": "handover",
    },
    "result_review": {
        "title": "Complete outstanding result review",
        "ownerRole": "clinician",
        "urgency": "red",
        "dueMinutes": 10,
        "category": "result_review",
    },
    "discharge": {
        "title": "Complete discharge evidence",
        "ownerRole": "clinician",
        "urgency": "amber",
        "dueMinutes": 30,
        "category": "discharge_evidence",
    },
    "owner_communication": {
        "title": "Update owner and record communication",
        "ownerRole": "clinician",
        "urgency": "amber",
        "dueMinutes": 30,
        "category": "owner_communication",
    },
}


class AutomationEvaluate(BaseModel):
    episodeRef: str = PydanticField(min_length=1, max_length=160)
    triggerType: str = PydanticField(min_length=1, max_length=80)
    triggerRef: str = PydanticField(min_length=1, max_length=200)
    facts: dict[str, Any] = PydanticField(default_factory=dict)
    commitActions: bool = False
    reason: str = PydanticField(min_length=8, max_length=2000)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def clean_text(value: Any, *, maximum: int = 500) -> str:
    return " ".join(str(value or "").split())[:maximum]


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def as_int(value: Any, *, minimum: int = 0, maximum: int = 10080) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="numeric trigger fact is invalid")
    return max(minimum, min(parsed, maximum))


def require_episode(session: Session, episode_ref: str) -> CanonicalEpisodeState:
    episode = session.exec(
        select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    if not episode.patient_ref:
        raise HTTPException(status_code=409, detail="canonical episode is not linked to a patient")
    return episode


def action(
    code: str,
    *,
    title: str,
    owner_role: str,
    urgency: str,
    due_minutes: int,
    category: str,
    description: str,
    section_name: str | None,
) -> dict[str, Any]:
    return {
        "actionCode": code,
        "title": title,
        "ownerRole": owner_role,
        "urgency": urgency,
        "dueMinutes": due_minutes,
        "category": category,
        "description": description,
        "sectionName": section_name,
        "humanAuthorityRequired": True,
        "permittedEffect": "create_owned_review_or_coordination_work",
        "forbiddenEffects": [
            "diagnosis",
            "prognosis",
            "prescription",
            "dose_change",
            "medication_administration",
            "admission",
            "discharge",
            "clinical_phase_transition",
            "automatic_rescheduling",
            "evidence_completion",
        ],
    }


def evaluate_trigger(
    episode: CanonicalEpisodeState,
    trigger_type: str,
    trigger_ref: str,
    facts: dict[str, Any],
) -> list[dict[str, Any]]:
    area = episode.current_area_ref
    detail = clean_text(facts.get("detail") or facts.get("summary") or trigger_ref)

    if trigger_type == "observation":
        level = clean_text(facts.get("concernLevel"), maximum=20).lower()
        if level not in {"green", "amber", "red"}:
            raise HTTPException(status_code=422, detail="observation concernLevel must be green, amber or red")
        if level == "green":
            return []
        due = 5 if level == "red" else 30
        return [action(
            f"observation-{level}-review",
            title=f"{level.upper()} observation requires clinical review",
            owner_role="clinician",
            urgency=level,
            due_minutes=due,
            category="clinical_observation_review",
            description=(
                f"Review recorded observation {trigger_ref}: {detail}. "
                "This task is an escalation only; the responsible veterinary professional must assess and decide."
            ),
            section_name=area,
        )]

    if trigger_type == "critical_result":
        if not as_bool(facts.get("critical")) or as_bool(facts.get("acknowledged")):
            return []
        overdue = as_bool(facts.get("overdue"))
        return [action(
            "critical-result-overdue" if overdue else "critical-result-review",
            title="Overdue critical result acknowledgement" if overdue else "Critical result requires acknowledgement",
            owner_role="clinician",
            urgency="red",
            due_minutes=0 if overdue else 10,
            category="critical_result_review",
            description=(
                f"Review and acknowledge recorded critical result {trigger_ref}: {detail}. "
                "Automation has not interpreted the result or recorded acknowledgement."
            ),
            section_name=area,
        )]

    if trigger_type == "operational_delay":
        delay_minutes = as_int(facts.get("delayMinutes"))
        if delay_minutes < 15:
            return []
        urgency = "red" if delay_minutes >= 60 else "amber"
        proposals = [action(
            "delay-coordination-review",
            title=f"Coordinate {delay_minutes}-minute operational delay",
            owner_role="ops_manager",
            urgency=urgency,
            due_minutes=5 if urgency == "red" else 15,
            category="operational_delay",
            description=(
                f"Review delay or overrun {trigger_ref}: {detail}. Check rooms, staff, dependencies and the next safe action. "
                "No schedule or patient state has been changed automatically."
            ),
            section_name=area,
        )]
        if delay_minutes >= 30:
            proposals.append(action(
                "delay-owner-communication",
                title="Review whether owner communication is required",
                owner_role="clinician",
                urgency="amber",
                due_minutes=30,
                category="owner_communication",
                description=(
                    f"Recorded delay {trigger_ref} has reached {delay_minutes} minutes. "
                    "Decide whether an owner update is required and record any communication."
                ),
                section_name=area,
            ))
        return proposals

    if trigger_type == "evidence_gap":
        raw_gaps = facts.get("gaps")
        if not isinstance(raw_gaps, list):
            raise HTTPException(status_code=422, detail="evidence_gap facts.gaps must be a list")
        gaps = list(dict.fromkeys(clean_text(value, maximum=80).lower() for value in raw_gaps))[:10]
        unknown = [value for value in gaps if value not in EVIDENCE_GAP_RULES]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unsupported evidence gaps: {', '.join(unknown)}")
        proposals: list[dict[str, Any]] = []
        for gap in gaps:
            rule = EVIDENCE_GAP_RULES[gap]
            proposals.append(action(
                f"evidence-gap-{gap}",
                title=rule["title"],
                owner_role=rule["ownerRole"],
                urgency=rule["urgency"],
                due_minutes=rule["dueMinutes"],
                category=rule["category"],
                description=(
                    f"Resolve recorded {gap.replace('_', ' ')} gap from {trigger_ref}. "
                    "Automation cannot mark the evidence complete; an authorised user must record and verify it."
                ),
                section_name=area,
            ))
        return proposals

    raise HTTPException(status_code=422, detail="unsupported automation trigger type")


def fingerprint_for(
    episode_ref: str,
    patient_ref: str,
    trigger_type: str,
    trigger_ref: str,
    facts: dict[str, Any],
    proposals: list[dict[str, Any]],
) -> str:
    canonical = json.dumps(
        {
            "episodeRef": episode_ref,
            "patientRef": patient_ref,
            "triggerType": trigger_type,
            "triggerRef": trigger_ref,
            "facts": facts,
            "actions": [row["actionCode"] for row in proposals],
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decision_dict(row: AutomationDecisionV20) -> dict[str, Any]:
    return row.model_dump(mode="json")


def work_dict(row: WorkItem) -> dict[str, Any]:
    return row.model_dump(mode="json")


def record_event(
    session: Session,
    auth: AuthContext,
    decision: AutomationDecisionV20,
    *,
    risk: str,
) -> str:
    event, _ = create_evidence_event(
        session,
        event_type="v20_operational_automation_decision",
        action=decision.outcome,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        patient_case_id=decision.patient_ref,
        referral_episode_id=decision.episode_ref,
        previous_state={},
        new_state=decision_dict(decision),
        reason=decision.reason,
        justification="Deterministic governed escalation into accountable human-owned work",
        evidence_links=[
            {"type": "automation_decision_v20", "id": decision.decision_ref},
            *[
                {"type": "work_item", "id": str(work_id)}
                for work_id in decision.created_work_item_ids
            ],
        ],
        compliance_domain="clinical_operations",
        risk_level=risk,
        source_module="operational-automation-v20",
        source_record_ref=decision.decision_ref,
        correlation_id=decision.episode_ref,
        entity_type="automation_decision_v20",
        entity_id=decision.decision_ref,
        idempotency_key=f"v20:automation:{decision.decision_ref}:{decision.outcome}",
    )
    return event.event_ref


def ensure_commit_authority(auth: AuthContext, trigger_type: str) -> None:
    if trigger_type in CLINICAL_TRIGGER_TYPES and auth.role not in CLINICAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail="a verified clinical role is required to commit observation or critical-result escalation",
        )


@router.post("/evaluate")
def evaluate_automation(
    payload: AutomationEvaluate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*AUTOMATION_ROLES)),
):
    trigger_type = payload.triggerType.strip().lower()
    if trigger_type not in SUPPORTED_TRIGGER_TYPES:
        raise HTTPException(status_code=422, detail="unsupported automation trigger type")
    if payload.commitActions:
        ensure_commit_authority(auth, trigger_type)

    episode = require_episode(session, payload.episodeRef.strip())
    patient_ref = str(episode.patient_ref)
    trigger_ref = payload.triggerRef.strip()
    facts = json.loads(json.dumps(payload.facts, default=str))
    proposals = evaluate_trigger(episode, trigger_type, trigger_ref, facts)
    fingerprint = fingerprint_for(
        episode.episode_ref,
        patient_ref,
        trigger_type,
        trigger_ref,
        facts,
        proposals,
    )

    existing = None
    if payload.commitActions:
        existing = session.exec(
            select(AutomationDecisionV20)
            .where(AutomationDecisionV20.action_fingerprint == fingerprint)
            .where(AutomationDecisionV20.committed == True)  # noqa: E712
            .order_by(AutomationDecisionV20.created_at.desc())
        ).first()

    now = utc_now()
    decision = AutomationDecisionV20(
        decision_ref=new_ref("autodecision-v20"),
        action_fingerprint=fingerprint,
        episode_ref=episode.episode_ref,
        patient_ref=patient_ref,
        trigger_type=trigger_type,
        trigger_ref=trigger_ref,
        trigger_facts=facts,
        proposals=proposals,
        commit_requested=payload.commitActions,
        committed=bool(payload.commitActions and proposals),
        replayed=bool(existing),
        outcome=(
            "replayed"
            if existing
            else "committed"
            if payload.commitActions and proposals
            else "no_action"
            if not proposals
            else "previewed"
        ),
        created_work_item_ids=list(existing.created_work_item_ids) if existing else [],
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        reason=payload.reason.strip(),
    )
    session.add(decision)
    session.flush()

    created_work: list[WorkItem] = []
    if payload.commitActions and proposals and not existing:
        for proposal in proposals:
            source = f"automation-v20:{fingerprint}:{proposal['actionCode']}"
            duplicate = session.exec(
                select(WorkItem)
                .where(WorkItem.source == source)
                .where(WorkItem.linked_episode_ref == episode.episode_ref)
            ).first()
            if duplicate:
                created_work.append(duplicate)
                continue
            work = WorkItem(
                title=proposal["title"],
                input_type="governed_automation",
                source=source,
                category=proposal["category"],
                description=proposal["description"],
                urgency=proposal["urgency"],
                owner_role=proposal["ownerRole"],
                section_name=proposal.get("sectionName"),
                patient_location_label=episode.current_area_ref,
                linked_patient_name=episode.patient_name,
                linked_episode_ref=episode.episode_ref,
                status="new",
                due_at=now + timedelta(minutes=int(proposal["dueMinutes"])),
            )
            session.add(work)
            session.flush()
            created_work.append(work)
        decision.created_work_item_ids = [int(row.id) for row in created_work if row.id is not None]
    elif existing and existing.created_work_item_ids:
        created_work = session.exec(
            select(WorkItem).where(WorkItem.id.in_(existing.created_work_item_ids))
        ).all()

    risk = "red" if any(row["urgency"] == "red" for row in proposals) else "amber"
    decision.evidence_event_ref = record_event(session, auth, decision, risk=risk)
    session.add(decision)
    session.commit()
    session.refresh(decision)
    for row in created_work:
        session.refresh(row)

    return {
        "decision": decision_dict(decision),
        "context": {
            "episodeRef": episode.episode_ref,
            "patientRef": patient_ref,
            "patientName": episode.patient_name,
            "currentAreaRef": episode.current_area_ref,
        },
        "proposals": proposals,
        "workItems": [work_dict(row) for row in created_work],
        "replayProtected": bool(existing),
        "safetyBoundary": {
            "automationMay": ["create owned review work", "create coordination work", "record escalation evidence"],
            "automationMayNot": [
                "diagnose",
                "prescribe",
                "calculate medication outside v18",
                "administer medication",
                "acknowledge a result",
                "complete evidence",
                "reschedule automatically",
                "admit or discharge",
                "change clinical phase",
            ],
        },
    }


@router.get("/episodes/{episode_ref}")
def episode_automation_history(
    episode_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    episode = require_episode(session, episode_ref)
    decisions = session.exec(
        select(AutomationDecisionV20)
        .where(AutomationDecisionV20.episode_ref == episode.episode_ref)
        .order_by(AutomationDecisionV20.created_at.desc())
    ).all()
    work = session.exec(
        select(WorkItem)
        .where(WorkItem.linked_episode_ref == episode.episode_ref)
        .where(WorkItem.source.startswith("automation-v20:"))
        .order_by(WorkItem.created_at.desc())
    ).all()
    return {
        "context": {
            "episodeRef": episode.episode_ref,
            "patientRef": episode.patient_ref,
            "patientName": episode.patient_name,
        },
        "decisions": [decision_dict(row) for row in decisions],
        "workItems": [work_dict(row) for row in work],
    }
