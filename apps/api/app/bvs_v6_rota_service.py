from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.auth import AuthContext
from app.bvs_v6_models import CoverageRequirement, WorkforceCompetency, WorkforceProfile
from app.bvs_v6_rota_models import WorkforceAvailabilityExceptionV6, WorkforceShiftV6
from app.bvs_v6_service import PREMISES_REF, coverage_dict
from app.evidence_service import create_evidence_event

LONDON = ZoneInfo("Europe/London")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _actor(auth: AuthContext) -> tuple[str, str, str]:
    return auth.actor_id or auth.subject, auth.actor_name, auth.role


def _evidence(session: Session, auth: AuthContext, *, event_type: str, action: str, entity_id: str, before: Any, after: Any, reason: str, risk: str = "amber") -> None:
    actor_id, actor_name, actor_role = _actor(auth)
    create_evidence_event(
        session,
        event_type=event_type,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=after,
        reason=reason,
        justification="LucyWorks governed workforce rota and safe-coverage assessment",
        evidence_links=[{"type": "workforce_rota", "id": entity_id}],
        compliance_domain="workforce_safety",
        risk_level=risk,
        source_module="bvs_v6_rota",
        source_record_ref=entity_id,
        entity_type="workforce_rota",
        entity_id=entity_id,
    )


def shift_dict(row: WorkforceShiftV6) -> dict[str, Any]:
    return {
        "shiftRef": row.shift_ref,
        "premisesRef": row.premises_ref,
        "staffRef": row.staff_ref,
        "departmentRef": row.department_ref,
        "areaRef": row.area_ref,
        "startsAt": _aware(row.starts_at).isoformat(),
        "endsAt": _aware(row.ends_at).isoformat(),
        "shiftType": row.shift_type,
        "status": row.status,
        "onCall": row.on_call,
        "sourceStatus": row.source_status,
        "version": row.version,
        "updatedBy": row.updated_by_actor_name,
        "updatedAt": _aware(row.updated_at).isoformat(),
    }


def exception_dict(row: WorkforceAvailabilityExceptionV6) -> dict[str, Any]:
    return {
        "exceptionRef": row.exception_ref,
        "premisesRef": row.premises_ref,
        "staffRef": row.staff_ref,
        "startsAt": _aware(row.starts_at).isoformat(),
        "endsAt": _aware(row.ends_at).isoformat(),
        "exceptionType": row.exception_type,
        "status": row.status,
        "detail": row.detail,
        "sourceStatus": row.source_status,
        "version": row.version,
        "updatedBy": row.updated_by_actor_name,
        "updatedAt": _aware(row.updated_at).isoformat(),
    }


def roster(session: Session, starts_at: datetime | None = None, ends_at: datetime | None = None) -> dict[str, Any]:
    query = select(WorkforceShiftV6).where(WorkforceShiftV6.premises_ref == PREMISES_REF)
    if starts_at:
        query = query.where(WorkforceShiftV6.ends_at > _aware(starts_at))
    if ends_at:
        query = query.where(WorkforceShiftV6.starts_at < _aware(ends_at))
    shifts = session.exec(query.order_by(WorkforceShiftV6.starts_at, WorkforceShiftV6.staff_ref)).all()
    exceptions = session.exec(select(WorkforceAvailabilityExceptionV6).where(WorkforceAvailabilityExceptionV6.premises_ref == PREMISES_REF).order_by(WorkforceAvailabilityExceptionV6.starts_at)).all()
    return {"premisesRef": PREMISES_REF, "shifts": [shift_dict(row) for row in shifts], "availabilityExceptions": [exception_dict(row) for row in exceptions]}


