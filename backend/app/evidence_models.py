from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceEvent(SQLModel, table=True):
    """Append-only evidence record for consequential LucyWorks actions."""

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)
    actor_name: str
    actor_role: Optional[str] = None
    authority_basis: Optional[str] = None
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id", index=True)
    action: str
    state_before_json: str = "{}"
    state_after_json: str = "{}"
    reason: Optional[str] = None
    evidence_refs_json: str = "[]"
    source_system: str = "lucyworks"
    correlation_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class VerificationRecord(SQLModel, table=True):
    """Human verification trail for AI-generated or otherwise review-gated content."""

    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id", index=True)
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    content_type: str
    status: str = Field(default="awaiting_verification", index=True)
    original_content: str
    final_content: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    provenance: Optional[str] = None
    generated_at: datetime = Field(default_factory=utc_now)
    verified_by: Optional[str] = None
    verifier_role: Optional[str] = None
    verification_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
