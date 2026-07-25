from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.detailed_hospital_models import PatientClinicalRecordV8
from app.hospital_command_models import ReferralIntakeV9
from app.hospital_command_routes import row_dict
from app.hospital_ops_models import CanonicalEpisodeState

router = APIRouter(prefix="/api/v9", tags=["hospital-command-intake-v9"])
READ_ROLES = ("admin", "ops_manager", "clinician", "clinical_director", "senior_clinician", "supervisor", "nurse")


@router.get("/referrals")
def referral_queue(
    status: str | None = None,
    premises_ref: str | None = None,
    requested_service: str | None = None,
    urgency: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    query = select(ReferralIntakeV9)
    if status:
        query = query.where(ReferralIntakeV9.status == status)
    if premises_ref:
        query = query.where(ReferralIntakeV9.premises_ref == premises_ref)
    if requested_service:
        query = query.where(ReferralIntakeV9.requested_service == requested_service)
    if urgency:
        query = query.where(ReferralIntakeV9.urgency == urgency)
    rows = session.exec(query.order_by(ReferralIntakeV9.received_at.desc()).limit(limit)).all()
    episode_refs = [row.episode_ref for row in rows]
    patient_refs = [row.patient_ref for row in rows]
    episodes = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref.in_(episode_refs))).all() if episode_refs else []
    patients = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref.in_(patient_refs))).all() if patient_refs else []
    episode_map = {row.episode_ref: row for row in episodes}
    patient_map = {row.patient_ref: row for row in patients}
    items = []
    for row in rows:
        episode = episode_map.get(row.episode_ref)
        patient = patient_map.get(row.patient_ref)
        items.append({
            **row_dict(row),
            "patientName": patient.display_name if patient else episode.patient_name if episode else None,
            "episodePhase": episode.phase if episode else None,
            "episodeVersion": episode.version if episode else None,
            "episodeOwnerRole": episode.owner_role if episode else None,
        })
    return {"items": items, "count": len(items), "requestedBy": auth.subject}


@router.get("/referrals/{referral_ref}")
def referral_detail(
    referral_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    row = session.exec(select(ReferralIntakeV9).where(ReferralIntakeV9.referral_ref == referral_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="referral not found")
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == row.episode_ref)).first()
    patient = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == row.patient_ref)).first()
    return {
        "referral": row_dict(row),
        "episode": row_dict(episode) if episode else None,
        "patient": row_dict(patient) if patient else None,
        "requestedBy": auth.subject,
    }
