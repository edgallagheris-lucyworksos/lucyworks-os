from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpeechAdapterV29(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("adapter_ref", name="uq_speechadapterv29_ref"),
        UniqueConstraint("site_ref", "name", name="uq_speechadapterv29_site_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    adapter_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    provider_ref: str = Field(index=True)
    name: str
    adapter_type: str = Field(default="browser", index=True)
    processing_location: str = Field(default="device", index=True)
    protocol: str = Field(default="browser_recognition", index=True)
    reconnect_enabled: bool = True
    max_reconnect_attempts: int = 5
    reconnect_backoff_ms: int = 1000
    fallback_provider_ref: Optional[str] = Field(default=None, index=True)
    minimum_confidence: float = 0.78
    maximum_latency_ms: int = 2000
    network_requirements: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    configuration: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    last_test_status: str = Field(default="not_tested", index=True)
    last_test_detail: Optional[str] = None
    last_test_results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    last_test_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class VeterinaryTerminologyPackV29(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("pack_ref", name="uq_vetterminologypackv29_ref"),
        UniqueConstraint("site_ref", "name", "release_label", name="uq_vetterminologypackv29_site_release"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    pack_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    name: str
    release_label: str = Field(default="v1", index=True)
    language: str = Field(default="en-GB", index=True)
    categories: dict[str, list[str]] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    correction_rules: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    abbreviations: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    site_terms: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = Field(default=None, index=True)
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class IntegrationSimulatorV29(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("simulator_ref", name="uq_integrationsimulatorv29_ref"),
        UniqueConstraint("site_ref", "connector_type", "name", name="uq_integrationsimulatorv29_site_type_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    simulator_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    connector_ref: str = Field(index=True)
    connector_type: str = Field(index=True)
    name: str
    seed: int = 29
    default_latency_ms: int = 50
    synthetic_banner: str = "SYNTHETIC TEST DATA - NOT A CLINICAL RECORD"
    configuration: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    last_test_status: str = Field(default="not_tested", index=True)
    last_test_detail: Optional[str] = None
    last_test_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SimulatorScenarioV29(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("scenario_ref", name="uq_simulatorscenariov29_ref"),
        UniqueConstraint("simulator_ref", "scenario_code", name="uq_simulatorscenariov29_sim_code"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_ref: str = Field(index=True)
    simulator_ref: str = Field(index=True)
    scenario_code: str = Field(index=True)
    title: str
    fault_type: str = Field(index=True)
    event_type: str = Field(default="synthetic_update", index=True)
    event_count: int = 1
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    expected_detection: str
    critical: bool = True
    status: str = Field(default="ready", index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SimulatorRunV29(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("run_ref", name="uq_simulatorrunv29_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True)
    scenario_ref: str = Field(index=True)
    simulator_ref: str = Field(index=True)
    pilot_ref: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="running", index=True)
    detection_status: str = Field(default="pending", index=True)
    injected_event_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    affected_synthetic_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    started_by_subject: str = Field(index=True)
    started_by_name: str
    started_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    evidence_ref: Optional[str] = Field(default=None, index=True)


class ReadinessAssessmentV29(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("assessment_ref", name="uq_readinessassessmentv29_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    assessment_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    pilot_ref: Optional[str] = Field(default=None, index=True)
    overall_status: str = Field(default="NOT_READY", index=True)
    score: int = 0
    checks: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    blockers: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    device_diagnostics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_chain_ok: bool = False
    migration_head: Optional[str] = Field(default=None, index=True)
    assessed_by_subject: str = Field(index=True)
    assessed_by_name: str
    assessed_by_role: str = Field(index=True)
    assessed_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_ref: Optional[str] = Field(default=None, index=True)


class HospitalPilotV29(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("pilot_ref", name="uq_hospitalpilotv29_ref"),
        UniqueConstraint("site_ref", "name", name="uq_hospitalpilotv29_site_name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    pilot_ref: str = Field(index=True)
    authority_ref: Optional[str] = Field(default=None, index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    name: str
    department: str = Field(default="referral", index=True)
    service_line: str = Field(default="referral", index=True)
    mode: str = Field(default="synthetic", index=True)
    status: str = Field(default="draft", index=True)
    case_limit: int = 25
    cases_started: int = 0
    start_at: Optional[datetime] = Field(default=None, index=True)
    end_at: Optional[datetime] = Field(default=None, index=True)
    allowed_device_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    allowed_provider_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    allowed_simulator_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    success_criteria: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    stop_criteria: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    rollback_plan: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    auto_stop_enabled: bool = True
    readiness_assessment_ref: Optional[str] = Field(default=None, index=True)
    operations_approved_by_subject: Optional[str] = Field(default=None, index=True)
    operations_approved_by_name: Optional[str] = None
    operations_approved_at: Optional[datetime] = Field(default=None, index=True)
    clinical_approved_by_subject: Optional[str] = Field(default=None, index=True)
    clinical_approved_by_name: Optional[str] = None
    clinical_approved_at: Optional[datetime] = Field(default=None, index=True)
    accountable_owner_subject: str = Field(index=True)
    accountable_owner_name: str
    clinical_owner_subject: Optional[str] = Field(default=None, index=True)
    clinical_owner_name: Optional[str] = None
    stopped_reason: Optional[str] = None
    activated_at: Optional[datetime] = Field(default=None, index=True)
    stopped_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class PilotApprovalV29(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("approval_ref", name="uq_pilotapprovalv29_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    approval_ref: str = Field(index=True)
    pilot_ref: str = Field(index=True)
    approval_type: str = Field(index=True)
    decision: str = Field(index=True)
    reason: str
    pilot_version: int
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_ref: Optional[str] = Field(default=None, index=True)


class PilotIncidentV29(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("incident_ref", name="uq_pilotincidentv29_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_ref: str = Field(index=True)
    pilot_ref: str = Field(index=True)
    severity: str = Field(default="amber", index=True)
    category: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    synthetic: bool = True
    description: str
    immediate_action: str
    status: str = Field(default="open", index=True)
    resolution: Optional[str] = None
    created_by_subject: str = Field(index=True)
    created_by_name: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
    resolved_by_subject: Optional[str] = Field(default=None, index=True)
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    evidence_ref: Optional[str] = Field(default=None, index=True)
    version: int = 1


class PilotMeasurementV29(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("measurement_ref", name="uq_pilotmeasurementv29_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    measurement_ref: str = Field(index=True)
    pilot_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    synthetic: bool = True
    metric_type: str = Field(index=True)
    value: float
    unit: str
    baseline_value: Optional[float] = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    recorded_by_subject: str = Field(index=True)
    recorded_by_name: str
    recorded_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_ref: Optional[str] = Field(default=None, index=True)


class ExportArtifactV29(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("artifact_ref", name="uq_exportartifactv29_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    pilot_ref: Optional[str] = Field(default=None, index=True)
    artifact_type: str = Field(index=True)
    status: str = Field(default="generated", index=True)
    content: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_by_subject: str = Field(index=True)
    generated_by_name: str
    generated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_ref: Optional[str] = Field(default=None, index=True)
    version: int = 1
