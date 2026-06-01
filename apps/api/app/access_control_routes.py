from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, User

router = APIRouter(prefix="/api/access", tags=["access-control"])

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "clinical_director": {"view_all", "manage_all", "clinical_decision", "audit_view", "admin_override", "shadow_review"},
    "ops_manager": {"view_all", "manage_flow", "manage_resources", "audit_view", "admin_override", "shadow_review"},
    "clinician": {"view_clinical", "clinical_decision", "review_results", "view_flow", "view_own_department"},
    "nurse": {"view_care", "manage_care_tasks", "view_flow", "view_own_department"},
    "pca": {"view_handoffs", "manage_patient_movement", "view_own_department"},
    "admin": {"view_comms", "manage_owner_comms", "view_reception", "view_own_department"},
}

ROLE_DEPARTMENTS: dict[str, set[str]] = {
    "clinical_director": {"*"},
    "ops_manager": {"*"},
    "clinician": {"Triage", "Consult", "Imaging", "Surgery", "ICU", "Wards", "Discharge", "Labs"},
    "nurse": {"Triage", "Surgery", "ICU", "Wards", "Discharge", "Pharmacy", "Labs"},
    "pca": {"Wards", "ICU", "Imaging", "Surgery", "Labs"},
    "admin": {"Reception", "Discharge", "Owner Comms", "Admin"},
}

SENSITIVE_ENTITY_TYPES = {"episode", "patient", "result_review", "shadow_mode", "audit", "pharmacy", "controlled_drug"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def permissions_for(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


def departments_for(role: str) -> set[str]:
    return ROLE_DEPARTMENTS.get(role, set())


def allowed(role: str, permission: str, department: Optional[str] = None) -> tuple[bool, str]:
    perms = permissions_for(role)
    if "manage_all" in perms or "view_all" in perms:
        return True, "role has global access"
    if permission not in perms:
        return False, f"role {role} lacks permission {permission}"
    if department:
        departments = departments_for(role)
        if "*" not in departments and department not in departments:
            return False, f"role {role} is not scoped to department {department}"
    return True, "permission and department scope allowed"


class AccessCheckPayload(BaseModel):
    role: str
    permission: str
    department: Optional[str] = None
    entity_type: Optional[str] = None


class AuditViewPayload(BaseModel):
    actor_name: str
    role: str
    entity_type: str
    entity_id: int = 0
    department: Optional[str] = None
    reason: str = "view"


class AdminOverridePayload(BaseModel):
    actor_name: str
    role: str
    target_action: str
    entity_type: str
    entity_id: int = 0
    department: Optional[str] = None
    reason: str


@router.get("/me")
def me(role: str = "nurse", department: Optional[str] = None):
    ok, reason = allowed(role, "view_own_department", department)
    return {
        "role": role,
        "department": department,
        "permissions": sorted(permissions_for(role)),
        "departments": sorted(departments_for(role)),
        "department_scope_ok": ok,
        "reason": reason,
    }


@router.get("/permissions")
def permissions():
    return {
        "roles": {role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()},
        "departments": {role: sorted(depts) for role, depts in ROLE_DEPARTMENTS.items()},
        "sensitive_entity_types": sorted(SENSITIVE_ENTITY_TYPES),
    }


@router.post("/check")
def check_access(payload: AccessCheckPayload):
    ok, reason = allowed(payload.role, payload.permission, payload.department)
    sensitive = bool(payload.entity_type and payload.entity_type in SENSITIVE_ENTITY_TYPES)
    return {"allowed": ok, "reason": reason, "sensitive": sensitive, "role": payload.role, "permission": payload.permission, "department": payload.department}


@router.post("/audit-view")
def audit_view(payload: AuditViewPayload, session: Session = Depends(get_session)):
    permission = "audit_view" if payload.entity_type == "audit" else "view_own_department"
    ok, reason = allowed(payload.role, permission, payload.department)
    if payload.entity_type in SENSITIVE_ENTITY_TYPES and not ok:
        raise HTTPException(status_code=403, detail=reason)
    event = write_audit(
        session,
        payload.actor_name,
        "sensitive_view_audited",
        payload.entity_type,
        payload.entity_id,
        f"{payload.role} viewed {payload.entity_type}; reason={payload.reason}; department={payload.department or 'none'}",
    )
    return {"ok": True, "allowed": ok, "reason": reason, "audit_event": event}


@router.post("/admin-override")
def admin_override(payload: AdminOverridePayload, session: Session = Depends(get_session)):
    ok, reason = allowed(payload.role, "admin_override", payload.department)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)
    event = write_audit(
        session,
        payload.actor_name,
        "admin_override_logged",
        payload.entity_type,
        payload.entity_id,
        f"Override {payload.target_action}; role={payload.role}; reason={payload.reason}; department={payload.department or 'none'}",
    )
    return {"ok": True, "audit_event": event}


@router.get("/audit-summary")
def audit_summary(session: Session = Depends(get_session)):
    events = session.exec(select(AuditEvent).order_by(AuditEvent.created_at)).all()
    by_action = Counter([event.action for event in events])
    by_entity = Counter([event.entity_type for event in events])
    sensitive_views = [event for event in events if event.action == "sensitive_view_audited"]
    overrides = [event for event in events if event.action == "admin_override_logged"]
    users = session.exec(select(User).where(User.active == True)).all()
    return {
        "generated_at": utc_now().isoformat(),
        "audit_event_count": len(events),
        "sensitive_view_count": len(sensitive_views),
        "admin_override_count": len(overrides),
        "active_user_count": len(users),
        "by_action": dict(by_action),
        "by_entity": dict(by_entity),
        "recent_events": [row(event) for event in events[-80:]],
    }