def upsert_shift(session: Session, shift_ref: str, payload: dict[str, Any], auth: AuthContext) -> WorkforceShiftV6:
    starts_at = datetime.fromisoformat(str(payload["startsAt"]).replace("Z", "+00:00")) if payload.get("startsAt") else None
    ends_at = datetime.fromisoformat(str(payload["endsAt"]).replace("Z", "+00:00")) if payload.get("endsAt") else None
    row = session.exec(select(WorkforceShiftV6).where(WorkforceShiftV6.premises_ref == PREMISES_REF, WorkforceShiftV6.shift_ref == shift_ref)).first()
    actor_id, actor_name, _ = _actor(auth)
    if row:
        expected = int(payload.get("expectedVersion", 0))
        if row.version != expected:
            raise RuntimeError(f"stale shift version: expected {expected}, current {row.version}")
        before = shift_dict(row)
        starts_at = starts_at or _aware(row.starts_at)
        ends_at = ends_at or _aware(row.ends_at)
        staff_ref = str(payload.get("staffRef") or row.staff_ref)
    else:
        before = None
        if not starts_at or not ends_at:
            raise ValueError("new shifts require startsAt and endsAt")
        staff_ref = str(payload["staffRef"])
        row = WorkforceShiftV6(
            premises_ref=PREMISES_REF,
            shift_ref=shift_ref,
            staff_ref=staff_ref,
            department_ref=str(payload["departmentRef"]),
            starts_at=_aware(starts_at),
            ends_at=_aware(ends_at),
            updated_by_actor_id=actor_id,
            updated_by_actor_name=actor_name,
        )
        session.add(row)

    if _aware(ends_at) <= _aware(starts_at):
        raise ValueError("shift endsAt must be after startsAt")
    if (_aware(ends_at) - _aware(starts_at)) > timedelta(hours=24):
        raise ValueError("a single shift cannot exceed 24 hours")
    profile = session.exec(select(WorkforceProfile).where(WorkforceProfile.premises_ref == PREMISES_REF, WorkforceProfile.staff_ref == staff_ref, WorkforceProfile.employment_status == "active")).first()
    if not profile:
        raise ValueError("shift staffRef must match an active workforce profile")

    overlaps = session.exec(select(WorkforceShiftV6).where(
        WorkforceShiftV6.premises_ref == PREMISES_REF,
        WorkforceShiftV6.staff_ref == staff_ref,
        WorkforceShiftV6.status.in_(["planned", "active"]),
        WorkforceShiftV6.starts_at < _aware(ends_at),
        WorkforceShiftV6.ends_at > _aware(starts_at),
    )).all()
    overlaps = [item for item in overlaps if item.shift_ref != shift_ref]
    if overlaps and not payload.get("overrideReason"):
        raise RuntimeError(f"staff member has {len(overlaps)} overlapping shift(s); a governed overrideReason is required")

    row.staff_ref = staff_ref
    row.department_ref = str(payload.get("departmentRef") or row.department_ref)
    row.area_ref = payload.get("areaRef", row.area_ref)
    row.starts_at = _aware(starts_at)
    row.ends_at = _aware(ends_at)
    row.shift_type = str(payload.get("shiftType") or row.shift_type)
    row.status = str(payload.get("status") or row.status)
    row.on_call = bool(payload.get("onCall", row.on_call))
    row.source_status = str(payload.get("sourceStatus") or row.source_status)
    if row.id is not None:
        row.version += 1
    row.updated_by_actor_id = actor_id
    row.updated_by_actor_name = actor_name
    row.updated_at = utc_now()
    session.flush()
    _evidence(session, auth, event_type="workforce_shift_updated", action="workforce shift updated", entity_id=shift_ref, before=before, after=shift_dict(row), reason=str(payload.get("reason") or payload.get("overrideReason") or "Rota shift maintained"), risk="red" if overlaps else "amber")
    return row


