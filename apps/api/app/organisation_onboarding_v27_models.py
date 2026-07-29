from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OnboardingOrganisationV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("organisation_ref", name="uq_onboardingorganisationv27_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    legal_name: str
    trading_name: Optional[str] = None
    company_number: Optional[str] = Field(default=None, index=True)
    country_code: str = Field(default="GB", index=True)
    registered_address: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    data_controller_name: Optional[str] = None
    data_controller_email: Optional[str] = None
    accountable_executive_subject: Optional[str] = Field(default=None, index=True)
    accountable_executive_name: Optional[str] = None
    status: str = Field(default="draft", index=True)
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_by_name: str
    updated_by_role: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OnboardingSiteV27(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("site_ref", name="uq_onboardingsitev27_ref"),
        UniqueConstraint("organisation_ref", "premises_ref", name="uq_onboardingsitev27_org_premises"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    site_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    name: str
    site_type: str = Field(default="referral_hospital", index=True)
    timezone_name: str = "Europe/London"
    address: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    regulator_premises_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    emergency_status: str = Field(default="not_declared", index=True)
    accountable_director_subject: Optional[str] = Field(default=None, index=True)
    accountable_director_name: Optional[str] = None
    clinical_governance_subject: Optional[str] = Field(default=None, index=True)
    clinical_governance_name: Optional[str] = None
    status: str = Field(default="draft", index=True)
    active_release_ref: Optional[str] = Field(default=None, index=True)
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_by_name: str
    updated_by_role: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OnboardingDepartmentV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("site_ref", "department_ref", name="uq_onboardingdepartmentv27_site_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    department_ref: str = Field(index=True)
    name: str
    department_type: str = Field(default="clinical", index=True)
    accountable_role: str = "department_lead"
    accountable_subject: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="draft", index=True)
    attributes: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OnboardingServiceV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("site_ref", "service_ref", name="uq_onboardingservicev27_site_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    service_ref: str = Field(index=True)
    department_ref: str = Field(index=True)
    name: str
    service_type: str = Field(default="clinical", index=True)
    clinical_service: bool = True
    operational_status: str = Field(default="draft", index=True)
    hours: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    minimum_staffing: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    required_equipment_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    escalation_role: str = "ops_manager"
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OnboardingRoomV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("site_ref", "room_ref", name="uq_onboardingroomv27_site_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    room_ref: str = Field(index=True)
    department_ref: str = Field(index=True)
    name: str
    room_type: str = Field(index=True)
    service_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    infection_control_zone: Optional[str] = None
    capacity: int = 1
    operational_status: str = Field(default="draft", index=True)
    attributes: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OnboardingEquipmentV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("site_ref", "equipment_ref", name="uq_onboardingequipmentv27_site_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    equipment_ref: str = Field(index=True)
    name: str
    equipment_type: str = Field(index=True)
    room_ref: Optional[str] = Field(default=None, index=True)
    service_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    asset_identifier: Optional[str] = Field(default=None, index=True)
    maintenance_status: str = Field(default="unverified", index=True)
    maintenance_due_at: Optional[date] = Field(default=None, index=True)
    operational_status: str = Field(default="draft", index=True)
    attributes: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class StaffImportBatchV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("batch_ref", name="uq_staffimportbatchv27_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    source_type: str = Field(default="csv", index=True)
    source_ref: Optional[str] = None
    checksum: str = Field(index=True)
    rows: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    row_count: int = 0
    valid_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    validation_findings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="preview", index=True)
    created_by_subject: str = Field(index=True)
    committed_by_subject: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    committed_at: Optional[datetime] = Field(default=None, index=True)


class OnboardingStaffV27(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("site_ref", "staff_ref", name="uq_onboardingstaffv27_site_ref"),
        UniqueConstraint("site_ref", "auth_subject", name="uq_onboardingstaffv27_site_subject"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    display_name: str
    email: Optional[str] = Field(default=None, index=True)
    auth_subject: Optional[str] = Field(default=None, index=True)
    identity_status: str = Field(default="unmatched", index=True)
    employment_status: str = Field(default="active", index=True)
    department_ref: str = Field(index=True)
    requested_role: str = Field(default="viewer", index=True)
    primary_role_ref: str = Field(default="staff", index=True)
    grade_or_training_level: Optional[str] = None
    contracted_hours_weekly: Optional[float] = None
    maximum_safe_hours_weekly: Optional[float] = None
    supervisor_staff_ref: Optional[str] = Field(default=None, index=True)
    on_call_eligible: bool = False
    access_status: str = Field(default="not_requested", index=True)
    clinical_authority_status: str = Field(default="not_applicable", index=True)
    source_batch_ref: Optional[str] = Field(default=None, index=True)
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class StaffCredentialV27(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("credential_ref", name="uq_staffcredentialv27_ref"),
        UniqueConstraint("site_ref", "staff_ref", "credential_type", "credential_number", name="uq_staffcredentialv27_staff_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    credential_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    credential_type: str = Field(index=True)
    issuing_body: str
    credential_number: str = Field(index=True)
    valid_from: Optional[date] = None
    valid_until: Optional[date] = Field(default=None, index=True)
    verification_status: str = Field(default="unverified", index=True)
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    verified_by_subject: Optional[str] = Field(default=None, index=True)
    verified_by_name: Optional[str] = None
    verified_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1


class StaffCompetencyV27(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("competency_record_ref", name="uq_staffcompetencyv27_ref"),
        UniqueConstraint("site_ref", "staff_ref", "competency_ref", "scope_ref", name="uq_staffcompetencyv27_staff_scope"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    competency_record_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    competency_ref: str = Field(index=True)
    scope_ref: str = Field(default="hospital", index=True)
    level: str = Field(default="supervised", index=True)
    verification_status: str = Field(default="unverified", index=True)
    evidence_summary: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    valid_from: Optional[date] = None
    valid_until: Optional[date] = Field(default=None, index=True)
    verified_by_subject: Optional[str] = Field(default=None, index=True)
    verified_by_name: Optional[str] = None
    verified_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1


class StaffAccessApprovalV27(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("approval_ref", name="uq_staffaccessapprovalv27_ref"),
        UniqueConstraint("site_ref", "staff_ref", name="uq_staffaccessapprovalv27_staff"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    approval_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    auth_subject: str = Field(index=True)
    approved_role: str = Field(index=True)
    clinical_authority_status: str = Field(index=True)
    status: str = Field(default="approved", index=True)
    reason: str
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    approved_by_subject: str = Field(index=True)
    approved_by_name: str
    approved_by_role: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    approved_at: datetime = Field(default_factory=utc_now, index=True)
    revoked_at: Optional[datetime] = Field(default=None, index=True)


class SitePolicyV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("site_ref", "policy_key", name="uq_sitepolicyv27_site_key"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    policy_key: str = Field(index=True)
    title: str
    policy_version: str
    status: str = Field(default="draft", index=True)
    rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    owner_role: str
    owner_subject: Optional[str] = Field(default=None, index=True)
    effective_from: Optional[date] = None
    review_due_at: Optional[date] = Field(default=None, index=True)
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    version: int = 1
    updated_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ConfigurationReleaseV27(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("release_ref", name="uq_configurationreleasev27_ref"),
        UniqueConstraint("site_ref", "release_version", name="uq_configurationreleasev27_site_version"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    release_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    release_version: int
    status: str = Field(default="approved", index=True)
    snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    snapshot_hash: str = Field(index=True)
    readiness_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    effective_at: datetime = Field(default_factory=utc_now, index=True)
    approved_by_subject: str = Field(index=True)
    approved_by_name: str
    approved_by_role: str = Field(index=True)
    reason: str
    rollback_of_release_ref: Optional[str] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class ConfigurationChangeV27(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("change_ref", name="uq_configurationchangev27_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    change_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: Optional[str] = Field(default=None, index=True)
    premises_ref: Optional[str] = Field(default=None, index=True)
    entity_type: str = Field(index=True)
    entity_ref: str = Field(index=True)
    action: str = Field(index=True)
    previous_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    new_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    reason: str
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
