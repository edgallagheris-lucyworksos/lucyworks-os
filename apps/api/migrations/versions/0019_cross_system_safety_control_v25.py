"""Add canonical patient, staff and mixed safety-control evidence.

Revision ID: 0019_cross_system_safety_control_v25
Revises: 0018_bounded_pilot_control_v24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.safety_control_v25_models import (
    SafetyAccessEventV25,
    SafetyActionV25,
    SafetyDecisionV25,
    SafetyEscalationV25,
    SafetyLinkV25,
    SafetyRecordV25,
)

revision: str = "0019_cross_system_safety_control_v25"
down_revision: Union[str, None] = "0018_bounded_pilot_control_v24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SafetyRecordV25.__table__.create(bind=bind, checkfirst=True)
    SafetyActionV25.__table__.create(bind=bind, checkfirst=True)
    SafetyDecisionV25.__table__.create(bind=bind, checkfirst=True)
    SafetyLinkV25.__table__.create(bind=bind, checkfirst=True)
    SafetyEscalationV25.__table__.create(bind=bind, checkfirst=True)
    SafetyAccessEventV25.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Safety reports, access evidence, investigations and closure decisions are retained.
    # Destructive rollback requires an approved retention and legal-hold decision.
    pass
