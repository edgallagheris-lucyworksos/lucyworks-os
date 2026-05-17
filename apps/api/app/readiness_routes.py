from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.catalogue_models import DiagnosticCatalogueItem, FormularyCatalogueItem, ProcedureCatalogueItem
from app.database import get_session
from app.flow_state_models import DischargeBlocker, OccupancyRecord, SeverityGate, StaffAssignmentRisk
from app.hr_models import CompetencyRecord, FatigueRiskRecord, LeaveRequest, OnCallAssignment, OvertimeRequest, StaffProfile
from app.inpatient_models import InpatientStay, MedicationDue, NightHandover, ObservationTask
from app.models import (
    AuditEvent,
    Episode,
    Handover,
    HospitalSection,
    MessageThread,
    OwnerCommsRequirement,
    PharmacyRequest,
    ResultReview,
    Room,
    ScheduleBlock,
    Shift,
    StaffMember,
    StockItem,
    WorkItem,
)

router = APIRouter()


def count(session: Session, model) -> int:
    return len(session.exec(select(model)).all())


def status_for(value: int, minimum: int) -> str:
    if value >= minimum:
        return "ready"
    if value > 0:
        return "partial"
    return "missing"


@router.get("/api/readiness/bvs")
def bvs_readiness(session: Session = Depends(get_session)):
    metrics = {
        "sections": count(session, HospitalSection),
        "rooms": count(session, Room),
        "staff": count(session, StaffMember),
        "shifts": count(session, Shift),
        "episodes": count(session, Episode),
        "schedule_blocks": count(session, ScheduleBlock),
        "work_items": count(session, WorkItem),
        "inpatient_stays": count(session, InpatientStay),
        "observation_tasks": count(session, ObservationTask),
        "medication_due": count(session, MedicationDue),
        "night_handovers": count(session, NightHandover),
        "handovers": count(session, Handover),
        "results": count(session, ResultReview),
        "discharge_blockers": count(session, DischargeBlocker),
        "occupancy_records": count(session, OccupancyRecord),
        "severity_gates": count(session, SeverityGate),
        "staff_assignment_risks": count(session, StaffAssignmentRisk),
        "message_threads": count(session, MessageThread),
        "owner_comms": count(session, OwnerCommsRequirement),
        "pharmacy_requests": count(session, PharmacyRequest),
        "stock_items": count(session, StockItem),
        "procedure_catalogue": count(session, ProcedureCatalogueItem),
        "formulary_catalogue": count(session, FormularyCatalogueItem),
        "diagnostic_catalogue": count(session, DiagnosticCatalogueItem),
        "staff_profiles": count(session, StaffProfile),
        "competencies": count(session, CompetencyRecord),
        "leave_requests": count(session, LeaveRequest),
        "overtime_requests": count(session, OvertimeRequest),
        "on_call_assignments": count(session, OnCallAssignment),
        "fatigue_risks": count(session, FatigueRiskRecord),
        "audit_events": count(session, AuditEvent),
    }

    layers = [
        {"layer": "Hospital structure", "status": status_for(min(metrics["sections"], metrics["rooms"]), 20), "evidence": {"sections": metrics["sections"], "rooms": metrics["rooms"]}, "missing_depth": "Needs live floorplan/resource dependency mapping for every room."},
        {"layer": "Staffing / HR", "status": status_for(min(metrics["staff"], metrics["staff_profiles"] + metrics["competencies"]), 5), "evidence": {"staff": metrics["staff"], "profiles": metrics["staff_profiles"], "competencies": metrics["competencies"], "fatigue_risks": metrics["fatigue_risks"]}, "missing_depth": "Needs full rota rule engine, leave collision checks and competency expiry alerts."},
        {"layer": "15-minute scheduling", "status": status_for(metrics["schedule_blocks"], 30), "evidence": {"schedule_blocks": metrics["schedule_blocks"]}, "missing_depth": "Needs utilisation forecasting and delay propagation across theatres, imaging, recovery and wards."},
        {"layer": "Overnight / inpatients", "status": status_for(min(metrics["inpatient_stays"], metrics["observation_tasks"], metrics["night_handovers"]), 5), "evidence": {"inpatients": metrics["inpatient_stays"], "obs": metrics["observation_tasks"], "night_handovers": metrics["night_handovers"]}, "missing_depth": "Needs bed forecasting, q30/q60 automatic task generation and morning-review automation."},
        {"layer": "Flow state / LIVE gates", "status": status_for(min(metrics["severity_gates"], metrics["discharge_blockers"] + metrics["occupancy_records"] + metrics["staff_assignment_risks"]), 3), "evidence": {"severity_gates": metrics["severity_gates"], "blockers": metrics["discharge_blockers"], "occupancy": metrics["occupancy_records"], "staff_risks": metrics["staff_assignment_risks"]}, "missing_depth": "Needs every clinical/action endpoint to call the gate engine before state changes."},
        {"layer": "Results / diagnostics", "status": status_for(min(metrics["diagnostic_catalogue"], metrics["results"]), 3), "evidence": {"diagnostic_catalogue": metrics["diagnostic_catalogue"], "results": metrics["results"]}, "missing_depth": "Needs real result lifecycle: received, reviewed, actioned, owner updated, linked to discharge/procedure decisions."},
        {"layer": "Pharmacy / stock", "status": status_for(min(metrics["formulary_catalogue"], metrics["stock_items"]), 5), "evidence": {"formulary": metrics["formulary_catalogue"], "stock_items": metrics["stock_items"], "pharmacy_requests": metrics["pharmacy_requests"]}, "missing_depth": "Needs authorised supplier ordering, stock decrement, cold-chain/locked-storage audit and discharge-med readiness."},
        {"layer": "Catalogues", "status": status_for(min(metrics["procedure_catalogue"], metrics["formulary_catalogue"], metrics["diagnostic_catalogue"]), 3), "evidence": {"procedures": metrics["procedure_catalogue"], "formulary": metrics["formulary_catalogue"], "diagnostics": metrics["diagnostic_catalogue"]}, "missing_depth": "Needs CSV upload UI and admin-controlled import/validation workflow."},
        {"layer": "Messaging / owner comms", "status": status_for(metrics["message_threads"] + metrics["owner_comms"], 5), "evidence": {"message_threads": metrics["message_threads"], "owner_comms": metrics["owner_comms"]}, "missing_depth": "Needs template actions, consent gate, owner update SLA and full thread-to-case audit."},
        {"layer": "Audit / governance", "status": status_for(metrics["audit_events"], 10), "evidence": {"audit_events": metrics["audit_events"]}, "missing_depth": "Needs hash-linked LucyTrace, access logging, GDPR retention controls and exportable governance pack."},
    ]

    missing = [x for x in layers if x["status"] == "missing"]
    partial = [x for x in layers if x["status"] == "partial"]
    ready = [x for x in layers if x["status"] == "ready"]

    return {
        "target": "BVS/CVS-style specialist veterinary hospital operating system",
        "overall_status": "partial" if missing or partial else "ready",
        "summary": {
            "ready_layers": len(ready),
            "partial_layers": len(partial),
            "missing_layers": len(missing),
            "total_layers": len(layers),
        },
        "layers": layers,
        "metrics": metrics,
        "next_required_build_slices": [
            "full action buttons wired to live-action routes",
            "CSV upload/import UI for procedures, formulary, diagnostics and assignments",
            "bed/theatre/imaging forecast engine",
            "results lifecycle and owner-update linkage",
            "pharmacy/stock decrement and ordering workflow",
            "RBAC/GDPR/compliance hardening",
            "hash-linked LucyTrace audit chain",
        ],
    }
