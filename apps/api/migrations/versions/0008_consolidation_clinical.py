"""Add secure sessions, durable events, canonical shadow, retry and clinical execution tables.

Revision ID: 0008_consolidation_clinical
Revises: 0007_bvs_config_workforce
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.clinical_execution_models import (
    AnaesthesiaRecord,
    ClinicalObservation,
    ControlledDrugLedgerEntry,
    DiagnosticWorkItem,
    DischargePlan,
    InventoryItem,
    MedicationAdministration,
    MedicationOrder,
    SampleChainEvent,
    TreatmentTask,
)
from app.v7_models import AuthSession, CanonicalShadowComparison, DurableEvent, IntegrationRetryJob, LegacyWriteRetirement

revision: str = "0008_consolidation_clinical"
down_revision: Union[str, None] = "0007_bvs_config_workforce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        AuthSession.__table__,
        DurableEvent.__table__,
        CanonicalShadowComparison.__table__,
        IntegrationRetryJob.__table__,
        LegacyWriteRetirement.__table__,
        MedicationOrder.__table__,
        MedicationAdministration.__table__,
        AnaesthesiaRecord.__table__,
        ClinicalObservation.__table__,
        TreatmentTask.__table__,
        ControlledDrugLedgerEntry.__table__,
        InventoryItem.__table__,
        DiagnosticWorkItem.__table__,
        SampleChainEvent.__table__,
        DischargePlan.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Clinical, security and governance evidence requires an approved migration
    # and retention decision. Automatic destructive downgrade is disabled.
    pass
