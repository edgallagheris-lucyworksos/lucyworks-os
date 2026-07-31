from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.real_hospital_connection_v28_models import SpeechSegmentV28, SpeechSessionV28
from app.real_hospital_connection_v28_routes import (
    CAPTURE_ROLES,
    SpeechSegmentAppend,
    SpeechSessionStart,
    append_speech_segment as append_speech_segment_original,
    start_speech_session as start_speech_session_original,
)

router = APIRouter(prefix="/api/v28/deployment", tags=["real-hospital-connection-speech-v28-hardening"])


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrictSpeechSessionStart(StrictModel):
    providerRef: str
    siteRef: str
    episodeRef: str
    captureMode: str = "clinical_dictation"
    language: str = "en-GB"
    noticeVersion: str = "v28-default"
    noticeAcknowledged: bool = False
    rawAudioRetained: bool = False
    deviceDiagnostics: dict[str, Any] = PydanticField(default_factory=dict)


class StrictSpeechSegmentAppend(StrictModel):
    expectedVersion: int
    sequence: int = PydanticField(ge=1)
    text: str = PydanticField(min_length=1, max_length=10000)
    confidence: float | None = PydanticField(default=None, ge=0, le=1)
    startedMs: int | None = PydanticField(default=None, ge=0)
    endedMs: int | None = PydanticField(default=None, ge=0)
    speakerLabel: str | None = None
    isFinal: bool = True
    source: str = "browser"
    words: list[dict[str, Any]] = PydanticField(default_factory=list)


@router.post("/speech/sessions")
def start_speech_session_hardened(
    payload: StrictSpeechSessionStart,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    return start_speech_session_original(SpeechSessionStart(**payload.model_dump()), session, auth)


@router.post("/speech/sessions/{session_ref}/segments")
def append_speech_segment_hardened(
    session_ref: str,
    payload: StrictSpeechSegmentAppend,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
) -> dict[str, Any]:
    speech_session = session.exec(select(SpeechSessionV28).where(SpeechSessionV28.session_ref == session_ref)).first()
    if not speech_session:
        raise HTTPException(status_code=404, detail="speech session not found")

    existing = session.exec(select(SpeechSegmentV28).where(
        SpeechSegmentV28.session_ref == session_ref,
        SpeechSegmentV28.sequence == payload.sequence,
    )).first()
    if not existing:
        last = session.exec(select(SpeechSegmentV28).where(
            SpeechSegmentV28.session_ref == session_ref,
        ).order_by(SpeechSegmentV28.sequence.desc())).first()
        expected_sequence = (last.sequence + 1) if last else 1
        if payload.sequence != expected_sequence:
            raise HTTPException(status_code=409, detail={
                "code": "speech_segment_sequence_gap",
                "message": "Speech segments must be appended without gaps.",
                "expectedSequence": expected_sequence,
                "receivedSequence": payload.sequence,
                "currentSessionVersion": speech_session.version,
            })

    return append_speech_segment_original(
        session_ref,
        SpeechSegmentAppend(**payload.model_dump()),
        session,
        auth,
    )
