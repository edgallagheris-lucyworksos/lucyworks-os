"""Upgrade existing LucyWorks databases to the control-spine schema.

Revision ID: 0002_control_spine_upgrade
Revises: 0001_lucyworks_baseline
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0002_control_spine_upgrade"
down_revision: Union[str, None] = "0001_lucyworks_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade() -> None:
    schedule_columns = [
        sa.Column("consent_status", sa.String(), nullable=True),
        sa.Column("estimate_status", sa.String(), nullable=True),
        sa.Column("insurance_status", sa.String(), nullable=True),
        sa.Column("pharmacy_ready", sa.Boolean(), nullable=True),
        sa.Column("owner_updated", sa.Boolean(), nullable=True),
        sa.Column("referring_vet_report_sent", sa.Boolean(), nullable=True),
        sa.Column("discharge_clear", sa.Boolean(), nullable=True),
    ]
    for column in schedule_columns:
        _add_if_missing("schedulestateblock", column)

    evidence_columns = [
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("causation_event_ref", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("actor_auth_source", sa.String(), nullable=False, server_default="unverified"),
        sa.Column("human_review_completed_at", sa.DateTime(), nullable=True),
        sa.Column("source_system", sa.String(), nullable=False, server_default="lucyworks-os"),
        sa.Column("source_record_ref", sa.String(), nullable=True),
        sa.Column("payload_schema_version", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("previous_event_hash", sa.String(), nullable=True),
        sa.Column("event_hash", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
    ]
    for column in evidence_columns:
        _add_if_missing("evidenceevent", column)

    estimate_columns = [
        sa.Column("supersedes_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("approved_ceiling", sa.Float(), nullable=True),
        sa.Column("change_reason", sa.String(), nullable=True),
        sa.Column("client_contact_method", sa.String(), nullable=True),
        sa.Column("client_contact_attempted_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_event_ref", sa.String(), nullable=True),
    ]
    for column in estimate_columns:
        _add_if_missing("estimateversion", column)

    consent_columns = [
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_consent_ref", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("client_contact_method", sa.String(), nullable=True),
        sa.Column("communication_notes", sa.String(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
    ]
    for column in consent_columns:
        _add_if_missing("consentrecord", column)


def downgrade() -> None:
    # This migration is intentionally irreversible for clinical audit safety.
    # Dropping evidence and consent columns could destroy regulated records.
    pass
