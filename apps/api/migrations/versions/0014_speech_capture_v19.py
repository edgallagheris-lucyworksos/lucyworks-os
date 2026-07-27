"""Add veterinary speech capture, reviewed drafts and phrase packs.

Revision ID: 0014_speech_capture_v19
Revises: 0013_medication_v18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.speech_capture_v19_models import SpeechCaptureV19, SpeechDraftV19, SpeechPhrasePackV19

revision: str = "0014_speech_capture_v19"
down_revision: Union[str, None] = "0013_medication_v18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        SpeechCaptureV19.__table__,
        SpeechDraftV19.__table__,
        SpeechPhrasePackV19.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Transcript, review and confirmation evidence is retained.
    # Destructive rollback requires an approved retention decision.
    pass