def upsert_exception(session: Session, exception_ref: str, payload: dict[str, Any], auth: AuthContext) -> WorkforceAvailabilityExceptionV6:
    starts_at = datetime.fromisoformat(str(payload["startsAt"]).replace("Z", "+00:00")) if payload.get("startsAt") else None
    ends_at = datetime.fromisoformat(str(payload["endsAt"]).replace("Z", "+00:00")) if payload.get("endsAt") else None
    row = session.exec(select(WorkforceAvailabilityExceptionV6).where(WorkforceAvailabilityExceptionV6.premises_ref == PREMISES_REF, WorkforceAvailabilityExceptionV6.exception_ref == exception_ref)).first()
    actor_id, actor_name, _ = _actor(auth)
    if row:
        expected = int(payload.get("expectedVersion", 0))
        if row.version != expected:
            raise RuntimeError(f"stale availability exception version: expected {expected}, current {row.version}")
        before = exception_dict(row)
        starts_at = starts_at or _aware(row.starts_at)
        ends_at = ends_at or _aware(row.ends_at)
    else:
        before = None
        if not starts_at or not ends_at:
            raise ValueError("new availability exceptions require startsAt and endsAt")
        row = WorkforceAvailabilityExceptionV6(
            premises_ref=PREMISES_REF,
            exception_ref=exception_ref,
            staff_ref=str(payload["staffRef"]),
            starts_at=_aware(starts_at),
            ends_at=_aware(ends_at),
            updated_by_actor_id=actor_id,
            updated_by_actor_name=actor_name,
        )
        session.add(row)
    if _aware(ends_at) <= _aware(starts_at):
        raise ValueError("availability exception endsAt must be after startsAt")
    row.staff_ref = str(payload.get("staffRef") or row.staff_ref)
    row.starts_at = _aware(starts_at)
    row.ends_at = _aware(ends_at)
    row.exception_type = str(payload.get("exceptionType") or row.exception_type)
    row.status = str(payload.get("status") or row.status)
    row.detail = payload.get("detail", row.detail)
    row.source_status = str(payload.get("sourceStatus") or row.source_status)
    if row.id is not None:
        row.version += 1
    row.updated_by_actor_id = actor_id
    row.updated_by_actor_name = actor_name
    row.updated_at = utc_now()
    session.flush()
    _evidence(session, auth, event_type="workforce_availability_updated", action="workforce availability exception updated", entity_id=exception_ref, before=before, after=exception_dict(row), reason=str(payload.get("reason") or row.detail or "Availability maintained"))
    return row


def _requirement_active(row: CoverageRequirement, at: datetime) -> bool:
    local = _aware(at).astimezone(LONDON)
    if row.day_type == "weekday" and local.weekday() >= 5:
        return False
    if row.day_type == "weekend" and local.weekday() < 5:
        return False
    current = local.strftime("%H:%M")
    if row.starts_at_local <= row.ends_at_local:
        return row.starts_at_local <= current <= row.ends_at_local
    return current >= row.starts_at_local or current <= row.ends_at_local


