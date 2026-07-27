from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated
from app.database import get_session
from app.detailed_hospital_models import (
    AnaesthesiaChartV8,
    ClinicalDocumentV8,
    CommunicationEventV8,
    EstimateV8,
    InpatientCarePlanV8,
    OwnerAccountV8,
    PatientClinicalRecordV8,
    PatientOwnerLinkV8,
    ProcedureRecordV8,
)
from app.hospital_command_models import (
    ConsentAuthorisationV9,
    EpisodeClosureV9,
    EpisodeHandoverV9,
    ReferralIntakeV9,
)
from app.hospital_command_routes import ALLOWED_TRANSITIONS, PHASES, evaluate_guard, row_dict
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.hospital_ops_service import block_dict, normalise_dt
from app.referral_identity_v12_models import ReferralTriageV12

router = APIRouter(prefix="/api/v13/flow", tags=["end-to-end-hospital-flow-v13"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest(rows: list[Any], attribute: str = "created_at") -> Any | None:
    if not rows:
        return None
    return max(rows, key=lambda row: normalise_dt(getattr(row, attribute)))


def _patient_identity(session: Session, episode: CanonicalEpisodeState) -> dict[str, Any]:
    patient = session.exec(
        select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == episode.patient_ref)
    ).first() if episode.patient_ref else None
    links = session.exec(
        select(PatientOwnerLinkV8).where(
            PatientOwnerLinkV8.patient_ref == episode.patient_ref,
            PatientOwnerLinkV8.active == True,  # noqa: E712
        )
    ).all() if episode.patient_ref else []
    owner_refs = [row.owner_ref for row in links]
    owners = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.owner_ref.in_(owner_refs))).all() if owner_refs else []
    owner_by_ref = {row.owner_ref: row for row in owners}
    return {
        "patient": row_dict(patient) if patient else None,
        "owners": [
            {
                "link": row_dict(link),
                "owner": row_dict(owner_by_ref[link.owner_ref]) if link.owner_ref in owner_by_ref else None,
            }
            for link in links
        ],
        "hasDecisionAuthority": any(row.decision_authority for row in links),
    }


def _active_block(blocks: list[OperationalBlock]) -> OperationalBlock | None:
    now = utc_now()
    active = [
        row for row in blocks
        if row.status not in {"cancelled", "completed"} and normalise_dt(row.ends_at) >= now
    ]
    if not active:
        return None
    return min(active, key=lambda row: normalise_dt(row.starts_at))


def _stage(code: str, label: str, status: str, detail: str, owner_role: str, refs: list[str] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "status": status,
        "detail": detail,
        "ownerRole": owner_role,
        "relatedRefs": refs or [],
    }


