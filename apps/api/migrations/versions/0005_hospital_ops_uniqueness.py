"""Backfill hospital operating-system uniqueness constraints.

Revision ID: 0005_hospital_ops_uniqueness
Revises: 0004_hospital_operating_system_v3
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = "0005_hospital_ops_uniqueness"
down_revision: Union[str, None] = "0004_hospital_operating_system_v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("hospitalpremises", "uq_hospitalpremises_ref", ("premises_ref",)),
    ("operationalarea", "uq_operationalarea_premises_ref", ("premises_ref", "area_ref")),
    ("canonicalepisodestate", "uq_canonicalepisode_ref", ("episode_ref",)),
    ("operationalblock", "uq_operationalblock_ref", ("block_ref",)),
    ("operationaldependency", "uq_operationaldependency_ref", ("dependency_ref",)),
    ("operationaldependency", "uq_operationaldependency_edge", ("predecessor_block_ref", "successor_block_ref", "dependency_type")),
    ("operationalcommand", "uq_operationalcommand_ref", ("command_ref",)),
    ("operationalcommand", "uq_operationalcommand_idempotency", ("idempotency_key",)),
    ("operationalconflict", "uq_operationalconflict_ref", ("conflict_ref",)),
    ("boardchangeevent", "uq_boardchangeevent_ref", ("event_ref",)),
    ("scenariorun", "uq_scenariorun_ref", ("run_ref",)),
    ("importbatch", "uq_importbatch_ref", ("batch_ref",)),
    ("importbatch", "uq_importbatch_source_hash", ("premises_ref", "source_hash")),
    ("importreconciliationitem", "uq_importreconciliation_ref", ("item_ref",)),
    ("importreconciliationitem", "uq_importreconciliation_row", ("batch_ref", "row_number")),
)


def _constraint_exists(table_name: str, columns: tuple[str, ...]) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    expected = set(columns)
    for item in inspector.get_unique_constraints(table_name):
        if set(item.get("column_names") or []) == expected:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for table_name, constraint_name, columns in CONSTRAINTS:
        if table_name not in tables or _constraint_exists(table_name, columns):
            continue
        # batch_alter_table works for PostgreSQL and recreates SQLite tables
        # safely where ALTER TABLE cannot add a named unique constraint.
        with op.batch_alter_table(table_name) as batch:
            batch.create_unique_constraint(constraint_name, list(columns))


def downgrade() -> None:
    # These constraints protect idempotency and canonical identity. Removing
    # them automatically would reopen duplicate and lost-update failure modes.
    pass
