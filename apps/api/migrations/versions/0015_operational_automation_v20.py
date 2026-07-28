"""Add governed operational automation decisions.

Revision ID: 0015_operational_automation_v20
Revises: 0014_speech_capture_v19
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.operational_automation_v20_models import AutomationDecisionV20

revision: str = "0015_operational_automation_v20"
down_revision: Union[str, None] = "0014_speech_capture_v19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    AutomationDecisionV20.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Automation decisions and linked evidence are retained.
    # Destructive rollback requires an approved retention decision.
    pass
