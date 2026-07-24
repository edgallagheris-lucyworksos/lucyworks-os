"""Add BVS configuration, workforce, referral and historical replay tables.

Revision ID: 0007_bvs_configuration_workforce_referrals
Revises: 0006_production_readiness
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.bvs_v6_models import (
    ConfigurationClaim,
    ConfigurationVerificationTask,
    CoverageRequirement,
    HistoricalReplayEvent,
    HistoricalReplayRun,
    HospitalConfigurationRecord,
    ReferralIntake,
    ReferralIntakeEvent,
    WorkforceCompetency,
    WorkforceProfile,
)

revision: str = "0007_bvs_configuration_workforce_referrals"
down_revision: Union[str, None] = "0006_production_readiness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        HospitalConfigurationRecord.__table__,
        ConfigurationClaim.__table__,
        ConfigurationVerificationTask.__table__,
        WorkforceProfile.__table__,
        WorkforceCompetency.__table__,
        CoverageRequirement.__table__,
        ReferralIntake.__table__,
        ReferralIntakeEvent.__table__,
        HistoricalReplayRun.__table__,
        HistoricalReplayEvent.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # These tables contain governance, referral and validation evidence. Removal
    # requires an approved retention/migration decision rather than an automatic downgrade.
    pass
