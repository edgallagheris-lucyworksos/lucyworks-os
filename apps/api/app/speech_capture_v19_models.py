from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpeechCaptureV19(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("capture_ref", name="uq_speechcapturev19_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    capture_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    capture_mode: str = Field(index=True)
    source_type: str = Field(default="typed", index=True)
    language: str = Field(default="en-GB", index=True)
    transcript_text: str
    redacted_transcript_text: Optional[str] = None
    raw_audio_retained: bool = False
    notice_version: str = Field(default="v19-default", index=True)
    notice_acknowledged: bool = False
    status: str = Field(default="draft", index=True)
    created_by_subject: str = Field(index=True)
    created_by_name: str
    created_by_role: str = Field(index=True)
    reviewed_by_subject: Optional[str] = Field(default=None, index=True)
    reviewed_by_name: Optional[str] = None
    reviewed_by_role: Optional[str] = Field(default=None, index=True)
    confirmed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class SpeechDraftV19(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("draft_ref", name="uq_speechdraftv19_ref"),
        UniqueConstraint("capture_ref", name="uq_speechdraftv19_capture"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    draft_ref: str = Field(index=True)
    capture_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    proposed_sections: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    suggestions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    uncertainties: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    negations: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    medication_proposals: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    observations: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    task_proposals: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    reviewer_edits: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    accepted_suggestion_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    rejected_suggestion_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    final_text: Optional[str] = None
    clinical_note_ref: Optional[str] = Field(default=None, index=True)
    work_item_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="proposed", index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class SpeechPhrasePackV19(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("phrase_pack_ref", name="uq_speechphrasepackv19_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    phrase_pack_ref: str = Field(index=True)
    organisation_ref: str = Field(default="reference", index=True)
    name: str = Field(index=True)
    terms: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    replacements: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
