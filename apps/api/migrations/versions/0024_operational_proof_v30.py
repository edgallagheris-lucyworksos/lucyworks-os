"""Add connected operational proof and mobile acceptance evidence.

Revision ID: 0024_operational_proof_v30
Revises: 0023_hospital_pilot_v29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.operational_proof_v30_models import (
    MobileAcceptanceV30,
    OperationalProofRunV30,
    OperationalProofScenarioV30,
    OperationalProofStepV30,
)

revision: str = "0024_operational_proof_v30"
down_revision: Union[str, None] = "0023_hospital_pilot_v29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    OperationalProofRunV30.__table__.create(bind=bind, checkfirst=True)
    OperationalProofStepV30.__table__.create(bind=bind, checkfirst=True)
    OperationalProofScenarioV30.__table__.create(bind=bind, checkfirst=True)
    MobileAcceptanceV30.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Operational proof, stress and mobile records form deployment evidence.
    # Destructive removal requires an explicit retention decision.
    pass
