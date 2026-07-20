from __future__ import annotations

import hashlib

from sqlalchemy.orm.attributes import set_committed_value
from sqlmodel import Session, select

from app import hospital_ops_service as service
from app import hospital_ops_extensions as extensions
from app.hospital_ops_models import (
    CanonicalEpisodeState,
    ImportBatch,
    ImportReconciliationItem,
    OperationalBlock,
)


_original_detect_constraints = service.detect_constraints
_original_patch_block = service.patch_block
_original_transition_episode = service.transition_episode
_original_apply_propagated_delay = service.apply_propagated_delay
_original_commit_import = service.commit_import
_original_preview_import = service.preview_import
_original_patch_episode_gates = extensions.patch_episode_gates
_original_resolve_reconciliation_item = extensions.resolve_reconciliation_item


def detect_constraints_with_normalised_datetimes(
    session: Session,
    premises_ref: str,
    operational_date,
    persist: bool = True,
):
    """Normalise persisted timestamps without creating phantom updates.

    SQLite returns timezone-naive values even when request-created objects are
    timezone-aware. PostgreSQL retains timezone metadata. The committed-value
    assignment normalises the session identity map but does not mark the rows
    dirty merely because a read-side constraint check occurred.
    """

    rows = session.exec(
        select(OperationalBlock).where(
            OperationalBlock.premises_ref == premises_ref,
            OperationalBlock.operational_date == operational_date,
        )
    ).all()
    for row in rows:
        set_committed_value(row, "starts_at", service.normalise_dt(row.starts_at))
        set_committed_value(row, "ends_at", service.normalise_dt(row.ends_at))
    return _original_detect_constraints(session, premises_ref, operational_date, persist=persist)


def patch_block_with_row_lock(session: Session, block_ref: str, payload, auth):
    """Serialise competing writes before checking expectedVersion."""

    session.exec(
        select(OperationalBlock)
        .where(OperationalBlock.block_ref == block_ref)
        .with_for_update()
    ).first()
    return _original_patch_block(session, block_ref, payload, auth)


def transition_episode_with_row_lock(session: Session, episode_ref: str, payload, auth):
    session.exec(
        select(CanonicalEpisodeState)
        .where(CanonicalEpisodeState.episode_ref == episode_ref)
        .with_for_update()
    ).first()
    return _original_transition_episode(session, episode_ref, payload, auth)


def patch_episode_gates_with_row_lock(session: Session, episode_ref: str, payload, auth):
    session.exec(
        select(CanonicalEpisodeState)
        .where(CanonicalEpisodeState.episode_ref == episode_ref)
        .with_for_update()
    ).first()
    return _original_patch_episode_gates(session, episode_ref, payload, auth)


def propagated_delay_with_ordered_locks(session: Session, block_ref: str, payload, auth):
    source = session.exec(
        select(OperationalBlock)
        .where(OperationalBlock.block_ref == block_ref)
        .with_for_update()
    ).first()
    if source:
        # Lock every potentially connected block in deterministic order before
        # previewing dependencies. This prevents deadlocks and ensures every
        # expected version is checked against one consistent operating plan.
        session.exec(
            select(OperationalBlock)
            .where(
                OperationalBlock.premises_ref == source.premises_ref,
                OperationalBlock.operational_date == source.operational_date,
            )
            .order_by(OperationalBlock.block_ref)
            .with_for_update()
        ).all()
    return _original_apply_propagated_delay(session, block_ref, payload, auth)


def preview_import_idempotently(session: Session, payload, auth):
    content = str(payload.get("content") or "")
    premises_ref = str(payload.get("premisesRef") or "default-premises")
    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = session.exec(
        select(ImportBatch).where(
            ImportBatch.premises_ref == premises_ref,
            ImportBatch.source_hash == source_hash,
        )
    ).first()
    if existing:
        return existing
    return _original_preview_import(session, payload, auth)


def commit_import_with_batch_lock(session: Session, batch_ref: str, auth):
    session.exec(
        select(ImportBatch)
        .where(ImportBatch.batch_ref == batch_ref)
        .with_for_update()
    ).first()
    return _original_commit_import(session, batch_ref, auth)


def resolve_reconciliation_with_locks(session: Session, batch_ref: str, item_ref: str, corrected_record, auth):
    session.exec(
        select(ImportBatch)
        .where(ImportBatch.batch_ref == batch_ref)
        .with_for_update()
    ).first()
    session.exec(
        select(ImportReconciliationItem)
        .where(
            ImportReconciliationItem.batch_ref == batch_ref,
            ImportReconciliationItem.item_ref == item_ref,
        )
        .with_for_update()
    ).first()
    return _original_resolve_reconciliation_item(session, batch_ref, item_ref, corrected_record, auth)


service.detect_constraints = detect_constraints_with_normalised_datetimes
service.patch_block = patch_block_with_row_lock
service.transition_episode = transition_episode_with_row_lock
service.apply_propagated_delay = propagated_delay_with_ordered_locks
service.preview_import = preview_import_idempotently
service.commit_import = commit_import_with_batch_lock
extensions.patch_episode_gates = patch_episode_gates_with_row_lock
extensions.resolve_reconciliation_item = resolve_reconciliation_with_locks
