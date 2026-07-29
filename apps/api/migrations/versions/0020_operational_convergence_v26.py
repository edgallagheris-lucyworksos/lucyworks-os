"""Add authorised operating context and canonical command convergence.

Revision ID: 0020_operational_convergence_v26
Revises: 0019_cross_system_safety_control_v25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.operational_context_v26_models import (
    ActiveOperatingContextV26,
    CanonicalCommandV26,
    ContextSwitchEvidenceV26,
    LegacyRouteConvergenceV26,
    OperationalImpactV26,
    OrganisationV26,
    SiteMembershipV26,
    SiteV26,
)

revision: str = "0020_operational_convergence_v26"
down_revision: Union[str, None] = "0019_cross_system_safety_control_v25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    OrganisationV26.__table__.create(bind=bind, checkfirst=True)
    SiteV26.__table__.create(bind=bind, checkfirst=True)
    SiteMembershipV26.__table__.create(bind=bind, checkfirst=True)
    ActiveOperatingContextV26.__table__.create(bind=bind, checkfirst=True)
    ContextSwitchEvidenceV26.__table__.create(bind=bind, checkfirst=True)
    CanonicalCommandV26.__table__.create(bind=bind, checkfirst=True)
    LegacyRouteConvergenceV26.__table__.create(bind=bind, checkfirst=True)
    OperationalImpactV26.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Context, command and site-attribution evidence is retained. Destructive
    # rollback requires an approved retention, legal-hold and hospital-safety decision.
    pass
