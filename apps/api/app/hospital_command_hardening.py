from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from app import hospital_command_routes as routes
from app.auth import AuthContext, SENIOR_ROLES, require_roles
from app.database import get_session
from app.detailed_hospital_models import CommunicationEventV8, EstimateV8, PatientOwnerLinkV8
from app.hospital_command_models import ConsentAuthorisationV9, EpisodeCheckpointV9, EpisodeClosureV9, ReferralIntakeV9
from app.hospital_ops_models import CanonicalEpisodeState

NON_WAIVABLE_GATES = {
    "unknown_target_phase",
    "transition_graph",
    "patient_identity",
    "referral_intake",
    "decision_authority",
    "closure_approval",
    "discharge_document_sent",
}
EARLY_CLOSURE_PHASES = {"referral_received", "intake", "triage", "consult"}
EARLY_CLOSURE_DISPOSITIONS = {"referral_declined", "referral_cancelled", "not_attended"}
MAX_WAIVER_DURATION = timedelta(hours=24)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def active_consents(session: Session, episode_ref: str) -> list[ConsentAuthorisationV9]:
    now = routes.utc_now()
    rows = session.exec(select(ConsentAuthorisationV9).where(
        ConsentAuthorisationV9.episode_ref == episode_ref,
        ConsentAuthorisationV9.status == "active",
    )).all()
    active: list[ConsentAuthorisationV9] = []
    for row in rows:
        valid_from = as_utc(row.valid_from)
        valid_until = as_utc(row.valid_until)
        if valid_from and valid_from <= now and (valid_until is None or valid_until >= now):
            active.append(row)
    return active


def latest_waivers(session: Session, episode_ref: str) -> dict[str, EpisodeCheckpointV9]:
    now = routes.utc_now()
    rows = session.exec(select(EpisodeCheckpointV9).where(
        EpisodeCheckpointV9.episode_ref == episode_ref,
        EpisodeCheckpointV9.status == "waived",
    ).order_by(EpisodeCheckpointV9.created_at.desc())).all()
    result: dict[str, EpisodeCheckpointV9] = {}
    for row in rows:
        valid_until = as_utc(row.valid_until)
        if row.checkpoint_code in NON_WAIVABLE_GATES:
            continue
        if row.checkpoint_code not in result and valid_until is not None and valid_until >= now:
            result[row.checkpoint_code] = row
    return result


_original_evaluate_guard = routes.evaluate_guard


def evaluate_guard(session: Session, episode: CanonicalEpisodeState, target_phase: str) -> dict[str, Any]:
    result = _original_evaluate_guard(session, episode, target_phase)

    restored: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for warning in result.get("warnings", []):
        if warning.get("code") in NON_WAIVABLE_GATES and warning.get("waivedByCheckpoint"):
            restored.append({key: value for key, value in warning.items() if key != "waivedByCheckpoint"})
        else:
            warnings.append(warning)
    result["blockers"] = result.get("blockers", []) + restored
    result["warnings"] = warnings

    early_closure = target_phase == "closed" and episode.phase in EARLY_CLOSURE_PHASES
    if early_closure:
        discharge_only = {
            "decision_authority",
            "active_inpatient_plan",
            "red_inpatient_concern",
            "procedure_incomplete",
            "anaesthesia_incomplete",
            "discharge_document",
            "owner_communication",
            "discharge_document_sent",
        }
        result["blockers"] = [item for item in result["blockers"] if item.get("code") not in discharge_only]
        result["warnings"] = [item for item in result["warnings"] if item.get("code") not in {"referrer_communication", "estimate_status"}]
        result["earlyClosure"] = True

    for item in result.get("blockers", []):
        item["waivable"] = item.get("code") not in NON_WAIVABLE_GATES
    result["canTransition"] = not result.get("blockers")
    return result


_original_create_consent = routes.create_consent


def create_consent(
    episode_ref: str,
    payload: routes.ConsentCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles("admin", "clinician", "clinical_director", "senior_clinician", "supervisor")),
) -> dict[str, Any]:
    if payload.maximum_authorised_pence is not None:
        episode = routes.require_episode(session, episode_ref)
        if not episode.patient_ref:
            raise HTTPException(status_code=409, detail="episode has no patient reference")
        link = session.exec(select(PatientOwnerLinkV8).where(
            PatientOwnerLinkV8.patient_ref == episode.patient_ref,
            PatientOwnerLinkV8.owner_ref == payload.owner_ref,
            PatientOwnerLinkV8.active == True,  # noqa: E712
            PatientOwnerLinkV8.decision_authority == True,  # noqa: E712
            PatientOwnerLinkV8.financial_responsibility == True,  # noqa: E712
        )).first()
        if not link:
            raise HTTPException(status_code=409, detail="owner does not have active financial responsibility for this patient")
    return _original_create_consent(episode_ref, payload, session, auth)


_original_create_checkpoint = routes.create_checkpoint


