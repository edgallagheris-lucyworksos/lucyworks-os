"""Add canonical hospital operating system tables.

Revision ID: 0004_hospital_operating_system_v3
Revises: 0003_external_integrations
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from app.hospital_ops_models import (
    BoardChangeEvent,
    CanonicalEpisodeState,
    HospitalPremises,
    ImportBatch,
    ImportReconciliationItem,
    OperationalArea,
    OperationalBlock,
    OperationalCommand,
    OperationalConflict,
    OperationalDependency,
    ScenarioRun,
)

revision: str = "0004_hospital_operating_system_v3"
down_revision: Union[str, None] = "0003_external_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Alembic creates version_num as VARCHAR(32) by default. This revision ID is
    # longer than 32 characters, so a completely fresh PostgreSQL database would
    # otherwise fail after the upgrade body when Alembic records this revision.
    # Widen the control column before Alembic updates it. Existing databases at a
    # later revision are unaffected because this code only runs during 0004.
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    for table in (
        HospitalPremises.__table__,
        OperationalArea.__table__,
        CanonicalEpisodeState.__table__,
        OperationalBlock.__table__,
        OperationalDependency.__table__,
        OperationalCommand.__table__,
        OperationalConflict.__table__,
        BoardChangeEvent.__table__,
        ScenarioRun.__table__,
        ImportBatch.__table__,
        ImportReconciliationItem.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Operational commands, evidence links and simulation/import provenance are
    # audit-bearing data. A production downgrade requires a reviewed export and
    # migration plan rather than destructive automatic table deletion.
    pass
