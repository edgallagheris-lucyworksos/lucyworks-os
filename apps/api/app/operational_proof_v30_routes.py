from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import get_session
from app.evidence_event_models import EvidenceEvent
from app.evidence_service import create_evidence_event
from app.hospital_command_models import EpisodeClosureV9, EpisodeHandoverV9, EpisodeTransitionV9, ReferralIntakeV9
from app.hospital_ops_models import BoardChangeEvent, CanonicalEpisodeState, OperationalBlock
from app.operational_proof_v30_models import (
    MobileAcceptanceV30,
    OperationalProofRunV30,
    OperationalProofScenarioV30,
    OperationalProofStepV30,
)
from app.role_queue_routes import queue_for_role

router = APIRouter(prefix="/api/v30/operational-proof", tags=["operational-proof-v30"])
WRITE_ROLES = ("hospital_director", "clinical_director", "ops_manager", "senior_clinician", "supervisor")
SCENARIOS = {
    "emergency_full_schedule": "Emergency insertion is visible, governed and does not silently overwrite planned care.",
    "theatre_imaging_overrun": "Overrun creates visible downstream displacement or conflict.",
    "staff_unavailable": "Unavailable assigned staff produces an owned reassignment action.",
    "unacknowledged_handover": "Offered handover remains visible to the receiving role until acknowledged.",
    "overdue_critical_result": "Critical result review remains visible with urgency and accountable owner.",
    "discharge_medication_or_comms_block": "Discharge remains blocked until medication and owner communication evidence is complete.",
    "stale_concurrent_update": "Stale version is rejected without overwriting the current episode state.",
    "duplicate_patient_identity": "Duplicate candidate is routed to explicit identity reconciliation before canonical attachment.",
}
JOURNEY_STEPS = [
    ("referral", "Referral received and clinically accepted", "Referral Intake"),
    ("identity", "Canonical patient and episode identity linked", "Patient Command"),
    ("triage", "Triage transition recorded", "Patient Command"),
    ("consult", "Clinical acceptance and consult recorded", "Care Brief"),
    ("consent", "Owner authority and consent gate satisfied", "Episode Command"),
    ("schedule", "Operational block or explicit unplaced status visible", "Hospital Today"),
    ("handover", "Accountable handover visible and acknowledged where required", "Role Queue"),
    ("discharge", "Discharge readiness, document and owner communication gates satisfied", "Care Brief"),
    ("closure", "Episode closure completed", "Episode Command"),
    ("board", "Canonical episode and changes visible on the master board", "Hospital Today"),
    ("queues", "Canonical work visible to the accountable role queue", "Role Queues"),
    ("evidence", "Verified actor evidence exists across the journey", "Evidence"),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def require_run(session: Session, run_ref: str, *, lock: bool = False) -> OperationalProofRunV30:
    query = select(OperationalProofRunV30).where(OperationalProofRunV30.run_ref == run_ref)
    if lock and session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="operational proof run not found")
    return row


def record_evidence(
    session: Session,
    *,
    auth: AuthContext,
    run_ref: str,
    action: str,
    new_state: Any,
    reason: str,
    risk: str = "amber",
    entity_type: str = "operational_proof_run",
    entity_id: str | None = None,
) -> str:
    evidence, _ = create_evidence_event(
        session,
        event_type=f"v30_{action}",
        action=action.replace("_", " "),
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=new_state,
        reason=reason,
        compliance_domain="operations",
        risk_level=risk,
        source_module="operational-proof-demo-hospital-v30",
        source_record_ref=entity_id or run_ref,
        correlation_id=run_ref,
        entity_type=entity_type,
        entity_id=entity_id or run_ref,
        idempotency_key=f"v30:{action}:{entity_id or run_ref}:{new_state.get('version', new_state.get('status', 'event')) if isinstance(new_state, dict) else 'event'}",
    )
    return evidence.event_ref


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organisationRef: str
    siteRef: str
    premisesRef: str
    operationalDate: date = PydanticField(default_factory=date.today)
    episodeRef: str | None = None
    patientRef: str | None = None
    mode: str = "synthetic"
    reason: str


class EpisodeAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int
    episodeRef: str
    patientRef: str | None = None
    reason: str


class ScenarioRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed: dict[str, Any] = PydanticField(default_factory=dict)
    failureDetected: bool
    accountableOwnerVisible: bool
    nextActionVisible: bool
    evidenceVisible: bool
    urgentAccessPreserved: bool = True
    reason: str


class MobileAssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deviceLabel: str
    operatingSystem: str
    browser: str
    viewportWidth: int
    viewportHeight: int
    secureContext: bool
    online: bool
    touchCapable: bool
    microphoneAvailable: bool
    checks: dict[str, Any] = PydanticField(default_factory=dict)
    manualHardwareConfirmation: bool = False
    reason: str


class CompleteRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int
    reason: str


@router.get("/contract")
def contract(_: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {
        "journeySteps": [
            {"code": code, "title": title, "surface": surface}
            for code, title, surface in JOURNEY_STEPS
        ],
        "stressScenarios": [
            {"code": code, "expectedDetection": detail}
            for code, detail in SCENARIOS.items()
        ],
        "completionRule": "Connected journey, eight stress scenarios and mobile assessment must all be recorded. Real-device confirmation remains separately visible.",
        "externalBoundary": "Synthetic proof does not replace real hospital OIDC, vendor sandboxes, DPIA, penetration testing or hospital UAT.",
    }


@router.post("/runs")
def create_run(
    payload: RunCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    if payload.mode not in {"synthetic", "shadow"}:
        raise HTTPException(status_code=422, detail="operational proof mode must be synthetic or shadow")
    run = OperationalProofRunV30(
        run_ref=new_ref("proof-run"),
        organisation_ref=payload.organisationRef,
        site_ref=payload.siteRef,
        premises_ref=payload.premisesRef,
        operational_date=payload.operationalDate,
        episode_ref=payload.episodeRef,
        patient_ref=payload.patientRef,
        mode=payload.mode,
        status="running",
        current_stage="connected_journey",
        external_boundaries=[
            "real Android hardware confirmation",
            "real hospital identity provider",
            "real vendor sandbox schemas",
            "DPIA and penetration test",
            "hospital governance and UAT approval",
        ],
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
        created_by_role=auth.role,
    )
    session.add(run)
    for sequence, (code, title, surface) in enumerate(JOURNEY_STEPS, start=1):
        session.add(OperationalProofStepV30(
            step_ref=new_ref("proof-step"),
            run_ref=run.run_ref,
            sequence=sequence,
            step_code=code,
            title=title,
            surface=surface,
            expected=title,
            owner_role="ops_manager" if code in {"schedule", "board", "queues", "evidence"} else "clinician",
        ))
    for code, expected in SCENARIOS.items():
        session.add(OperationalProofScenarioV30(
            scenario_ref=new_ref("proof-scenario"),
            run_ref=run.run_ref,
            scenario_code=code,
            title=code.replace("_", " ").title(),
            expected_detection=expected,
        ))
    session.flush()
    run.evidence_event_ref = record_evidence(
        session,
        auth=auth,
        run_ref=run.run_ref,
        action="operational_proof_started",
        new_state=row_dict(run),
        reason=payload.reason,
        risk="green",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return {"run": row_dict(run), "contract": contract(auth)}


@router.post("/runs/{run_ref}/attach-episode")
def attach_episode(
    run_ref: str,
    payload: EpisodeAttach,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    run = require_run(session, run_ref, lock=True)
    if run.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale proof run", "currentVersion": run.version})
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == payload.episodeRef)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    if episode.premises_ref != run.premises_ref:
        raise HTTPException(status_code=409, detail="episode belongs to another premises")
    run.episode_ref = episode.episode_ref
    run.patient_ref = payload.patientRef or episode.patient_ref
    run.version += 1
    run.updated_at = utc_now()
    session.add(run)
    evidence_ref = record_evidence(
        session,
        auth=auth,
        run_ref=run_ref,
        action="proof_episode_attached",
        new_state={"episodeRef": run.episode_ref, "patientRef": run.patient_ref, "version": run.version},
        reason=payload.reason,
        risk="green",
    )
    session.commit()
    session.refresh(run)
    return {"run": row_dict(run), "evidenceRef": evidence_ref}


def _step_result(code: str, episode: CanonicalEpisodeState, context: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    referral = context["referral"]
    transitions = context["transitions"]
    closure = context["closure"]
    blocks = context["blocks"]
    handovers = context["handovers"]
    board_events = context["board_events"]
    evidence = context["evidence"]
    queue_hits = context["queue_hits"]
    phase_targets = {row.to_phase for row in transitions if row.status == "completed"}
    if code == "referral":
        passed = bool(referral and referral.status == "accepted")
        return passed, {"status": referral.status if referral else None}
    if code == "identity":
        passed = bool(episode.patient_ref and context["patient_ref"] == episode.patient_ref)
        return passed, {"episodeRef": episode.episode_ref, "patientRef": episode.patient_ref}
    if code == "triage":
        return "triage" in phase_targets, {"completedPhases": sorted(phase_targets)}
    if code == "consult":
        return "consult" in phase_targets, {"completedPhases": sorted(phase_targets)}
    if code == "consent":
        consent_evidence = [item for item in evidence if "consent" in item.event_type]
        return bool(consent_evidence), {"consentEvidenceCount": len(consent_evidence)}
    if code == "schedule":
        visible = bool(blocks) or episode.episode_ref in context["unplaced_refs"]
        return visible, {"blockCount": len(blocks), "explicitlyUnplaced": episode.episode_ref in context["unplaced_refs"]}
    if code == "handover":
        passed = bool(handovers) and not any(row.status == "offered" for row in handovers)
        return passed, {"handoverStatuses": [row.status for row in handovers]}
    if code == "discharge":
        passed = "discharge_ready" in phase_targets and "discharged" in phase_targets
        return passed, {"completedPhases": sorted(phase_targets)}
    if code == "closure":
        passed = bool(closure and closure.status == "completed" and episode.status == "closed")
        return passed, {"closureStatus": closure.status if closure else None, "episodeStatus": episode.status}
    if code == "board":
        passed = bool(context["board_episode_visible"] and board_events)
        return passed, {"boardEpisodeVisible": context["board_episode_visible"], "changeEventCount": len(board_events)}
    if code == "queues":
        passed = bool(queue_hits)
        return passed, {"queueHits": queue_hits}
    if code == "evidence":
        passed = len(evidence) >= max(4, len(transitions))
        return passed, {"evidenceCount": len(evidence), "transitionCount": len(transitions)}
    return False, {"error": "unknown proof step"}


@router.post("/runs/{run_ref}/evaluate")
def evaluate_run(
    run_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    run = require_run(session, run_ref, lock=True)
    if not run.episode_ref:
        raise HTTPException(status_code=409, detail="attach a canonical episode before evaluation")
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == run.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="attached canonical episode not found")
    referral = session.exec(select(ReferralIntakeV9).where(ReferralIntakeV9.episode_ref == run.episode_ref)).first()
    transitions = session.exec(select(EpisodeTransitionV9).where(EpisodeTransitionV9.episode_ref == run.episode_ref).order_by(EpisodeTransitionV9.created_at)).all()
    closure = session.exec(select(EpisodeClosureV9).where(EpisodeClosureV9.episode_ref == run.episode_ref)).first()
    handovers = session.exec(select(EpisodeHandoverV9).where(EpisodeHandoverV9.episode_ref == run.episode_ref)).all()
    blocks = session.exec(select(OperationalBlock).where(OperationalBlock.episode_ref == run.episode_ref)).all()
    board_events = session.exec(select(BoardChangeEvent).where(BoardChangeEvent.entity_ref == run.episode_ref)).all()
    evidence = session.exec(select(EvidenceEvent).where(EvidenceEvent.referral_episode_id == run.episode_ref)).all()
    canonical = [row_dict(item) for item in session.exec(
        select(CanonicalEpisodeState).where(CanonicalEpisodeState.premises_ref == run.premises_ref)
    ).all()]
    block_episode_refs = {item.episode_ref for item in blocks if item.episode_ref}
    unplaced_refs = {item["episode_ref"] for item in canonical if item["episode_ref"] not in block_episode_refs}
    queue_hits: list[str] = []
    for role in ("manager", "clinician", "nurse", "admin", "ward", "theatre", "imaging"):
        queue = queue_for_role(session, role)
        if any(item.get("episode_ref") == run.episode_ref for item in queue.get("canonical_episodes", [])):
            queue_hits.append(role)
    context = {
        "referral": referral,
        "transitions": transitions,
        "closure": closure,
        "blocks": blocks,
        "handovers": handovers,
        "board_events": board_events,
        "evidence": evidence,
        "queue_hits": queue_hits,
        "board_episode_visible": any(item["episode_ref"] == run.episode_ref for item in canonical),
        "unplaced_refs": unplaced_refs,
        "patient_ref": run.patient_ref,
    }
    steps = session.exec(select(OperationalProofStepV30).where(
        OperationalProofStepV30.run_ref == run_ref
    ).order_by(OperationalProofStepV30.sequence)).all()
    for step in steps:
        passed, observed = _step_result(step.step_code, episode, context)
        step.status = "pass" if passed else "blocked"
        step.observed = observed
        step.entity_refs = [ref for ref in [run.episode_ref, run.patient_ref] if ref]
        step.completed_at = utc_now()
        step.failure_root_cause = None if passed else f"{step.title} was not observable through the canonical connected state."
        step.corrective_action = None if passed else "Correct the canonical propagation path and rerun this exact proof step."
        step.evidence_event_ref = record_evidence(
            session,
            auth=auth,
            run_ref=run_ref,
            action=f"proof_step_{step.step_code}_{step.status}",
            new_state={"stepCode": step.step_code, "status": step.status, "observed": observed},
            reason="Automated connected hospital journey evaluation.",
            risk="green" if passed else "red",
            entity_type="operational_proof_step",
            entity_id=step.step_ref,
        )
        session.add(step)
    run.step_count = len(steps)
    run.passed_count = len([step for step in steps if step.status == "pass"])
    run.partial_count = len([step for step in steps if step.status == "partial"])
    run.blocked_count = len([step for step in steps if step.status == "blocked"])
    run.current_stage = "stress_scenarios" if run.blocked_count == 0 else "correct_connected_journey"
    run.status = "running" if run.blocked_count == 0 else "blocked"
    run.summary = {
        "episodePhase": episode.phase,
        "episodeStatus": episode.status,
        "queueHits": queue_hits,
        "boardChangeEvents": len(board_events),
        "evidenceEvents": len(evidence),
        "operationalBlocks": len(blocks),
        "unplacedButVisible": run.episode_ref in unplaced_refs,
    }
    run.version += 1
    run.updated_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)
    return {"run": row_dict(run), "steps": [row_dict(step) for step in steps], "summary": run.summary}


@router.post("/runs/{run_ref}/scenarios/{scenario_code}")
def record_scenario(
    run_ref: str,
    scenario_code: str,
    payload: ScenarioRecord,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    if scenario_code not in SCENARIOS:
        raise HTTPException(status_code=404, detail="unknown stress scenario")
    run = require_run(session, run_ref, lock=True)
    scenario = session.exec(select(OperationalProofScenarioV30).where(
        OperationalProofScenarioV30.run_ref == run_ref,
        OperationalProofScenarioV30.scenario_code == scenario_code,
    )).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario record not found")
    passed = all([
        payload.failureDetected,
        payload.accountableOwnerVisible,
        payload.nextActionVisible,
        payload.evidenceVisible,
        payload.urgentAccessPreserved,
    ])
    scenario.status = "pass" if passed else "blocked"
    scenario.observed = payload.observed
    scenario.failure_detected = payload.failureDetected
    scenario.accountable_owner_visible = payload.accountableOwnerVisible
    scenario.next_action_visible = payload.nextActionVisible
    scenario.evidence_visible = payload.evidenceVisible
    scenario.urgent_access_preserved = payload.urgentAccessPreserved
    scenario.completed_at = utc_now()
    scenario.evidence_event_ref = record_evidence(
        session,
        auth=auth,
        run_ref=run_ref,
        action=f"stress_{scenario_code}_{scenario.status}",
        new_state=row_dict(scenario),
        reason=payload.reason,
        risk="green" if passed else "red",
        entity_type="operational_proof_scenario",
        entity_id=scenario.scenario_ref,
    )
    session.add(scenario)
    scenarios = session.exec(select(OperationalProofScenarioV30).where(
        OperationalProofScenarioV30.run_ref == run_ref
    )).all()
    run.scenario_count = len([item for item in scenarios if item.status != "pending"])
    run.current_stage = "mobile_acceptance" if all(item.status == "pass" for item in scenarios) else "stress_scenarios"
    if any(item.status == "blocked" for item in scenarios):
        run.status = "blocked"
    run.version += 1
    run.updated_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)
    session.refresh(scenario)
    return {"run": row_dict(run), "scenario": row_dict(scenario)}


@router.post("/runs/{run_ref}/mobile-assessments")
def record_mobile_assessment(
    run_ref: str,
    payload: MobileAssessmentCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    require_run(session, run_ref)
    automated_checks = {
        "minimumWidth": payload.viewportWidth >= 320,
        "minimumHeight": payload.viewportHeight >= 568,
        "secureContext": payload.secureContext,
        "online": payload.online,
        "touchCapable": payload.touchCapable,
        "microphoneAvailable": payload.microphoneAvailable,
        **payload.checks,
    }
    failed = [key for key, value in automated_checks.items() if value is False]
    status = "failed" if failed else "pass" if payload.manualHardwareConfirmation else "manual_confirmation_required"
    limitations = [] if payload.manualHardwareConfirmation else [
        "Automated browser diagnostics cannot prove keyboard overlap, touch comfort or real Android behaviour.",
        "A named person must complete the physical phone journey and record confirmation.",
    ]
    assessment = MobileAcceptanceV30(
        assessment_ref=new_ref("mobile-assessment"),
        run_ref=run_ref,
        device_label=payload.deviceLabel,
        operating_system=payload.operatingSystem,
        browser=payload.browser,
        viewport_width=payload.viewportWidth,
        viewport_height=payload.viewportHeight,
        secure_context=payload.secureContext,
        online=payload.online,
        touch_capable=payload.touchCapable,
        microphone_available=payload.microphoneAvailable,
        checks=automated_checks,
        status=status,
        manual_hardware_confirmation=payload.manualHardwareConfirmation,
        limitations=limitations,
        assessed_by_subject=auth.subject,
    )
    session.add(assessment)
    session.flush()
    assessment.evidence_event_ref = record_evidence(
        session,
        auth=auth,
        run_ref=run_ref,
        action=f"mobile_acceptance_{status}",
        new_state=row_dict(assessment),
        reason=payload.reason,
        risk="green" if status == "pass" else "amber" if status == "manual_confirmation_required" else "red",
        entity_type="mobile_acceptance",
        entity_id=assessment.assessment_ref,
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return {"assessment": row_dict(assessment), "manualActionRequired": not payload.manualHardwareConfirmation}


@router.post("/runs/{run_ref}/complete")
def complete_run(
    run_ref: str,
    payload: CompleteRun,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    run = require_run(session, run_ref, lock=True)
    if run.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale proof run", "currentVersion": run.version})
    steps = session.exec(select(OperationalProofStepV30).where(OperationalProofStepV30.run_ref == run_ref)).all()
    scenarios = session.exec(select(OperationalProofScenarioV30).where(OperationalProofScenarioV30.run_ref == run_ref)).all()
    mobile = session.exec(select(MobileAcceptanceV30).where(
        MobileAcceptanceV30.run_ref == run_ref
    ).order_by(MobileAcceptanceV30.assessed_at.desc())).first()
    blockers: list[str] = []
    if len(steps) != len(JOURNEY_STEPS) or any(step.status != "pass" for step in steps):
        blockers.append("connected journey has incomplete or blocked steps")
    if len(scenarios) != len(SCENARIOS) or any(item.status != "pass" for item in scenarios):
        blockers.append("all eight stress scenarios have not passed")
    if not mobile:
        blockers.append("mobile acceptance assessment missing")
    elif mobile.status == "failed":
        blockers.append("mobile acceptance failed")
    if blockers:
        raise HTTPException(status_code=409, detail={"message": "operational proof cannot complete", "blockers": blockers})
    run.status = "passed_with_manual_boundary" if mobile and mobile.status == "manual_confirmation_required" else "passed"
    run.current_stage = "completed"
    run.completed_at = utc_now()
    run.version += 1
    run.updated_at = utc_now()
    run.summary = {
        **run.summary,
        "connectedJourney": "passed",
        "stressScenarios": "8/8 passed",
        "mobileAcceptance": mobile.status if mobile else "missing",
        "realHospitalDeploymentReady": False,
    }
    run.evidence_event_ref = record_evidence(
        session,
        auth=auth,
        run_ref=run_ref,
        action="operational_proof_completed",
        new_state=row_dict(run),
        reason=payload.reason,
        risk="green" if run.status == "passed" else "amber",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return {"run": row_dict(run), "externalBoundary": run.external_boundaries}


@router.get("/runs/{run_ref}")
def get_run(
    run_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    run = require_run(session, run_ref)
    steps = session.exec(select(OperationalProofStepV30).where(
        OperationalProofStepV30.run_ref == run_ref
    ).order_by(OperationalProofStepV30.sequence)).all()
    scenarios = session.exec(select(OperationalProofScenarioV30).where(
        OperationalProofScenarioV30.run_ref == run_ref
    ).order_by(OperationalProofScenarioV30.scenario_code)).all()
    mobile = session.exec(select(MobileAcceptanceV30).where(
        MobileAcceptanceV30.run_ref == run_ref
    ).order_by(MobileAcceptanceV30.assessed_at.desc())).all()
    return {
        "run": row_dict(run),
        "steps": [row_dict(step) for step in steps],
        "scenarios": [row_dict(item) for item in scenarios],
        "mobileAssessments": [row_dict(item) for item in mobile],
    }


@router.get("/dashboard")
def dashboard(
    site_ref: str | None = Query(default=None),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(OperationalProofRunV30).order_by(OperationalProofRunV30.started_at.desc())
    if site_ref:
        query = query.where(OperationalProofRunV30.site_ref == site_ref)
    runs = session.exec(query).all()
    return {
        "runs": [row_dict(run) for run in runs[:50]],
        "summary": {
            "total": len(runs),
            "passed": len([run for run in runs if run.status in {"passed", "passed_with_manual_boundary"}]),
            "blocked": len([run for run in runs if run.status == "blocked"]),
            "running": len([run for run in runs if run.status == "running"]),
        },
        "boundary": "Passing synthetic proof does not authorise real hospital deployment.",
    }


@router.get("/runs/{run_ref}/report")
def report(
    run_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    payload = get_run(run_ref, session, auth)
    run = payload["run"]
    lines = [
        f"# LucyWorks Operational Proof {run_ref}",
        "",
        f"- Status: **{run['status']}**",
        f"- Site: `{run['site_ref']}`",
        f"- Premises: `{run['premises_ref']}`",
        f"- Episode: `{run.get('episode_ref') or 'not attached'}`",
        "",
        "## Connected journey",
    ]
    for step in payload["steps"]:
        lines.append(f"- {step['status'].upper()}: {step['title']} — {step['surface']}")
    lines.extend(["", "## Stress scenarios"])
    for item in payload["scenarios"]:
        lines.append(f"- {item['status'].upper()}: {item['title']}")
    lines.extend(["", "## External boundary"])
    for item in run["external_boundaries"]:
        lines.append(f"- {item}")
    return {"runRef": run_ref, "markdown": "\n".join(lines), "data": payload}
