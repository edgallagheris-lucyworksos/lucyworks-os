"""Add governed external integration tables.

Revision ID: 0003_external_integrations
Revises: 0002_control_spine_upgrade
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.integration_models import IntegrationConnection, IntegrationEntityLink, IntegrationEnvelope

revision: str = "0003_external_integrations"
down_revision: Union[str, None] = "0002_control_spine_upgrade"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        IntegrationConnection.__table__,
        IntegrationEnvelope.__table__,
        IntegrationEntityLink.__table__,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Integration envelopes and entity links are audit records. Production
    # downgrades must use a reviewed data migration rather than silently
    # deleting the tables and provenance.
    pass
