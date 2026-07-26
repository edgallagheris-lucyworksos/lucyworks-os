"""Add UK veterinary compliance, safety case, hazard and deployment assurance records.

Revision ID: 0011_compliance_safety
Revises: 0010_hospital_command_spine
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.compliance_safety_models import (
    DeploymentProfileV10,
    SafetyCaseV10,
    SafetyHazardV10,
    SafetyReviewV10,
)

revision: str = "0011_compliance_safety"
down_revision: Union[str, None] = "0010_hospital_command_spine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        SafetyCaseV10.__table__,
        SafetyHazardV10.__table__,
        SafetyReviewV10.__table__,
        DeploymentProfileV10.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Safety, review and release records are assurance evidence. A destructive
    # rollback requires an approved retention and migration plan.
    pass