def _recommended_transition(episode: CanonicalEpisodeState, guards: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    phase_index = {phase: index for index, phase in enumerate(PHASES)}
    candidates = sorted(
        guards.values(),
        key=lambda item: phase_index.get(item["targetPhase"], 999),
    )
    ready = [item for item in candidates if item["canTransition"]]
    selected = ready[0] if ready else candidates[0] if candidates else None
    if not selected:
        return None
    return {
        "targetPhase": selected["targetPhase"],
        "canTransition": selected["canTransition"],
        "targetOwnerRole": selected["targetOwnerRole"],
        "blockers": selected["blockers"],
        "warnings": selected["warnings"],
        "reason": (
            f"Move {episode.patient_name} from {episode.phase} to {selected['targetPhase']}"
            if selected["canTransition"]
            else f"Clear the blockers preventing {selected['targetPhase']}"
        ),
    }


@router.get("/episodes/{episode_ref}")
def case_control(
    episode_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    episode = session.exec(
        select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")

    referral = session.exec(
        select(ReferralIntakeV9).where(ReferralIntakeV9.episode_ref == episode_ref)
    ).first()
    triage_rows = session.exec(
        select(ReferralTriageV12).where(ReferralTriageV12.episode_ref == episode_ref)
    ).all()
    triage = _latest(triage_rows, "updated_at")
    blocks = session.exec(
        select(OperationalBlock).where(OperationalBlock.episode_ref == episode_ref).order_by(OperationalBlock.starts_at)
    ).all()
    handovers = session.exec(
        select(EpisodeHandoverV9).where(EpisodeHandoverV9.episode_ref == episode_ref).order_by(EpisodeHandoverV9.created_at.desc())
    ).all()
    consents = session.exec(
        select(ConsentAuthorisationV9).where(ConsentAuthorisationV9.episode_ref == episode_ref).order_by(ConsentAuthorisationV9.created_at.desc())
    ).all()
    procedures = session.exec(
        select(ProcedureRecordV8).where(ProcedureRecordV8.episode_ref == episode_ref)
    ).all()
    anaesthesia = session.exec(
        select(AnaesthesiaChartV8).where(AnaesthesiaChartV8.episode_ref == episode_ref)
    ).all()
    care_plans = session.exec(
        select(InpatientCarePlanV8).where(InpatientCarePlanV8.episode_ref == episode_ref)
    ).all()
    documents = session.exec(
        select(ClinicalDocumentV8).where(ClinicalDocumentV8.episode_ref == episode_ref)
    ).all()
    communications = session.exec(
        select(CommunicationEventV8).where(CommunicationEventV8.episode_ref == episode_ref)
    ).all()
    estimates = session.exec(
        select(EstimateV8).where(EstimateV8.episode_ref == episode_ref)
    ).all()
    closure = session.exec(
        select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == episode_ref)
    ).first()

    next_targets = sorted(ALLOWED_TRANSITIONS.get(episode.phase, set()))
    guards = {target: evaluate_guard(session, episode, target) for target in next_targets}
    all_blockers = [blocker for guard in guards.values() for blocker in guard["blockers"]]
    blocker_groups: dict[str, list[dict[str, Any]]] = {}
    for blocker in all_blockers:
        blocker_groups.setdefault(blocker["ownerRole"], [])
        if blocker not in blocker_groups[blocker["ownerRole"]]:
            blocker_groups[blocker["ownerRole"]].append(blocker)

    current_block = _active_block(blocks)
    active_consents = [row for row in consents if row.status == "active"]
    latest_handover = handovers[0] if handovers else None
    discharge_docs = [row for row in documents if row.document_type in {"discharge", "discharge_summary", "owner_instructions"}]
    owner_comms = [row for row in communications if row.audience == "owner" and row.direction == "outbound"]
    active_plans = [row for row in care_plans if row.status == "active"]

    stages = [
        _stage(
            "identity", "Patient and owner identity",
            "complete" if episode.patient_ref else "blocked",
            "Patient identity is linked to the canonical episode" if episode.patient_ref else "No patient identity is linked",
            "admin", [episode.patient_ref] if episode.patient_ref else [],
        ),
        _stage(
            "referral", "Referral decision",
            "complete" if referral and referral.status == "accepted" else "attention",
            f"Referral is {referral.status}" if referral else "Governed referral record is missing",
            "clinician", [referral.referral_ref] if referral else [],
        ),
        _stage(
            "triage", "Triage and response SLA",
            "complete" if triage and triage.status in {"acknowledged", "completed"} else "attention",
            f"{triage.category} triage · {triage.status}" if triage else "Triage has not been recorded",
            "clinician", [triage.triage_ref] if triage else [],
        ),
        _stage(
            "schedule", "Place, time and lead",
            "complete" if current_block and current_block.lead_staff_ref else "attention" if current_block else "blocked",
            (
                f"{current_block.area_name} · {normalise_dt(current_block.starts_at).isoformat()}"
                if current_block else "No active operational block"
            ),
            "ops_manager", [current_block.block_ref] if current_block else [],
        ),
        _stage(
            "consent", "Authority and consent",
            "complete" if active_consents else "attention",
            f"{len(active_consents)} active consent record(s)" if active_consents else "No active episode consent",
            "clinician", [row.consent_ref for row in active_consents],
        ),
        _stage(
            "handover", "Accountable handover",
            "complete" if latest_handover and latest_handover.status == "acknowledged" else "attention",
            f"Latest handover is {latest_handover.status}" if latest_handover else "No handover recorded",
            episode.owner_role, [latest_handover.handover_ref] if latest_handover else [],
        ),
        _stage(
            "discharge", "Discharge and closure",
            "complete" if closure and closure.status in {"approved", "completed"} else "attention",
            (
                f"Closure is {closure.status}"
                if closure else f"Documents {len(discharge_docs)} · owner communications {len(owner_comms)} · active plans {len(active_plans)}"
            ),
            "clinician", [closure.closure_ref] if closure else [],
        ),
    ]

    return {
        "generatedAt": utc_now().isoformat(),
        "requestedBy": auth.subject,
        "episode": row_dict(episode),
        "identity": _patient_identity(session, episode),
        "referral": row_dict(referral) if referral else None,
        "triage": row_dict(triage) if triage else None,
        "currentBlock": block_dict(current_block) if current_block else None,
        "blocks": [block_dict(row) for row in blocks],
        "stages": stages,
        "nextTransitions": guards,
        "recommendedAction": _recommended_transition(episode, guards),
        "blockersByOwner": blocker_groups,
        "handover": row_dict(latest_handover) if latest_handover else None,
        "activeConsents": [row_dict(row) for row in active_consents],
        "clinicalState": {
            "procedures": [row_dict(row) for row in procedures],
            "anaesthesia": [row_dict(row) for row in anaesthesia],
            "activeCarePlans": [row_dict(row) for row in active_plans],
            "dischargeDocuments": [row_dict(row) for row in discharge_docs],
            "ownerCommunications": [row_dict(row) for row in owner_comms],
            "estimates": [row_dict(row) for row in estimates],
            "closure": row_dict(closure) if closure else None,
        },
    }
