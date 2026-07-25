"""Add detailed longitudinal patient, anaesthesia, inpatient and commercial records.

Revision ID: 0009_detailed_hospital
Revises: 0008_consolidation_clinical
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.detailed_hospital_models import (
    AnaesthesiaChartV8,
    AnaesthesiaDrugEventV8,
    AnaesthesiaObservationV8,
    ClinicalDocumentV8,
    ClinicalEncounterV8,
    ClinicalNoteV8,
    CommunicationEventV8,
    EstimateLineV8,
    EstimateV8,
    FinancialTransactionV8,
    FluidBalanceEntryV8,
    FluidPlanV8,
    FormularyDoseRuleV8,
    FormularyMedicineV8,
    ImplantTraceV8,
    InpatientCarePlanV8,
    InpatientChartEntryV8,
    InsuranceCaseV8,
    MedicationSafetyReviewV8,
    OwnerAccountV8,
    PatientAllergyV8,
    PatientClinicalRecordV8,
    PatientOwnerLinkV8,
    PatientProblemV8,
    PatientWeightV8,
    ProcedureRecordV8,
)

revision: str = "0009_detailed_hospital"
down_revision: Union[str, None] = "0008_consolidation_clinical"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        OwnerAccountV8.__table__,
        PatientClinicalRecordV8.__table__,
        PatientOwnerLinkV8.__table__,
        PatientProblemV8.__table__,
        PatientAllergyV8.__table__,
        PatientWeightV8.__table__,
        ClinicalEncounterV8.__table__,
        ClinicalNoteV8.__table__,
        FormularyMedicineV8.__table__,
        FormularyDoseRuleV8.__table__,
        MedicationSafetyReviewV8.__table__,
        AnaesthesiaChartV8.__table__,
        AnaesthesiaObservationV8.__table__,
        AnaesthesiaDrugEventV8.__table__,
        FluidPlanV8.__table__,
        FluidBalanceEntryV8.__table__,
        InpatientCarePlanV8.__table__,
        InpatientChartEntryV8.__table__,
        ProcedureRecordV8.__table__,
        ImplantTraceV8.__table__,
        EstimateV8.__table__,
        EstimateLineV8.__table__,
        InsuranceCaseV8.__table__,
        FinancialTransactionV8.__table__,
        CommunicationEventV8.__table__,
        ClinicalDocumentV8.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # These tables contain clinical, financial and client-communication evidence.
    # Automatic destructive downgrade requires an approved retention decision.
    pass
