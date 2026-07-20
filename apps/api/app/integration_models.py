from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IntegrationConnection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    connection_ref: str = Field(index=True)
    integration_type: str = Field(index=True)
    vendor: str
    direction: str = "inbound"
    status: str = Field(default="draft", index=True)
    premises_ref: str = Field(default="default-premises", index=True)
    endpoint_url: Optional[str] = None
    secret_env: str
    mapping_profile_json: Optional[str] = None
    store_payload: bool = False
    accountable_owner: str
    created_by: str = "system"
    last_received_at: Optional[datetime] = None
    last_processed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class IntegrationEnvelope(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    envelope_ref: str = Field(index=True)
    connection_ref: str = Field(index=True)
    message_type: str = Field(index=True)
    external_event_id: Optional[str] = Field(default=None, index=True)
    dedupe_key: str = Field(index=True)
    payload_hash: str = Field(index=True)
    payload_json: Optional[str] = None
    status: str = Field(default="received", index=True)
    patient_case_id: Optional[str] = Field(default=None, index=True)
    referral_episode_id: Optional[str] = Field(default=None, index=True)
    internal_record_type: Optional[str] = None
    internal_record_ref: Optional[str] = None
    evidence_event_ref: Optional[str] = None
    error: Optional[str] = None
    received_at: datetime = Field(default_factory=utc_now, index=True)
    processed_at: Optional[datetime] = None


class IntegrationEntityLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    connection_ref: str = Field(index=True)
    external_entity_type: str = Field(index=True)
    external_entity_id: str = Field(index=True)
    internal_entity_type: str = Field(index=True)
    internal_entity_id: str = Field(index=True)
    last_seen_at: datetime = Field(default_factory=utc_now, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
