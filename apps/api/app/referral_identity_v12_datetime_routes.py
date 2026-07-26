from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import get_session
from app.hospital_command_routes import row_dict
from app.referral_identity_v12_models import AccessReviewV12, ReferralTriageV12, utc_now

router = APIRouter(prefix="/api/v12", tags=["referral-identity-assurance-v12-datetime"])
ACCESS_REVIEW_ROLES = ("admin", "governance_lead", "hospital_director", "clinical_director")


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@router.get("/triage")
def triage_queue_utc(
    status: str | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(ReferralTriageV12).order_by(ReferralTriageV12.response_due_at)
    if status:
        query = query.where(ReferralTriageV12.status == status)
    if category:
        query = query.where(ReferralTriageV12.category == category)
    rows = session.exec(query.limit(limit)).all()
    now = utc_now()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = row_dict(row)
        item["responseOverdue"] = row.status == "pending" and as_utc(row.response_due_at) < now
        item["clinicalReviewOverdue"] = row.status not in {"completed", "closed"} and as_utc(row.clinical_review_due_at) < now
        items.append(item)
    return {"items": items, "count": len(items), "generatedAt": now.isoformat()}


@router.get("/access-reviews")
def list_access_reviews_utc(
    status: str | None = None,
    subject_ref: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*ACCESS_REVIEW_ROLES)),
) -> dict[str, Any]:
    query = select(AccessReviewV12).order_by(AccessReviewV12.due_at)
    if status:
        query = query.where(AccessReviewV12.status == status)
    if subject_ref:
        query = query.where(AccessReviewV12.subject_ref == subject_ref)
    rows = session.exec(query).all()
    now = utc_now()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = row_dict(row)
        item["overdue"] = row.status == "pending" and as_utc(row.due_at) < now
        items.append(item)
    return {"items": items, "count": len(items)}
