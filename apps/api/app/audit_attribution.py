from __future__ import annotations

from fastapi import HTTPException
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
from app.hospital_ops_models import ImportBatch, OperationalBlock, OperationalCommand, ScenarioRun
from app.integration_models import IntegrationConnection
from app.models import AuditEvent
from app.schedule_state_models import ScheduleStateEvent


@event.listens_for(SASession, "before_flush")
def enforce_verified_attribution(session: SASession, _flush_context: object, _instances: object) -> None:
    """Enforce verified audit attribution and non-destructive import policy."""

    auth = get_current_auth_context()

    # This invariant is independent of authentication mode: invalid rows cannot
    # be silently committed by a direct service call or an older route.
    for row in session.dirty:
        if isinstance(row, ImportBatch) and row.status == "committed" and row.rejected_count > 0:
            raise HTTPException(status_code=409, detail={
                "code": "reconciliation_required",
                "message": "all rejected import rows must be resolved before commit",
                "unresolvedCount": row.rejected_count,
            })

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
        elif isinstance(row, IntegrationConnection):
            row.created_by = auth.actor_name
        elif isinstance(row, ScheduleStateEvent):
            row.actor = auth.actor_name
        elif isinstance(row, AuditEvent):
            row.actor_name = auth.actor_name
        elif isinstance(row, OperationalCommand):
            row.actor_subject = auth.subject
            row.actor_name = auth.actor_name
            row.actor_role = auth.role
            row.auth_source = auth.auth_source
        elif isinstance(row, OperationalBlock):
            row.updated_by_subject = auth.subject
            row.updated_by_name = auth.actor_name
            row.updated_by_role = auth.role
            row.updated_by_auth_source = auth.auth_source
        elif isinstance(row, ScenarioRun):
            row.created_by_subject = auth.subject
        elif isinstance(row, ImportBatch):
            row.created_by_subject = auth.subject

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
        elif isinstance(row, OperationalBlock):
            row.updated_by_subject = auth.subject
            row.updated_by_name = auth.actor_name
            row.updated_by_role = auth.role
            row.updated_by_auth_source = auth.auth_source