def create_checkpoint(
    episode_ref: str,
    payload: routes.CheckpointCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    if payload.status == "waived":
        if payload.checkpoint_code in NON_WAIVABLE_GATES:
            raise HTTPException(status_code=409, detail={
                "message": "checkpoint cannot be waived",
                "checkpointCode": payload.checkpoint_code,
            })
        valid_until = as_utc(payload.valid_until)
        now = routes.utc_now()
        if valid_until is None:
            raise HTTPException(status_code=422, detail="waiver expiry is required")
        if valid_until <= now:
            raise HTTPException(status_code=422, detail="waiver expiry must be in the future")
        if valid_until - now > MAX_WAIVER_DURATION:
            raise HTTPException(status_code=422, detail="waiver cannot exceed 24 hours")
    return _original_create_checkpoint(episode_ref, payload, session, auth)


def _communication(session: Session, reference: str | None, *, audience: set[str] | None = None) -> CommunicationEventV8 | None:
    if not reference:
        return None
    row = session.exec(select(CommunicationEventV8).where(CommunicationEventV8.communication_ref == reference)).first()
    if not row or row.direction != "outbound":
        return None
    if audience and row.audience not in audience:
        return None
    return row


def approve_closure(
    closure_ref: str,
    payload: routes.VersionedReason,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    query = select(EpisodeClosureV9).where(EpisodeClosureV9.closure_ref == closure_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="closure not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale closure", "currentVersion": row.version})
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="only a draft closure can be approved")

    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == row.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=409, detail="canonical episode missing for closure")
    referral = session.exec(select(ReferralIntakeV9).where(ReferralIntakeV9.episode_ref == row.episode_ref)).first()
    early = episode.phase in EARLY_CLOSURE_PHASES and row.disposition in EARLY_CLOSURE_DISPOSITIONS
    failures: list[str] = []

    if row.outstanding_actions:
        failures.append("outstanding actions remain")
    if row.financial_status not in routes.FINANCIAL_CLOSURE_STATES:
        failures.append("financial status is not closure-ready")

    owner_communication = _communication(session, row.owner_communication_ref, audience={"owner"})
    referrer_communication = _communication(session, row.referrer_communication_ref, audience={"referring_vet", "referrer"})

    if early:
        if row.disposition == "referral_declined" and (not referral or referral.status != "declined"):
            failures.append("referral must be declined before referral-declined closure")
        if not owner_communication and not referrer_communication:
            failures.append("owner or referrer closure communication evidence is required")
    else:
        if not row.discharge_document_ref:
            failures.append("discharge document reference missing")
        else:
            document = session.exec(select(routes.ClinicalDocumentV8).where(routes.ClinicalDocumentV8.document_ref == row.discharge_document_ref)).first()
            if not document or document.episode_ref != row.episode_ref or document.status != "sent":
                failures.append("discharge document is not a sent document for this episode")
        if not owner_communication or owner_communication.episode_ref != row.episode_ref:
            failures.append("owner communication evidence is invalid")

    if row.referrer_communication_ref and (not referrer_communication or referrer_communication.episode_ref != row.episode_ref):
        failures.append("referrer communication evidence is invalid")
    if row.final_estimate_ref:
        estimate = session.exec(select(EstimateV8).where(EstimateV8.estimate_ref == row.final_estimate_ref)).first()
        if not estimate or estimate.episode_ref != row.episode_ref or estimate.status != "approved":
            failures.append("final estimate is not an approved estimate for this episode")
    if failures:
        raise HTTPException(status_code=409, detail={"message": "closure approval blocked", "failures": failures})

    previous = routes.row_dict(row)
    row.status = "approved"
    row.approved_by_subject = auth.subject
    row.approved_at = routes.utc_now()
    row.version += 1
    row.updated_at = routes.utc_now()
    session.add(row)
    row.evidence_event_ref = routes.record_evidence(
        session,
        entity_type="episode_closure",
        entity_ref=closure_ref,
        action="approved",
        episode_ref=row.episode_ref,
        patient_ref=row.patient_ref,
        previous=previous,
        current=routes.row_dict(row),
        reason=payload.reason,
        risk="amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"closure": routes.row_dict(row), "earlyClosure": early}


def patch_route(path: str, method: str, endpoint: Any) -> None:
    for route in routes.router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            route.endpoint = endpoint
            route.dependant.call = endpoint


routes.active_consents = active_consents
routes.latest_waivers = latest_waivers
routes.evaluate_guard = evaluate_guard
routes.create_consent = create_consent
routes.create_checkpoint = create_checkpoint
routes.approve_closure = approve_closure
patch_route("/api/v9/episodes/{episode_ref}/consents", "POST", create_consent)
patch_route("/api/v9/episodes/{episode_ref}/checkpoints", "POST", create_checkpoint)
patch_route("/api/v9/closures/{closure_ref}/approve", "PATCH", approve_closure)
