from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.auth import AuthContext
from app import bvs_v6_service as service
from app.bvs_v6_models import ConfigurationClaim

_original_claim_dict = service.claim_dict
_original_review_claim = service.review_claim


def claim_dict_with_review_evidence(row: ConfigurationClaim) -> dict[str, Any]:
    payload = _original_claim_dict(row)
    payload["reviewEvidenceRefs"] = list(row.review_evidence_refs or [])
    return payload


def review_claim_with_evidence(
    session: Session,
    claim_ref: str,
    payload: dict[str, Any],
    auth: AuthContext,
) -> ConfigurationClaim:
    row = _original_review_claim(session, claim_ref, payload, auth)
    evidence_ref = str(payload.get("evidenceRef") or "").strip()
    if evidence_ref and evidence_ref not in (row.review_evidence_refs or []):
        before_refs = list(row.review_evidence_refs or [])
        row.review_evidence_refs = [*before_refs, evidence_ref]
        session.flush()
        service._evidence(
            session,
            auth,
            event_type="configuration_claim_review_evidence_linked",
            action="claim review evidence linked",
            entity_type="configuration_claim",
            entity_id=claim_ref,
            previous_state={"reviewEvidenceRefs": before_refs},
            new_state={"reviewEvidenceRefs": row.review_evidence_refs},
            reason=f"Review evidence linked: {evidence_ref}",
            risk_level="red" if row.status == "verified" else "amber",
        )
    return row


service.claim_dict = claim_dict_with_review_evidence
service.review_claim = review_claim_with_evidence
