from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import control_plane_routes as legacy
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import get_session

router = APIRouter(prefix="/api/control-plane", tags=["control-plane-deadlines-v13"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalise_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def deadline_state(row: CriticalResultAcknowledgement, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    due_at = normalise_utc(row.due_at)
    overdue = bool(row.status != "acknowledged" and due_at and due_at < current)
    minutes_overdue = max(0, int((current - due_at).total_seconds() // 60)) if overdue and due_at else 0
    return {
        **legacy.critical_result_dict(row),
        "overdue": overdue,
        "minutesOverdue": minutes_overdue,
        "deadlineState": "overdue" if overdue else "acknowledged" if row.status == "acknowledged" else "within_window",
    }


@router.get("/critical-results")
def list_critical_results_with_deadlines(
    status: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(CriticalResultAcknowledgement).order_by(CriticalResultAcknowledgement.created_at.desc())
    if status:
        query = query.where(CriticalResultAcknowledgement.status == status)
    rows = session.exec(query).all()
    now = utc_now()
    payload = [deadline_state(row, now=now) for row in rows]
    payload.sort(key=lambda item: (not item["overdue"], item.get("dueAt") or "9999", item.get("createdAt") or ""))
    return {
        "results": payload,
        "count": len(payload),
        "overdueCount": sum(1 for item in payload if item["overdue"]),
    }


@router.get("/dashboard")
def control_plane_dashboard_with_deadlines(session: Session = Depends(get_session)) -> dict[str, Any]:
    payload = legacy.control_plane_dashboard(session)
    rows = session.exec(select(CriticalResultAcknowledgement).order_by(CriticalResultAcknowledgement.created_at.desc())).all()
    now = utc_now()
    critical_results = [deadline_state(row, now=now) for row in rows]
    critical_results.sort(key=lambda item: (not item["overdue"], item.get("dueAt") or "9999", item.get("createdAt") or ""))
    payload["criticalResults"] = critical_results[:20]
    payload["summary"]["overdueCriticalResults"] = sum(1 for item in critical_results if item["overdue"])
    payload["summary"]["unacknowledgedCriticalResults"] = sum(1 for item in critical_results if item["status"] != "acknowledged")
    return payload
