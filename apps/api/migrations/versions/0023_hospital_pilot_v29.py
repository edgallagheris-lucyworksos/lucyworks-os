"""Add hospital pilot, simulator, readiness and terminology controls.

Revision ID: 0023_hospital_pilot_v29
Revises: 0022_real_hospital_connection_v28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.hospital_pilot_v29_models import (
    ExportArtifactV29,
    HospitalPilotV29,
    IntegrationSimulatorV29,
    PilotApprovalV29,
    PilotIncidentV29,
    PilotMeasurementV29,
    ReadinessAssessmentV29,
    SimulatorRunV29,
    SimulatorScenarioV29,
    SpeechAdapterV29,
    VeterinaryTerminologyPackV29,
)

revision: str = "0023_hospital_pilot_v29"
down_revision: Union[str, None] = "0022_real_hospital_connection_v28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SpeechAdapterV29.__table__.create(bind=bind, checkfirst=True)
    VeterinaryTerminologyPackV29.__table__.create(bind=bind, checkfirst=True)
    IntegrationSimulatorV29.__table__.create(bind=bind, checkfirst=True)
    SimulatorScenarioV29.__table__.create(bind=bind, checkfirst=True)
    SimulatorRunV29.__table__.create(bind=bind, checkfirst=True)
    ReadinessAssessmentV29.__table__.create(bind=bind, checkfirst=True)
    HospitalPilotV29.__table__.create(bind=bind, checkfirst=True)
    PilotApprovalV29.__table__.create(bind=bind, checkfirst=True)
    PilotIncidentV29.__table__.create(bind=bind, checkfirst=True)
    PilotMeasurementV29.__table__.create(bind=bind, checkfirst=True)
    ExportArtifactV29.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Pilot, readiness, incident, simulator and deployment-pack records are
    # governance evidence and are never removed automatically.
    pass
