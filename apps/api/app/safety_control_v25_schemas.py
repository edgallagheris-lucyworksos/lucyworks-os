from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SafetyRecordCreate(BaseModel):
    recordRef: str | None = None
    recordType: str
    domain: str
    confidentiality: str = "standard"
    reporterVisibility: str | None = None
    severity: str = "amber"
    title: str
    summary: str
    description: str = ""
    premisesRef: str = "default-premises"
    patientRef: str | None = None
    episodeRef: str | None = None
    affectedStaffSubject: str | None = None
    affectedStaffName: str | None = None
    sourceModule: str = "manual"
    sourceRecordRef: str | None = None
    immediateRisk: bool = False
    safetyHoldRequested: bool = False
    operationalImpact: dict[str, Any] = Field(default_factory=dict)
    protectiveSummary: str | None = None
    owners: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    conflictSubjects: list[str] = Field(default_factory=list)
    dueAt: datetime | None = None
    links: list[dict[str, Any]] = Field(default_factory=list)


class TriagePayload(BaseModel):
    expectedVersion: int
    severity: str | None = None
    confidentiality: str | None = None
    status: str | None = None
    immediateRisk: bool | None = None
    safetyHoldRequested: bool | None = None
    operationalImpact: dict[str, Any] | None = None
    protectiveSummary: str | None = None
    dueAt: datetime | None = None
    reason: str


class OwnerAssignmentPayload(BaseModel):
    expectedVersion: int
    owners: dict[str, dict[str, str | None]]
    reason: str


class OwnershipDecisionPayload(BaseModel):
    expectedVersion: int
    decision: str
    reason: str


class ConflictPayload(BaseModel):
    expectedVersion: int
    subject: str
    reason: str


class SafetyActionCreate(BaseModel):
    actionRef: str | None = None
    actionType: str
    title: str
    description: str = ""
    owner: dict[str, str]
    dueAt: datetime | None = None
    requiresIndependentVerification: bool | None = None


class SafetyActionComplete(BaseModel):
    expectedVersion: int
    completionEvidence: str


class SafetyActionVerify(BaseModel):
    expectedVersion: int
    decision: str
    note: str


class EscalationCreate(BaseModel):
    escalationRef: str | None = None
    reason: str
    to: dict[str, str | None] = Field(default_factory=lambda: {"role": "governance_lead"})
    dueAt: datetime | None = None


class ClosureReviewPayload(BaseModel):
    decision: str
    reason: str
    rootCause: str | None = None
    recurrenceControls: list[str] = Field(default_factory=list)


class ClosePayload(BaseModel):
    expectedVersion: int
    rootCause: str | None = None
    recurrenceControls: list[str] = Field(default_factory=list)
    reason: str


class ReopenPayload(BaseModel):
    expectedVersion: int
    reason: str
