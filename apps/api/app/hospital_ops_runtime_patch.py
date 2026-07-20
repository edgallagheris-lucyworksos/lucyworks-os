from __future__ import annotations

from sqlmodel import Session, select

from app import hospital_ops_service as service
from app.hospital_ops_models import OperationalBlock


_original_detect_constraints = service.detect_constraints


def detect_constraints_with_normalised_datetimes(
    session: Session,
    premises_ref: str,
    operational_date,
    persist: bool = True,
):
    """Normalise database-returned timestamps before mixed-session evaluation.

    SQLite returns timezone-naive values even when request-created objects are
    timezone-aware. PostgreSQL retains timezone metadata. Normalising the
    identity-map rows at this boundary keeps comparisons deterministic across
    both engines without changing the canonical UTC data contract.
    """

    rows = session.exec(
        select(OperationalBlock).where(
            OperationalBlock.premises_ref == premises_ref,
            OperationalBlock.operational_date == operational_date,
        )
    ).all()
    for row in rows:
        row.starts_at = service.normalise_dt(row.starts_at)
        row.ends_at = service.normalise_dt(row.ends_at)
    return _original_detect_constraints(session, premises_ref, operational_date, persist=persist)


service.detect_constraints = detect_constraints_with_normalised_datetimes
