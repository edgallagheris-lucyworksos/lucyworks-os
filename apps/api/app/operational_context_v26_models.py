from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganisationV26(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("organisation_ref", name="uq_organisationv26_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    name: str
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class SiteV26(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("site_ref", name="uq_sitev26_ref"),
        UniqueConstraint("organisation_ref", "premises_ref", name="uq_sitev26_org_premises"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    site_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    name: str
    timezone_name: str = "Europe/London"
    status: str = Field(default="active", index=True)
    configuration_state: str = Field(default="draft", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class SiteMembershipV26(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("membership_ref", name="uq_sitemembershipv26_ref"),
        UniqueConstraint("subject", "site_ref", name="uq_sitemembershipv26_subject_site"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    membership_ref: str = Field(index=True)
    subject: str = Field(index=True)
    actor_id: Optional[str] = Field(default=None, index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    role: str = Field(index=True)
    status: str = Field(default="active", index=True)
    is_primary: bool = False
    granted_by_subject: str = Field(index=True)
    granted_at: datetime = Field(default_factory=utc_now, index=True)
    revoked_at: Optional[datetime] = Field(default=None, index=True)


class ActiveOperatingContextV26(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("subject", name="uq_activecontextv26_subject"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    context_ref: str = Field(index=True, unique=True)
    subject: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    version: int = 1
    selected_by_subject: str = Field(index=True)
    selected_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ContextSwitchEvidenceV26(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("switch_ref", name="uq_contextswitchv26_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    switch_ref: str = Field(index=True)
    subject: str = Field(index=True)
    previous_context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    new_context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    reason: str
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class CanonicalCommandV26(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("command_ref", name="uq_canonicalcommandv26_ref"),
        UniqueConstraint("idempotency_key", name="uq_canonicalcommandv26_idempotency"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    command_ref: str = Field(index=True)
    command_type: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    source_route: str = Field(index=True)
    source_module: str = Field(index=True)
    source_record_ref: Optional[str] = Field(default=None, index=True)
    legacy_route_key: Optional[str] = Field(default=None, index=True)
    request_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    outcome_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="recorded", index=True)
    requires_human_decision: bool = True
    clinical_mutation_performed: bool = False
    safety_record_ref: Optional[str] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    idempotency_key: str = Field(index=True)
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    created_at: datetime = Field(default_factory=utc_now, index=True)


class LegacyRouteConvergenceV26(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("route_key", name="uq_legacyroutev26_key"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    route_key: str = Field(index=True)
    method: str = Field(index=True)
    legacy_path: str
    canonical_command_type: str = Field(index=True)
    canonical_path: str
    status: str = Field(default="canonicalised", index=True)
    retirement_state: str = Field(default="observe", index=True)
    reason: str
    activated_at: datetime = Field(default_factory=utc_now, index=True)


class OperationalImpactV26(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("impact_ref", name="uq_operationalimpactv26_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    impact_ref: str = Field(index=True)
    command_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    impact_type: str = Field(index=True)
    severity: str = Field(default="amber", index=True)
    service_ref: Optional[str] = Field(default=None, index=True)
    patient_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    affected_patient_count: int = 0
    board_summary: str
    restricted_detail_ref: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="active", index=True)
    owner_subject: Optional[str] = Field(default=None, index=True)
    owner_role: Optional[str] = Field(default=None, index=True)
    due_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
