"""Add canonical referral, consent, handover, transition and closure records.

Revision ID: 0010_hospital_command_spine
Revises: 0009_detailed_hospital
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.hospital_command_models import (
    ConsentAuthorisationV9,
    EpisodeCheckpointV9,
    EpisodeClosureV9,
    EpisodeHandoverV9,
    EpisodeTransitionV9,
    ReferralIntakeV9,
)

revision: str = "0010_hospital_command_spine"
down_revision: Union[str, None] = "0009_detailed_hospital"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        ReferralIntakeV9.__table__,
        ConsentAuthorisationV9.__table__,
        EpisodeHandoverV9.__table__,
        EpisodeCheckpointV9.__table__,
        EpisodeTransitionV9.__table__,
        EpisodeClosureV9.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # These records form the legal and operational command history for a case.
    # Destructive rollback requires a reviewed retention and migration plan.
    pass
