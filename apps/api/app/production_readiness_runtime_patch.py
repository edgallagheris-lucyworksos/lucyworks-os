from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.production_readiness_models import PilotObservation, PilotRun, ReadinessControl
from app import production_readiness_service as service

_original_create_pilot = service.create_pilot
_original_add_observation = service.add_observation
_original_update_pilot = service.update_pilot
_original_resolve_observation = service.resolve_observation


def _pilot_evidence(
    session: Session,
    auth: AuthContext,
    *,
    event_type: str,
    action: str,
    run_ref: str,
    before: Any,
    after: Any,
    risk_level: str,
    reason: str,
) -> None:
    create_evidence_event(
        session,
        event_type=event_type,
        action=action,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=after,
        reason=reason,
        justification="LucyWorks controlled validation and production-readiness governance",
        evidence_links=[{"type": "pilot_run", "id": run_ref}],
        compliance_domain="information_governance",
        risk_level=risk_level,
        source_module="production_readiness",
        source_record_ref=run_ref,
        entity_type="pilot_run",
        entity_id=run_ref,
    )


def _missing_before_bounded(summary: dict[str, Any]) -> list[str]:
    return [ref for ref in summary.get("liveMissing", []) if ref != "pilot.bounded"]


def create_pilot_guarded(session: Session, payload: dict[str, Any], auth: AuthContext) -> PilotRun:
    phase = str(payload.get("phase") or "synthetic")
    summary = service.gate_summary(session)
    if phase == "shadow" and not summary["shadowEligible"]:
        raise RuntimeError(f"shadow mode is blocked; missing controls: {', '.join(summary['shadowMissing']) or 'open red observations'}")
    if phase == "bounded_pilot":
        missing = _missing_before_bounded(summary)
        if missing or summary["openRedObservations"]:
            raise RuntimeError(f"bounded pilot is blocked; missing controls: {', '.join(missing) or 'none'}; open red observations: {summary['openRedObservations']}")
    if phase == "scale_up":
        passed_pilot = session.exec(select(PilotRun).where(PilotRun.phase == "bounded_pilot", PilotRun.status == "passed")).first()
        if not summary["liveEligible"] or not passed_pilot:
            raise RuntimeError("scale-up is blocked until every live-readiness control passes and a bounded pilot is approved as passed")

    run = _original_create_pilot(session, payload, auth)
    session.flush()
    _pilot_evidence(
        session,
        auth,
        event_type="pilot_run_created",
        action=f"{phase} validation run created",
        run_ref=run.run_ref,
        before=None,
        after=service.pilot_dict(run),
        risk_level="amber",
        reason=f"controlled {phase} validation initiated",
    )
    return run


def add_observation_evidenced(session: Session, run_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotObservation:
    row = _original_add_observation(session, run_ref, payload, auth)
    session.flush()
    _pilot_evidence(
        session,
        auth,
        event_type="pilot_observation_recorded",
        action=f"{row.severity} pilot observation recorded",
        run_ref=run_ref,
        before=None,
        after=service.observation_dict(row),
        risk_level="red" if row.severity == "red" else "amber" if row.severity == "amber" else "green",
        reason=row.summary,
    )
    return row


def update_pilot_evidenced(session: Session, run_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotRun:
    existing = session.exec(select(PilotRun).where(PilotRun.run_ref == run_ref)).first()
    if not existing:
        raise ValueError("pilot run not found")
    before = service.pilot_dict(existing)
    requested_status = payload.get("status")
    if requested_status == "passed":
        if not str(payload.get("approvalNote") or "").strip():
            raise ValueError("approvalNote is required to pass a validation run")
        open_red = session.exec(select(PilotObservation).where(PilotObservation.run_ref == run_ref, PilotObservation.severity == "red", PilotObservation.status != "resolved")).all()
        if open_red:
            raise RuntimeError(f"pilot cannot pass with {len(open_red)} unresolved red observations")

    run = _original_update_pilot(session, run_ref, payload, auth)
    session.flush()
    after = service.pilot_dict(run)
    _pilot_evidence(
        session,
        auth,
        event_type="pilot_run_updated",
        action=f"pilot run marked {run.status}",
        run_ref=run_ref,
        before=before,
        after=after,
        risk_level="green" if run.status == "passed" else "red" if run.status in {"blocked", "failed"} else "amber",
        reason=str(payload.get("approvalNote") or f"pilot status updated to {run.status}"),
    )

    control_ref = "shadow.mode" if run.phase == "shadow" else "pilot.bounded" if run.phase == "bounded_pilot" else None
    if requested_status == "passed" and control_ref:
        control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == control_ref)).first()
        if control:
            service.update_control(
                session,
                control_ref,
                {
                    "expectedVersion": control.version,
                    "status": "passed",
                    "evidenceSummary": f"Approved {run.phase} run {run.run_ref}: {payload['approvalNote']}",
                    "reason": str(payload["approvalNote"]),
                    "validDays": 180,
                },
                auth,
            )
    return run


def resolve_observation_evidenced(session: Session, observation_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotObservation:
    existing = session.exec(select(PilotObservation).where(PilotObservation.observation_ref == observation_ref)).first()
    if not existing:
        raise ValueError("observation not found")
    before = service.observation_dict(existing)
    row = _original_resolve_observation(session, observation_ref, payload, auth)
    session.flush()
    _pilot_evidence(
        session,
        auth,
        event_type="pilot_observation_resolved",
        action="pilot observation resolved",
        run_ref=row.run_ref,
        before=before,
        after=service.observation_dict(row),
        risk_level="green",
        reason=row.resolution or "resolved",
    )
    return row


service.create_pilot = create_pilot_guarded
service.add_observation = add_observation_evidenced
service.update_pilot = update_pilot_evidenced
service.resolve_observation = resolve_observation_evidenced
