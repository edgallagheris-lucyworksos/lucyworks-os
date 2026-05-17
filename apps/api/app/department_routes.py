from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.department_models import (
    DepartmentConflictPattern,
    DepartmentDashboardNeed,
    DepartmentDefinition,
    DepartmentEntity,
    DepartmentRole,
    DepartmentWorkflowState,
)
from app.models import AuditEvent

router = APIRouter()

DEPARTMENTS = [
    {
        "code": "reception_intake",
        "name": "Reception / Intake",
        "lucy_module": "Lucy Flow",
        "purpose": "Creates and coordinates incoming operational flow.",
        "roles": ["Reception staff", "Referral coordinators", "Duty clinician for urgent escalation"],
        "entities": ["Incoming contact", "Referral", "Appointment", "Case intake", "Owner communication", "Consult room", "Queue position"],
        "states": ["Contact received", "Referral captured", "Case created", "Awaiting triage", "Booked", "Arrived", "Waiting", "Handed to clinical team"],
        "conflicts": ["Wrong urgency", "Duplicate case", "Wrong owner details", "Delayed intake", "Consult room unavailable", "Unclear handover"],
        "dashboard_needs": ["Arrivals", "Consult room usage", "Waiting times", "Urgent arrivals", "Owner updates due"],
    },
    {
        "code": "triage_consult",
        "name": "Triage / Consult",
        "lucy_module": "Lucy Flow",
        "purpose": "Converts intake into clinical ownership and next-step direction.",
        "roles": ["Specialist Vet", "Consulting Nurse", "Duty / triage clinician"],
        "entities": ["Triage queue item", "Consult room", "Specialist", "Nurse support", "Case urgency", "Next required action"],
        "states": ["Awaiting triage", "In consult", "Awaiting diagnostics", "Awaiting treatment decision", "Sent to next stage"],
        "conflicts": ["Triage backlog", "Room pressure", "Specialist unavailable", "No clear owner", "No next action"],
        "dashboard_needs": ["Queue by urgency", "Current consults", "Blocked consults", "Time in state"],
    },
    {
        "code": "imaging",
        "name": "Imaging",
        "lucy_module": "Lucy Diagnostics",
        "purpose": "Provides MRI, CT, X-ray, ultrasound and related throughput.",
        "roles": ["Diagnostic Imaging Specialist", "Imaging Nurse", "Anaesthetist if sedation / anaesthesia required"],
        "entities": ["MRI suite", "CT suite", "Imaging room", "Imaging queue", "Result", "Reviewer"],
        "states": ["Requested", "Booked", "Waiting", "In scan", "Reporting", "Result returned", "Reviewed", "Actioned"],
        "conflicts": ["Queue overflow", "Sedation delay", "Anaesthesia dependency", "Reviewer not assigned", "Unreviewed result", "Emergency scan jumps queue"],
        "dashboard_needs": ["Queue by urgency", "Slot utilisation", "Delayed scans", "Review SLA", "Downstream ownership"],
    },
    {
        "code": "surgery_theatre",
        "name": "Surgery / Theatre",
        "lucy_module": "Lucy Theatre",
        "purpose": "Delivers scheduled and emergency procedures using theatres, anaesthesia, prep, recovery and specialist teams.",
        "roles": ["Specialist Surgeon", "Anaesthetist", "Theatre Nurse", "Recovery Nurse", "ICU clinician downstream"],
        "entities": ["Theatre", "Procedure room", "Prep area", "CaseProcedure", "ScheduleBlock", "CleaningBlock", "Equipment / implants"],
        "states": ["Waiting for theatre", "In prep", "Anaesthesia start", "Procedure in progress", "Recovery", "Cleaning", "Ready again"],
        "conflicts": ["Anaesthetist double-booked", "Theatre not cleaned in time", "Procedure overruns", "Kit missing", "ICU bed not available", "Emergency add-on disrupts list"],
        "dashboard_needs": ["Live theatre board", "Start / expected end / actual end", "Overrun risk", "Cleaning state", "ICU destination pressure"],
    },
    {
        "code": "icu",
        "name": "ICU",
        "lucy_module": "Lucy Ward",
        "purpose": "Handles highest-acuity inpatients requiring close monitoring, stabilisation and rapid escalation.",
        "roles": ["ICU / ECC clinician", "ICU nurse", "Anaesthetist downstream / upstream", "Referring specialist"],
        "entities": ["ICU bed group", "PatientStay", "Monitoring task", "Drug task", "Transfer task"],
        "states": ["Admitted", "Stable", "Unstable", "Escalated", "Transfer pending", "Discharged to ward", "Discharged from hospital"],
        "conflicts": ["Bed full", "Monitoring overdue", "Transfer blocked", "Unsafe ratio", "Emergency admission with no capacity", "Recovery arrival with no ready bed"],
        "dashboard_needs": ["Census", "Bed occupancy", "Next observations due", "Critical alerts", "Transfer flow", "Staffing visibility"],
    },
]


def audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
    session.commit()


def clear_department(session: Session, code: str):
    for model in [DepartmentRole, DepartmentEntity, DepartmentWorkflowState, DepartmentConflictPattern, DepartmentDashboardNeed]:
        for row in session.exec(select(model).where(model.department_code == code)).all():
            session.delete(row)


@router.post("/api/departments/seed")
def seed_departments(actor_name: str = "System", session: Session = Depends(get_session)):
    seeded = 0
    for dept in DEPARTMENTS:
        existing = session.exec(select(DepartmentDefinition).where(DepartmentDefinition.code == dept["code"])).first()
        if not existing:
            existing = DepartmentDefinition(code=dept["code"], name=dept["name"], lucy_module=dept["lucy_module"], purpose=dept["purpose"])
        existing.name = dept["name"]
        existing.lucy_module = dept["lucy_module"]
        existing.purpose = dept["purpose"]
        session.add(existing)
        session.commit()
        session.refresh(existing)
        clear_department(session, dept["code"])
        for role in dept["roles"]:
            session.add(DepartmentRole(department_code=dept["code"], role_name=role))
        for entity in dept["entities"]:
            session.add(DepartmentEntity(department_code=dept["code"], entity_name=entity))
        for idx, state in enumerate(dept["states"]):
            session.add(DepartmentWorkflowState(department_code=dept["code"], state_name=state, state_order=idx))
        for conflict in dept["conflicts"]:
            severity = "red" if any(word in conflict.lower() for word in ["unsafe", "emergency", "bed full", "not available", "unreviewed"]) else "amber"
            session.add(DepartmentConflictPattern(department_code=dept["code"], conflict_name=conflict, severity_default=severity))
        for need in dept["dashboard_needs"]:
            session.add(DepartmentDashboardNeed(department_code=dept["code"], need_name=need))
        seeded += 1
    session.commit()
    audit(session, actor_name, "seeded", "departments", seeded, "Seeded LucyVet department operations pack")
    return {"ok": True, "seeded_departments": seeded}


@router.get("/api/departments")
def get_departments(session: Session = Depends(get_session)):
    departments = session.exec(select(DepartmentDefinition).where(DepartmentDefinition.active == True).order_by(DepartmentDefinition.name)).all()
    payload = []
    for dept in departments:
        payload.append({
            "department": dept,
            "roles": session.exec(select(DepartmentRole).where(DepartmentRole.department_code == dept.code).order_by(DepartmentRole.role_name)).all(),
            "entities": session.exec(select(DepartmentEntity).where(DepartmentEntity.department_code == dept.code).order_by(DepartmentEntity.entity_name)).all(),
            "states": session.exec(select(DepartmentWorkflowState).where(DepartmentWorkflowState.department_code == dept.code).order_by(DepartmentWorkflowState.state_order)).all(),
            "conflicts": session.exec(select(DepartmentConflictPattern).where(DepartmentConflictPattern.department_code == dept.code).order_by(DepartmentConflictPattern.conflict_name)).all(),
            "dashboard_needs": session.exec(select(DepartmentDashboardNeed).where(DepartmentDashboardNeed.department_code == dept.code).order_by(DepartmentDashboardNeed.need_name)).all(),
        })
    return {"summary": {"departments": len(payload)}, "departments": payload}
