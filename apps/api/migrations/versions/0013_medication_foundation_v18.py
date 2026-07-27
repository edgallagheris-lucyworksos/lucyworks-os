"""Add the commercial medication catalogue, protocols, calculations and proposals.

Revision ID: 0013_medication_v18
Revises: 0012_referral_identity
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.medication_foundation_v18_models import (
    DoseCalculationV18,
    MedicationProposalV18,
    MedicationProtocolV18,
    ProductImportBatchV18,
    VeterinaryProductV18,
)

revision: str = "0013_medication_v18"
down_revision: Union[str, None] = "0012_referral_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        ProductImportBatchV18.__table__,
        VeterinaryProductV18.__table__,
        MedicationProtocolV18.__table__,
        DoseCalculationV18.__table__,
        MedicationProposalV18.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Product provenance, calculations and prescribing-review evidence are retained.
    # Destructive rollback requires an approved migration and retention plan.
    pass
