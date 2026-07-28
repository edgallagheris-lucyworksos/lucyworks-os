"""Add event-driven automation configuration and durable triggers.

Revision ID: 0016_event_driven_automation_v22
Revises: 0015_operational_automation_v20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.event_driven_automation_v22_models import AutomationRuntimeConfigV22, AutomationTriggerV22

revision: str = "0016_event_driven_automation_v22"
down_revision: Union[str, None] = "0015_operational_automation_v20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    AutomationRuntimeConfigV22.__table__.create(bind=bind, checkfirst=True)
    AutomationTriggerV22.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Automation trigger history and configuration are retained for auditability.
    # Destructive rollback requires an approved retention decision.
    pass
