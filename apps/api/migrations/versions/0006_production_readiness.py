"""Add production-readiness governance tables.

Revision ID: 0006_production_readiness
Revises: 0005_hospital_ops_uniqueness
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.production_readiness_models import (
    PilotObservation,
    PilotRun,
    ReadinessControl,
    ReadinessEvidence,
    SecurityAssessmentRun,
)

revision: str = "0006_production_readiness"
down_revision: Union[str, None] = "0005_hospital_ops_uniqueness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        ReadinessControl.__table__,
        ReadinessEvidence.__table__,
        SecurityAssessmentRun.__table__,
        PilotRun.__table__,
        PilotObservation.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Readiness evidence and pilot observations are governance records. They must
    # be retained or migrated through an approved data-retention process.
    pass
