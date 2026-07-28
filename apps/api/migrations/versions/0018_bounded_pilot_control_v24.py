"""Add bounded pilot authority, approval, UAT and shadow evidence.

Revision ID: 0018_bounded_pilot_control_v24
Revises: 0017_automation_operator_control_v23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.pilot_control_v24_models import (
    PilotApprovalV24,
    PilotAuthorityV24,
    PilotControlActionV24,
    PilotShadowComparisonV24,
    PilotUATScenarioV24,
)

revision: str = "0018_bounded_pilot_control_v24"
down_revision: Union[str, None] = "0017_automation_operator_control_v23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    PilotAuthorityV24.__table__.create(bind=bind, checkfirst=True)
    PilotApprovalV24.__table__.create(bind=bind, checkfirst=True)
    PilotControlActionV24.__table__.create(bind=bind, checkfirst=True)
    PilotShadowComparisonV24.__table__.create(bind=bind, checkfirst=True)
    PilotUATScenarioV24.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Pilot authority, approvals and recovery decisions are retained as governance evidence.
    # Destructive rollback requires an approved retention and legal-hold decision.
    pass