def rota_assessment(session: Session, at: datetime, rest_threshold_hours: float = 11.0) -> dict[str, Any]:
    at = _aware(at)
    requirements = [item for item in session.exec(select(CoverageRequirement).where(CoverageRequirement.premises_ref == PREMISES_REF)).all() if _requirement_active(item, at)]
    profiles = {item.staff_ref: item for item in session.exec(select(WorkforceProfile).where(WorkforceProfile.premises_ref == PREMISES_REF, WorkforceProfile.employment_status == "active")).all()}
    competencies = session.exec(select(WorkforceCompetency).where(WorkforceCompetency.premises_ref == PREMISES_REF, WorkforceCompetency.status == "verified")).all()
    competency_index = {(item.staff_ref, item.competency_ref, item.scope_ref) for item in competencies if (not item.valid_from or item.valid_from <= at.date()) and (not item.valid_until or item.valid_until >= at.date())}
    shifts = session.exec(select(WorkforceShiftV6).where(WorkforceShiftV6.premises_ref == PREMISES_REF, WorkforceShiftV6.status.in_(["planned", "active"]), WorkforceShiftV6.starts_at <= at, WorkforceShiftV6.ends_at > at)).all()
    exceptions = session.exec(select(WorkforceAvailabilityExceptionV6).where(WorkforceAvailabilityExceptionV6.premises_ref == PREMISES_REF, WorkforceAvailabilityExceptionV6.status == "approved", WorkforceAvailabilityExceptionV6.starts_at <= at, WorkforceAvailabilityExceptionV6.ends_at > at)).all()
    absent = {item.staff_ref: item for item in exceptions}
    all_window_shifts = session.exec(select(WorkforceShiftV6).where(WorkforceShiftV6.premises_ref == PREMISES_REF, WorkforceShiftV6.status.in_(["planned", "active", "completed"]), WorkforceShiftV6.starts_at >= at - timedelta(days=7), WorkforceShiftV6.starts_at <= at + timedelta(days=1)).order_by(WorkforceShiftV6.staff_ref, WorkforceShiftV6.starts_at)).all()
    by_staff: dict[str, list[WorkforceShiftV6]] = {}
    for shift in all_window_shifts:
        by_staff.setdefault(shift.staff_ref, []).append(shift)

    staff_risks: dict[str, list[dict[str, Any]]] = {}
    for staff_ref, staff_shifts in by_staff.items():
        preceding = [item for item in staff_shifts if _aware(item.starts_at) >= at - timedelta(days=7) and _aware(item.starts_at) <= at]
        hours = sum((_aware(item.ends_at) - _aware(item.starts_at)).total_seconds() / 3600 for item in preceding)
        profile = profiles.get(staff_ref)
        maximum = profile.maximum_safe_hours_weekly if profile and profile.maximum_safe_hours_weekly is not None else None
        if maximum is not None and hours > maximum:
            staff_risks.setdefault(staff_ref, []).append({"type": "weekly_hours", "severity": "red", "scheduledHours": round(hours, 2), "maximumSafeHours": maximum})
        ordered = sorted(staff_shifts, key=lambda item: _aware(item.starts_at))
        for previous, current in zip(ordered, ordered[1:]):
            gap = (_aware(current.starts_at) - _aware(previous.ends_at)).total_seconds() / 3600
            if current.shift_ref in {shift.shift_ref for shift in shifts} and gap < rest_threshold_hours:
                staff_risks.setdefault(staff_ref, []).append({"type": "short_rest", "severity": "amber", "restHours": round(gap, 2), "configuredThresholdHours": rest_threshold_hours, "previousShiftRef": previous.shift_ref})

    results: list[dict[str, Any]] = []
    for requirement in requirements:
        eligible: list[str] = []
        excluded: list[dict[str, Any]] = []
        for shift in shifts:
            profile = profiles.get(shift.staff_ref)
            if not profile:
                excluded.append({"staffRef": shift.staff_ref, "reason": "missing active workforce profile"})
                continue
            if profile.primary_role_ref != requirement.role_ref:
                continue
            if shift.department_ref != requirement.service_ref and profile.department_ref != requirement.service_ref:
                continue
            if requirement.area_ref and shift.area_ref not in {requirement.area_ref, None}:
                continue
            if shift.staff_ref in absent:
                excluded.append({"staffRef": shift.staff_ref, "reason": f"availability exception: {absent[shift.staff_ref].exception_type}"})
                continue
            if requirement.competency_ref:
                scopes = {requirement.area_ref or "hospital", requirement.service_ref, "hospital"}
                if not any((shift.staff_ref, requirement.competency_ref, scope) in competency_index for scope in scopes):
                    excluded.append({"staffRef": shift.staff_ref, "reason": f"missing verified competency {requirement.competency_ref}"})
                    continue
            if any(item["severity"] == "red" for item in staff_risks.get(shift.staff_ref, [])):
                excluded.append({"staffRef": shift.staff_ref, "reason": "red fatigue/workload risk"})
                continue
            eligible.append(shift.staff_ref)
        gap = max(0, requirement.minimum_count - len(set(eligible)))
        results.append({
            "requirement": coverage_dict(requirement),
            "eligibleStaffRefs": sorted(set(eligible)),
            "eligibleCount": len(set(eligible)),
            "excluded": excluded,
            "gap": gap,
            "status": "met" if gap == 0 else "gap",
        })

    unprofiled_shifts = [shift.shift_ref for shift in shifts if shift.staff_ref not in profiles]
    return {
        "premisesRef": PREMISES_REF,
        "assessedAt": at.isoformat(),
        "localAssessedAt": at.astimezone(LONDON).isoformat(),
        "activeShiftCount": len(shifts),
        "approvedExceptionCount": len(exceptions),
        "requirements": results,
        "gapCount": sum(1 for item in results if item["status"] == "gap"),
        "staffRisks": staff_risks,
        "unprofiledShifts": unprofiled_shifts,
        "safeToOperate": all(item["status"] == "met" for item in results) and not unprofiled_shifts,
        "governanceNote": "The rest threshold and maximum-safe-hours values are local configuration inputs requiring hospital approval; LucyWorks does not infer clinical fitness from hours alone.",
    }
