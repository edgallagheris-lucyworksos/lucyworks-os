import json
from typing import Any, Iterable, Optional

from sqlmodel import Session

from app.evidence_models import EvidenceEvent


def _json(value: Any, fallback: Any) -> str:
    return json.dumps(fallback if value is None else value, sort_keys=True, default=str, separators=(",", ":"))


def record_evidence(
    session: Session,
    *,
    event_type: str,
    actor_name: str,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor_role: Optional[str] = None,
    authority_basis: Optional[str] = None,
    episode_id: Optional[int] = None,
    state_before: Any = None,
    state_after: Any = None,
    reason: Optional[str] = None,
    evidence_refs: Optional[Iterable[str]] = None,
    source_system: str = "lucyworks",
    correlation_id: Optional[str] = None,
) -> EvidenceEvent:
    """Create evidence without mutating or replacing any earlier event."""
    event = EvidenceEvent(
        event_type=event_type,
        actor_name=actor_name,
        actor_role=actor_role,
        authority_basis=authority_basis,
        entity_type=entity_type,
        entity_id=str(entity_id),
        episode_id=episode_id,
        action=action,
        state_before_json=_json(state_before, {}),
        state_after_json=_json(state_after, {}),
        reason=reason,
        evidence_refs_json=_json(list(evidence_refs or []), []),
        source_system=source_system,
        correlation_id=correlation_id,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
