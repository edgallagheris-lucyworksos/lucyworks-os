"""Add audited automation operator actions.

Revision ID: 0017_automation_operator_control_v23
Revises: 0016_event_driven_automation_v22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from app.automation_operator_control_v23_models import AutomationOperatorActionV23

revision: str = "0017_automation_operator_control_v23"
down_revision: Union[str, None] = "0016_event_driven_automation_v22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    AutomationOperatorActionV23.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Operator authorisation, retry and reconciliation actions are retained for auditability.
    # Destructive rollback requires an approved retention decision.
    pass
