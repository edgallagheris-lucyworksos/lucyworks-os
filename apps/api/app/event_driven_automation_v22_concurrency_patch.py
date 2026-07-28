from __future__ import annotations

from app import event_driven_automation_v22_service as service
from app.auth import AuthContext
from app.event_driven_automation_v22_models import AutomationTriggerV22


def concurrency_safe_dispatch_source(
    source_type: str,
    source_ref: str,
    *,
    initiated_by: AuthContext | None = None,
) -> AutomationTriggerV22:
    row, created = service.enqueue_source(source_type, source_ref, initiated_by=initiated_by)
    # The database uniqueness constraint elects one creator for a source state and
    # mode. Only that creator may automatically execute the queued trigger. All
    # concurrent or retried followers return the same durable row and work set.
    if created and row.status == "queued":
        return service.process_trigger(row.trigger_ref)
    return row


service.dispatch_source = concurrency_safe_dispatch_source
