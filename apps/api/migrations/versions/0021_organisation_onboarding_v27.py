"""Add governed organisation onboarding and configuration releases.

Revision ID: 0021_organisation_onboarding_v27
Revises: 0020_operational_convergence_v26
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.organisation_onboarding_v27_models import (
    ConfigurationChangeV27,
    ConfigurationReleaseV27,
    OnboardingDepartmentV27,
    OnboardingEquipmentV27,
    OnboardingOrganisationV27,
    OnboardingRoomV27,
    OnboardingServiceV27,
    OnboardingSiteV27,
    OnboardingStaffV27,
    SitePolicyV27,
    StaffAccessApprovalV27,
    StaffCompetencyV27,
    StaffCredentialV27,
    StaffImportBatchV27,
)

revision: str = "0021_organisation_onboarding_v27"
down_revision: Union[str, None] = "0020_operational_convergence_v26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    OnboardingOrganisationV27.__table__.create(bind=bind, checkfirst=True)
    OnboardingSiteV27.__table__.create(bind=bind, checkfirst=True)
    OnboardingDepartmentV27.__table__.create(bind=bind, checkfirst=True)
    OnboardingServiceV27.__table__.create(bind=bind, checkfirst=True)
    OnboardingRoomV27.__table__.create(bind=bind, checkfirst=True)
    OnboardingEquipmentV27.__table__.create(bind=bind, checkfirst=True)
    StaffImportBatchV27.__table__.create(bind=bind, checkfirst=True)
    OnboardingStaffV27.__table__.create(bind=bind, checkfirst=True)
    StaffCredentialV27.__table__.create(bind=bind, checkfirst=True)
    StaffCompetencyV27.__table__.create(bind=bind, checkfirst=True)
    StaffAccessApprovalV27.__table__.create(bind=bind, checkfirst=True)
    SitePolicyV27.__table__.create(bind=bind, checkfirst=True)
    ConfigurationReleaseV27.__table__.create(bind=bind, checkfirst=True)
    ConfigurationChangeV27.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Approved configuration, access decisions and immutable change evidence are
    # retained. Destructive rollback requires an explicit legal, safety and data-
    # retention decision outside an automatic migration downgrade.
    pass
