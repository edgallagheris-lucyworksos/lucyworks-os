from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated
from app.clinical_execution_models import (
    AnaesthesiaRecord,
    ClinicalObservation,
    ControlledDrugLedgerEntry,
    DiagnosticWorkItem,
    DischargePlan,
    InventoryItem,
    InventoryMovement,
    MedicationAdministration,
    MedicationOrder,
    TreatmentTask,
)
from app.database import get_session

router = APIRouter(prefix="/api/clinical-execution/governed", tags=["clinical-execution-governance"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def rows_for(session: Session, model: Any, field: Any, episode_ref: str | None) -> list[Any]:
    query = select(model)
    if episode_ref:
        query = query.where(field == episode_ref)
    return list(session.exec(query).all())


@router.get("/dashboard")
def governed_dashboard(
    episode_ref: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    orders = rows_for(session, MedicationOrder, MedicationOrder.episode_ref, episode_ref)
    administrations = rows_for(session, MedicationAdministration, MedicationAdministration.episode_ref, episode_ref)
    anaesthesia = rows_for(session, AnaesthesiaRecord, AnaesthesiaRecord.episode_ref, episode_ref)
    observations = rows_for(session, ClinicalObservation, ClinicalObservation.episode_ref, episode_ref)
    tasks = rows_for(session, TreatmentTask, TreatmentTask.episode_ref, episode_ref)
    diagnostics = rows_for(session, DiagnosticWorkItem, DiagnosticWorkItem.episode_ref, episode_ref)
    discharges = rows_for(session, DischargePlan, DischargePlan.episode_ref, episode_ref)
    controlled = session.exec(select(ControlledDrugLedgerEntry).order_by(ControlledDrugLedgerEntry.created_at.desc()).limit(250)).all()
    inventory = session.exec(select(InventoryItem).order_by(InventoryItem.name)).all()
    movements = session.exec(select(InventoryMovement).order_by(InventoryMovement.created_at.desc()).limit(250)).all()
    return {
        "summary": {
            "activeMedicationOrders": len([row for row in orders if row.status == "active"]),
            "overdueAdministrations": len([row for row in administrations if row.status == "due" and row.scheduled_at < utc_now()]),
            "redObservations": len([row for row in observations if row.concern_level == "red" and row.escalation_status != "resolved"]),
            "overdueTasks": len([row for row in tasks if row.status != "completed" and row.due_at < utc_now()]),
            "criticalDiagnostics": len([row for row in diagnostics if row.critical_result and row.status == "reported"]),
            "lowStockItems": len([row for row in inventory if row.quantity_on_hand <= row.reorder_level]),
            "openControlledDrugDiscrepancies": len([row for row in controlled if row.discrepancy and row.discrepancy_status != "resolved"]),
            "unapprovedDischarges": len([row for row in discharges if row.status != "approved"]),
        },
        "medicationOrders": [{
            "orderRef": row.order_ref, "episodeRef": row.episode_ref, "medicationName": row.medication_name,
            "dose": row.dose, "route": row.route, "frequency": row.frequency, "status": row.status,
            "highRisk": row.high_risk, "controlledDrug": row.controlled_drug, "version": row.version,
        } for row in orders],
        "administrations": [{
            "administrationRef": row.administration_ref, "orderRef": row.order_ref, "episodeRef": row.episode_ref,
            "scheduledAt": row.scheduled_at.isoformat(), "status": row.status, "doseGiven": row.dose_given,
            "administeredByName": row.administered_by_name, "version": row.version,
        } for row in administrations],
        "anaesthesia": [{
            "recordRef": row.record_ref, "episodeRef": row.episode_ref, "blockRef": row.block_ref,
            "responsibleClinicianName": row.responsible_clinician_name, "asaStatus": row.asa_status,
            "status": row.status, "checklist": row.checklist, "complications": row.complications, "version": row.version,
        } for row in anaesthesia],
        "observations": [{
            "observationRef": row.observation_ref, "episodeRef": row.episode_ref, "type": row.observation_type,
            "values": row.values, "concernLevel": row.concern_level, "escalationStatus": row.escalation_status,
            "escalatedToRole": row.escalated_to_role, "escalationNote": row.escalation_note,
            "recordedAt": row.recorded_at.isoformat(), "version": row.version,
        } for row in observations],
        "tasks": [{
            "taskRef": row.task_ref, "episodeRef": row.episode_ref, "title": row.title, "status": row.status,
            "dueAt": row.due_at.isoformat(), "priority": row.priority, "version": row.version,
        } for row in tasks],
        "diagnostics": [{
            "workRef": row.work_ref, "episodeRef": row.episode_ref, "modality": row.modality,
            "requestedTest": row.requested_test, "urgency": row.urgency, "status": row.status,
            "reportSummary": row.report_summary, "criticalResult": row.critical_result, "version": row.version,
        } for row in diagnostics],
        "inventory": [{
            "itemRef": row.item_ref, "name": row.name, "quantityOnHand": row.quantity_on_hand,
            "unit": row.unit, "reorderLevel": row.reorder_level, "lowStock": row.quantity_on_hand <= row.reorder_level,
            "version": row.version,
        } for row in inventory],
        "inventoryMovements": [{
            "movementRef": row.movement_ref, "itemRef": row.item_ref, "movementType": row.movement_type,
            "quantityChange": row.quantity_change, "previousQuantity": row.previous_quantity,
            "newQuantity": row.new_quantity, "reason": row.reason, "actorName": row.actor_name,
            "createdAt": row.created_at.isoformat(),
        } for row in movements],
        "controlledDrugEntries": [{
            "entryRef": row.entry_ref, "medicationRef": row.medication_ref, "movementType": row.movement_type,
            "quantity": row.quantity, "unit": row.unit, "runningBalance": row.running_balance,
            "discrepancy": row.discrepancy, "discrepancyStatus": row.discrepancy_status,
            "discrepancyResolution": row.discrepancy_resolution, "version": row.version,
        } for row in controlled],
        "dischargePlans": [{
            "planRef": row.plan_ref, "episodeRef": row.episode_ref, "status": row.status,
            "careInstructions": row.care_instructions, "followUp": row.follow_up, "warningSigns": row.warning_signs,
            "referringVetReportStatus": row.referring_vet_report_status,
            "referringVetReportEvidenceRef": row.referring_vet_report_evidence_ref,
            "ownerCommunicationStatus": row.owner_communication_status,
            "ownerCommunicationEvidenceRef": row.owner_communication_evidence_ref,
            "approvedBy": row.approved_by_name, "version": row.version,
        } for row in discharges],
    }
