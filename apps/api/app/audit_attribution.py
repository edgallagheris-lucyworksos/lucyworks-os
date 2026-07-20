from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session as SASession

from app.auth import get_current_auth_context
from app.control_plane_models import (
    AIModelRegistration,
    AccountableHandover,
    CriticalResultAcknowledgement,
    ServiceAvailability,
)
from app.evidence_approval_models import ApprovalTask
from app.evidence_event_models import ConsentRecord, EstimateVersion


@event.listens_for(SASession, "before_flush")
def enforce_verified_attribution(session: SASession, _flush_context: object, _instances: object) -> None:
    """Replace payload-supplied audit actors with the verified request identity.

    Domain ownership fields such as accountable_owner and responsible_actor are
    intentionally left untouched. Only fields that claim who performed the
    current write or decision are enforced here.
    """

    auth = get_current_auth_context()
    if not auth.verified:
        return

    for row in session.new:
        if isinstance(row, EstimateVersion):
            row.created_by = auth.actor_name
        elif isinstance(row, ConsentRecord):
            row.recorded_by = auth.actor_name
        elif isinstance(row, AccountableHandover):
            row.from_actor = auth.actor_name
            row.from_role = auth.role
        elif isinstance(row, ServiceAvailability):
            row.updated_by = auth.actor_name

    for row in session.dirty:
        if isinstance(row, AccountableHandover) and row.accepted_at is not None:
            row.accepted_by = auth.actor_name
            row.accepted_by_role = auth.role
        elif isinstance(row, ServiceAvailability):
            row.updated_by = auth.actor_name
        elif isinstance(row, AIModelRegistration) and row.approved_at is not None:
            row.approved_by = auth.actor_name
        elif isinstance(row, CriticalResultAcknowledgement) and row.acknowledged_at is not None:
            row.acknowledged_by = auth.actor_name
        elif isinstance(row, ApprovalTask) and row.decided_at is not None:
            row.decided_by = auth.actor_name
            row.decided_by_role = auth.role
