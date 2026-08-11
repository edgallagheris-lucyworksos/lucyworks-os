"""Add regulated workflow, estimate governance, client evidence and AI provenance.

Revision ID: 0025_regulated_workflow_v32
Revises: 0024_operational_proof_v30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.regulated_workflow_v32_extension_models import ChargeProvenanceV32, ComplaintV32, PrescriptionChoiceV32
from app.regulated_workflow_v32_models import AIProvenanceV32, EstimateGovernanceV32, ServicePriceV32

revision: str = "0025_regulated_workflow_v32"
down_revision: Union[str, None] = "0024_operational_proof_v30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    ServicePriceV32.__table__.create(bind=bind, checkfirst=True)
    EstimateGovernanceV32.__table__.create(bind=bind, checkfirst=True)
    AIProvenanceV32.__table__.create(bind=bind, checkfirst=True)
    ChargeProvenanceV32.__table__.create(bind=bind, checkfirst=True)
    ComplaintV32.__table__.create(bind=bind, checkfirst=True)
    PrescriptionChoiceV32.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # These tables contain regulatory, financial and provenance evidence.
    # Destructive removal requires an explicit retention decision rather than
    # an automatic downgrade.
    pass
