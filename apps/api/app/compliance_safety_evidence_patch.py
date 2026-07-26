from __future__ import annotations

from sqlmodel import Session, select

from app import compliance_safety_deployment_routes as deployment
from app.production_readiness_models import ReadinessControl, ReadinessEvidence


def approved_evidence(session: Session, evidence_ref: str) -> bool:
    evidence = session.exec(select(ReadinessEvidence).where(ReadinessEvidence.evidence_ref == evidence_ref)).first()
    if not evidence:
        return False
    control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == evidence.control_ref)).first()
    if not control or control.status != "passed":
        return False
    latest = session.exec(select(ReadinessEvidence).where(
        ReadinessEvidence.control_ref == evidence.control_ref,
    ).order_by(ReadinessEvidence.recorded_at.desc())).first()
    return bool(latest and latest.evidence_ref == evidence_ref)


deployment._approved_evidence = approved_evidence
