"""Add referral identity intake, duplicate review, document, triage and access-review records.

Revision ID: 0012_referral_identity
Revises: 0011_compliance_safety
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.referral_identity_v12_models import (
    AccessReviewV12,
    IdentityMatchReviewV12,
    ReferralDocumentV12,
    ReferralIdentityIntakeV12,
    ReferralTriageV12,
)

revision: str = "0012_referral_identity"
down_revision: Union[str, None] = "0011_compliance_safety"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        ReferralIdentityIntakeV12.__table__,
        IdentityMatchReviewV12.__table__,
        ReferralDocumentV12.__table__,
        ReferralTriageV12.__table__,
        AccessReviewV12.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Identity decisions, referral provenance and access reviews are audit evidence.
    # Destructive rollback requires an approved retention and migration plan.
    pass
