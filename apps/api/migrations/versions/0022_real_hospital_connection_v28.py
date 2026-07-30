"""Add governed speech sessions and real-hospital integration controls.

Revision ID: 0022_real_hospital_connection_v28
Revises: 0021_organisation_onboarding_v27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.real_hospital_connection_v28_models import (
    IntegrationConnectorV28,
    IntegrationEventV28,
    IntegrationPromotionV28,
    ReconciliationItemV28,
    SpeechProviderV28,
    SpeechSegmentV28,
    SpeechSessionV28,
)

revision: str = "0022_real_hospital_connection_v28"
down_revision: Union[str, None] = "0021_organisation_onboarding_v27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SpeechProviderV28.__table__.create(bind=bind, checkfirst=True)
    SpeechSessionV28.__table__.create(bind=bind, checkfirst=True)
    SpeechSegmentV28.__table__.create(bind=bind, checkfirst=True)
    IntegrationConnectorV28.__table__.create(bind=bind, checkfirst=True)
    IntegrationPromotionV28.__table__.create(bind=bind, checkfirst=True)
    IntegrationEventV28.__table__.create(bind=bind, checkfirst=True)
    ReconciliationItemV28.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Speech, connector, promotion and reconciliation records form deployment and
    # clinical-governance evidence. Destructive removal requires an explicit
    # retention decision and is not performed automatically.
    pass
