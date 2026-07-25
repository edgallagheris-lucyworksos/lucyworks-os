from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, PRESCRIBER_ROLES, SENIOR_ROLES, require_authenticated
from app.clinical_execution_models import (
    AnaesthesiaRecord,
    ClinicalObservation,
    ControlledDrugLedgerEntry,
    DiagnosticWorkItem,
    DischargePlan,
    InventoryItem,
    MedicationAdministration,
    MedicationOrder,
    SampleChainEvent,
    TreatmentTask,
)
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.v7_event_service import publish_event

router = APIRouter(prefix="/api/clinical-execution", tags=["clinical-execution"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def require_episode(session: Session, episode_ref: str) -> CanonicalEpisodeState:
    row = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    return row


def require_version(current: int, expected: int, entity: str) -> None:
    if current != expected:
        raise HTTPException(status_code=409, detail={"message": f"stale {entity}", "currentVersion": current})


def evidence_and_event(
    session: Session,
    *,
    episode_ref: str,
    entity_type: str,
    entity_ref: str,
    action: str,
    previous: Any,
    current: Any,
    reason: str,
    risk: str = "amber",
    compliance: str = "clinical_operations",
    event_type: str | None = None,
) -> str:
    evidence, _ = create_evidence_event(
        session,
        event_type=event_type or f"{entity_type}_{action}",
        action=action,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        compliance_domain=compliance,
        risk_level=risk,
        source_module="clinical-execution-v8",
        source_record_ref=entity_ref,
        correlation_id=episode_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"clinical:{entity_type}:{entity_ref}:{action}:{current.get('version', current.get('status', 'event')) if isinstance(current, dict) else 'event'}",
    )
    publish_event(
        session,
        event_type=event_type or f"{entity_type}_{action}",
        aggregate_type=entity_type,
        aggregate_ref=entity_ref,
        payload=current if isinstance(current, dict) else {"value": current},
        severity="error" if risk == "red" else "warning" if risk == "amber" else "info",
        correlation_id=episode_ref,
        idempotency_key=f"clinical-event:{evidence.event_ref}",
    )
    return evidence.event_ref


def med_order_dict(row: MedicationOrder) -> dict[str, Any]:
    return {
        "orderRef": row.order_ref, "episodeRef": row.episode_ref, "patientRef": row.patient_ref,
        "medicationRef": row.medication_ref, "medicationName": row.medication_name, "dose": row.dose,
        "route": row.route, "frequency": row.frequency, "indication": row.indication,
        "startsAt": row.starts_at.isoformat(), "endsAt": row.ends_at.isoformat() if row.ends_at else None,
        "prescriberSubject": row.prescriber_subject, "prescriberName": row.prescriber_name,
        "status": row.status, "highRisk": row.high_risk, "controlledDrug": row.controlled_drug,
        "version": row.version,
    }


def administration_dict(row: MedicationAdministration) -> dict[str, Any]:
    return {
        "administrationRef": row.administration_ref, "orderRef": row.order_ref, "episodeRef": row.episode_ref,
        "scheduledAt": row.scheduled_at.isoformat(), "administeredAt": row.administered_at.isoformat() if row.administered_at else None,
        "status": row.status, "doseGiven": row.dose_given, "routeUsed": row.route_used,
        "administeredBySubject": row.administered_by_subject, "administeredByName": row.administered_by_name,
        "witnessedBySubject": row.witnessed_by_subject, "omissionReason": row.omission_reason,
        "adverseReaction": row.adverse_reaction, "version": row.version, "evidenceEventRef": row.evidence_event_ref,
    }


class MedicationOrderCreate(BaseModel):
    episode_ref: str
    medication_ref: str
    medication_name: str
    dose: str
    route: str
    frequency: str
    indication: str
    starts_at: datetime
    ends_at: datetime | None = None
    high_risk: bool = False
    controlled_drug: bool = False
    scheduled_times: list[datetime] = PydanticField(default_factory=list)


class AdministrationAction(BaseModel):
    expected_version: int
    status: str
    dose_given: str | None = None
    route_used: str | None = None
    witness_subject: str | None = None
    omission_reason: str | None = None
    adverse_reaction: str | None = None
    reason: str


@router.post("/medication-orders")
def create_medication_order(payload: MedicationOrderCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    if auth.role not in PRESCRIBER_ROLES:
        raise HTTPException(status_code=403, detail="verified prescriber role required")
    episode = require_episode(session, payload.episode_ref)
    order = MedicationOrder(
        order_ref=new_ref("medorder"), episode_ref=episode.episode_ref, patient_ref=episode.patient_ref,
        medication_ref=payload.medication_ref, medication_name=payload.medication_name, dose=payload.dose,
        route=payload.route, frequency=payload.frequency, indication=payload.indication,
        starts_at=payload.starts_at, ends_at=payload.ends_at, prescriber_subject=auth.subject,
        prescriber_name=auth.actor_name, high_risk=payload.high_risk, controlled_drug=payload.controlled_drug,
    )
    session.add(order)
    session.flush()
    times = payload.scheduled_times or [payload.starts_at]
    administrations: list[MedicationAdministration] = []
    for due_at in times:
        administration = MedicationAdministration(
            administration_ref=new_ref("medadmin"), order_ref=order.order_ref,
            episode_ref=order.episode_ref, scheduled_at=due_at,
        )
        session.add(administration)
        administrations.append(administration)
    evidence_ref = evidence_and_event(
        session, episode_ref=order.episode_ref, entity_type="medication_order", entity_ref=order.order_ref,
        action="prescribed", previous=None, current=med_order_dict(order), reason=payload.indication,
        risk="red" if payload.high_risk or payload.controlled_drug else "amber", compliance="medication",
    )
    session.commit()
    return {"order": med_order_dict(order), "administrations": [administration_dict(row) for row in administrations], "evidenceEventRef": evidence_ref}


@router.get("/medication-orders")
def list_medication_orders(episode_ref: str | None = None, session: Session = Depends(get_session), _: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    query = select(MedicationOrder).order_by(MedicationOrder.created_at.desc())
    if episode_ref:
        query = query.where(MedicationOrder.episode_ref == episode_ref)
    rows = session.exec(query.limit(500)).all()
    administrations = session.exec(select(MedicationAdministration).order_by(MedicationAdministration.scheduled_at)).all()
    if episode_ref:
        administrations = [row for row in administrations if row.episode_ref == episode_ref]
    return {"orders": [med_order_dict(row) for row in rows], "administrations": [administration_dict(row) for row in administrations]}


@router.patch("/administrations/{administration_ref}")
def act_on_administration(administration_ref: str, payload: AdministrationAction, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    if auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical role required")
    row = session.exec(select(MedicationAdministration).where(MedicationAdministration.administration_ref == administration_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="medication administration not found")
    require_version(row.version, payload.expected_version, "medication administration")
    order = session.exec(select(MedicationOrder).where(MedicationOrder.order_ref == row.order_ref)).first()
    if not order or order.status != "active":
        raise HTTPException(status_code=409, detail="medication order is not active")
    status = payload.status.lower().strip()
    if status not in {"administered", "omitted", "withheld", "refused"}:
        raise HTTPException(status_code=400, detail="unsupported administration status")
    if status == "administered" and not payload.dose_given:
        raise HTTPException(status_code=400, detail="dose_given is required")
    if (order.high_risk or order.controlled_drug) and status == "administered" and not payload.witness_subject:
        raise HTTPException(status_code=409, detail="high-risk or controlled-drug administration requires a witness")
    if status != "administered" and not payload.omission_reason:
        raise HTTPException(status_code=400, detail="omission_reason is required")
    previous = administration_dict(row)
    row.status = status
    row.administered_at = utc_now() if status == "administered" else None
    row.dose_given = payload.dose_given
    row.route_used = payload.route_used or order.route
    row.administered_by_subject = auth.subject
    row.administered_by_name = auth.actor_name
    row.witnessed_by_subject = payload.witness_subject
    row.omission_reason = payload.omission_reason
    row.adverse_reaction = payload.adverse_reaction
    row.version += 1
    current = administration_dict(row)
    row.evidence_event_ref = evidence_and_event(
        session, episode_ref=row.episode_ref, entity_type="medication_administration", entity_ref=row.administration_ref,
        action=status, previous=previous, current=current, reason=payload.reason,
        risk="red" if order.high_risk or order.controlled_drug or payload.adverse_reaction else "amber", compliance="medication",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"administration": administration_dict(row)}


class AnaesthesiaCreate(BaseModel):
    episode_ref: str
    block_ref: str | None = None
    responsible_clinician_subject: str
    responsible_clinician_name: str
    anaesthetist_subject: str | None = None
    asa_status: str | None = None
    airway_plan: str | None = None
    analgesia_plan: str | None = None
    checklist: dict[str, Any] = PydanticField(default_factory=dict)


class AnaesthesiaUpdate(BaseModel):
    expected_version: int
    status: str
    checklist: dict[str, Any] | None = None
    complication: dict[str, Any] | None = None
    reason: str


def anaesthesia_dict(row: AnaesthesiaRecord) -> dict[str, Any]:
    return {
        "recordRef": row.record_ref, "episodeRef": row.episode_ref, "blockRef": row.block_ref,
        "responsibleClinicianSubject": row.responsible_clinician_subject, "responsibleClinicianName": row.responsible_clinician_name,
        "anaesthetistSubject": row.anaesthetist_subject, "asaStatus": row.asa_status,
        "airwayPlan": row.airway_plan, "analgesiaPlan": row.analgesia_plan,
        "inductionAt": row.induction_at.isoformat() if row.induction_at else None,
        "recoveryAt": row.recovery_at.isoformat() if row.recovery_at else None,
        "status": row.status, "checklist": row.checklist, "complications": row.complications,
        "version": row.version, "evidenceEventRef": row.evidence_event_ref,
    }


@router.post("/anaesthesia")
def create_anaesthesia(payload: AnaesthesiaCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    if auth.role not in PRESCRIBER_ROLES:
        raise HTTPException(status_code=403, detail="clinician authority required")
    require_episode(session, payload.episode_ref)
    if payload.block_ref and not session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == payload.block_ref)).first():
        raise HTTPException(status_code=404, detail="operational block not found")
    row = AnaesthesiaRecord(record_ref=new_ref("anaesthesia"), **payload.model_dump())
    session.add(row)
    session.flush()
    row.evidence_event_ref = evidence_and_event(
        session, episode_ref=row.episode_ref, entity_type="anaesthesia_record", entity_ref=row.record_ref,
        action="planned", previous=None, current=anaesthesia_dict(row), reason="anaesthesia plan recorded", risk="amber", compliance="clinical_governance",
    )
    session.commit()
    return {"record": anaesthesia_dict(row)}


@router.patch("/anaesthesia/{record_ref}")
def update_anaesthesia(record_ref: str, payload: AnaesthesiaUpdate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = session.exec(select(AnaesthesiaRecord).where(AnaesthesiaRecord.record_ref == record_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="anaesthesia record not found")
    require_version(row.version, payload.expected_version, "anaesthesia record")
    if auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical role required")
    status = payload.status.lower().strip()
    if status == "induced":
        required = {"identity_checked", "consent_checked", "equipment_checked", "airway_plan_confirmed"}
        checklist = payload.checklist or row.checklist
        missing = sorted(key for key in required if not checklist.get(key))
        if missing:
            raise HTTPException(status_code=409, detail={"message": "anaesthesia checklist incomplete", "missing": missing})
        row.induction_at = utc_now()
    if status == "recovered":
        row.recovery_at = utc_now()
    previous = anaesthesia_dict(row)
    if payload.checklist is not None:
        row.checklist = payload.checklist
    if payload.complication:
        row.complications = [*row.complications, {**payload.complication, "recordedAt": utc_now().isoformat(), "recordedBy": auth.actor_name}]
    row.status = status
    row.version += 1
    row.updated_at = utc_now()
    current = anaesthesia_dict(row)
    row.evidence_event_ref = evidence_and_event(
        session, episode_ref=row.episode_ref, entity_type="anaesthesia_record", entity_ref=row.record_ref,
        action=status, previous=previous, current=current, reason=payload.reason,
        risk="red" if payload.complication else "amber", compliance="clinical_governance",
    )
    session.add(row)
    session.commit()
    return {"record": anaesthesia_dict(row)}


class ObservationCreate(BaseModel):
    episode_ref: str
    area_ref: str | None = None
    observation_type: str
    values: dict[str, Any]
    concern_level: str = "green"
    reason: str = "clinical observation recorded"


@router.post("/observations")
def create_observation(payload: ObservationCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_episode(session, payload.episode_ref)
    concern = payload.concern_level.lower().strip()
    row = ClinicalObservation(
        observation_ref=new_ref("observation"), episode_ref=payload.episode_ref, area_ref=payload.area_ref,
        observation_type=payload.observation_type, values=payload.values, concern_level=concern,
        escalation_required=concern in {"amber", "red"}, escalation_status="pending" if concern in {"amber", "red"} else "not_required",
        recorded_by_subject=auth.subject, recorded_by_name=auth.actor_name,
    )
    session.add(row)
    session.flush()
    current = {"observationRef": row.observation_ref, "episodeRef": row.episode_ref, "type": row.observation_type, "values": row.values, "concernLevel": row.concern_level, "escalationStatus": row.escalation_status}
    row.evidence_event_ref = evidence_and_event(
        session, episode_ref=row.episode_ref, entity_type="clinical_observation", entity_ref=row.observation_ref,
        action="recorded", previous=None, current=current, reason=payload.reason,
        risk="red" if concern == "red" else "amber" if concern == "amber" else "green", compliance="clinical_operations",
    )
    session.commit()
    return {"observation": current, "evidenceEventRef": row.evidence_event_ref}


class TaskCreate(BaseModel):
    episode_ref: str
    task_type: str
    title: str
    instructions: str
    due_at: datetime
    assigned_role: str
    assigned_subject: str | None = None
    priority: str = "amber"
    requires_witness: bool = False


class TaskComplete(BaseModel):
    expected_version: int
    witness_subject: str | None = None
    reason: str


@router.post("/treatment-tasks")
def create_task(payload: TaskCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_episode(session, payload.episode_ref)
    row = TreatmentTask(task_ref=new_ref("treatment"), **payload.model_dump())
    session.add(row)
    session.flush()
    current = {"taskRef": row.task_ref, "episodeRef": row.episode_ref, "title": row.title, "dueAt": row.due_at.isoformat(), "assignedRole": row.assigned_role, "status": row.status, "priority": row.priority, "version": row.version}
    row.evidence_event_ref = evidence_and_event(session, episode_ref=row.episode_ref, entity_type="treatment_task", entity_ref=row.task_ref, action="created", previous=None, current=current, reason="treatment task created", risk=row.priority)
    session.commit()
    return {"task": current}


@router.patch("/treatment-tasks/{task_ref}/complete")
def complete_task(task_ref: str, payload: TaskComplete, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = session.exec(select(TreatmentTask).where(TreatmentTask.task_ref == task_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="treatment task not found")
    require_version(row.version, payload.expected_version, "treatment task")
    if row.requires_witness and not payload.witness_subject:
        raise HTTPException(status_code=409, detail="task completion requires a witness")
    previous = {"status": row.status, "version": row.version}
    row.status = "completed"
    row.completed_by_subject = auth.subject
    row.completed_at = utc_now()
    row.version += 1
    current = {"taskRef": row.task_ref, "status": row.status, "completedBy": auth.actor_name, "completedAt": row.completed_at.isoformat(), "version": row.version}
    row.evidence_event_ref = evidence_and_event(session, episode_ref=row.episode_ref, entity_type="treatment_task", entity_ref=row.task_ref, action="completed", previous=previous, current=current, reason=payload.reason, risk=row.priority)
    session.add(row)
    session.commit()
    return {"task": current}


class ControlledDrugMovement(BaseModel):
    medication_ref: str
    batch_ref: str | None = None
    episode_ref: str | None = None
    movement_type: str
    quantity: float
    unit: str
    expected_previous_balance: float
    reason: str
    witness_subject: str | None = None


@router.post("/controlled-drugs")
def controlled_drug_movement(payload: ControlledDrugMovement, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    if auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical role required")
    if not payload.witness_subject:
        raise HTTPException(status_code=409, detail="controlled-drug movement requires a witness")
    previous = session.exec(select(ControlledDrugLedgerEntry).where(ControlledDrugLedgerEntry.medication_ref == payload.medication_ref).order_by(ControlledDrugLedgerEntry.created_at.desc())).first()
    previous_balance = previous.running_balance if previous else 0.0
    discrepancy = abs(previous_balance - payload.expected_previous_balance) > 0.0001
    sign = 1 if payload.movement_type in {"received", "returned"} else -1
    balance = previous_balance + sign * payload.quantity
    if balance < -0.0001:
        discrepancy = True
    row = ControlledDrugLedgerEntry(
        entry_ref=new_ref("cd"), medication_ref=payload.medication_ref, batch_ref=payload.batch_ref,
        episode_ref=payload.episode_ref, movement_type=payload.movement_type, quantity=payload.quantity,
        unit=payload.unit, running_balance=balance, reason=payload.reason, actor_subject=auth.subject,
        actor_name=auth.actor_name, witness_subject=payload.witness_subject, discrepancy=discrepancy,
        discrepancy_status="open" if discrepancy else "none",
    )
    session.add(row)
    session.flush()
    current = {"entryRef": row.entry_ref, "medicationRef": row.medication_ref, "movementType": row.movement_type, "quantity": row.quantity, "runningBalance": row.running_balance, "discrepancy": row.discrepancy, "discrepancyStatus": row.discrepancy_status}
    row.evidence_event_ref = evidence_and_event(
        session, episode_ref=row.episode_ref or "controlled-drug-ledger", entity_type="controlled_drug_entry", entity_ref=row.entry_ref,
        action=payload.movement_type, previous={"runningBalance": previous_balance}, current=current,
        reason=payload.reason, risk="red" if discrepancy else "amber", compliance="medication",
    )
    session.commit()
    return {"entry": current, "evidenceEventRef": row.evidence_event_ref}


class InventoryUpsert(BaseModel):
    item_ref: str
    name: str
    item_type: str
    batch_ref: str | None = None
    expires_at: datetime | None = None
    quantity_on_hand: float
    unit: str
    reorder_level: float = 0
    location_ref: str | None = None
    controlled_drug: bool = False
    expected_version: int | None = None
    reason: str


@router.post("/inventory")
def upsert_inventory(payload: InventoryUpsert, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = session.exec(select(InventoryItem).where(InventoryItem.item_ref == payload.item_ref)).first()
    previous = None
    if row:
        if payload.expected_version is None:
            raise HTTPException(status_code=428, detail="expected_version is required for an existing inventory item")
        require_version(row.version, payload.expected_version, "inventory item")
        previous = {"quantityOnHand": row.quantity_on_hand, "version": row.version}
        for key, value in payload.model_dump(exclude={"expected_version", "reason"}).items():
            setattr(row, key, value)
        row.version += 1
        row.updated_at = utc_now()
    else:
        row = InventoryItem(**payload.model_dump(exclude={"expected_version", "reason"}))
    session.add(row)
    session.flush()
    current = {"itemRef": row.item_ref, "name": row.name, "quantityOnHand": row.quantity_on_hand, "unit": row.unit, "reorderLevel": row.reorder_level, "expiresAt": row.expires_at.isoformat() if row.expires_at else None, "controlledDrug": row.controlled_drug, "version": row.version, "lowStock": row.quantity_on_hand <= row.reorder_level}
    evidence_and_event(session, episode_ref="inventory", entity_type="inventory_item", entity_ref=row.item_ref, action="upserted", previous=previous, current=current, reason=payload.reason, risk="amber" if current["lowStock"] else "green", compliance="pharmacy")
    session.commit()
    return {"item": current}


class DiagnosticCreate(BaseModel):
    episode_ref: str
    modality: str
    requested_test: str
    urgency: str = "routine"
    specimen_ref: str | None = None
    assigned_service: str | None = None


class DiagnosticUpdate(BaseModel):
    expected_version: int
    status: str
    accession_ref: str | None = None
    report_summary: str | None = None
    critical_result: bool = False
    reason: str


def diagnostic_dict(row: DiagnosticWorkItem) -> dict[str, Any]:
    return {"workRef": row.work_ref, "episodeRef": row.episode_ref, "modality": row.modality, "requestedTest": row.requested_test, "urgency": row.urgency, "status": row.status, "specimenRef": row.specimen_ref, "accessionRef": row.accession_ref, "assignedService": row.assigned_service, "acquiredAt": row.acquired_at.isoformat() if row.acquired_at else None, "reportedAt": row.reported_at.isoformat() if row.reported_at else None, "reportSummary": row.report_summary, "criticalResult": row.critical_result, "version": row.version}


@router.post("/diagnostics")
def create_diagnostic(payload: DiagnosticCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_episode(session, payload.episode_ref)
    row = DiagnosticWorkItem(work_ref=new_ref("diagnostic"), requested_by_subject=auth.subject, **payload.model_dump())
    session.add(row)
    session.flush()
    row.evidence_event_ref = evidence_and_event(session, episode_ref=row.episode_ref, entity_type="diagnostic_work", entity_ref=row.work_ref, action="requested", previous=None, current=diagnostic_dict(row), reason="diagnostic request created", risk="amber", compliance="diagnostics")
    session.commit()
    return {"workItem": diagnostic_dict(row)}


@router.patch("/diagnostics/{work_ref}")
def update_diagnostic(work_ref: str, payload: DiagnosticUpdate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = session.exec(select(DiagnosticWorkItem).where(DiagnosticWorkItem.work_ref == work_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="diagnostic work item not found")
    require_version(row.version, payload.expected_version, "diagnostic work item")
    previous = diagnostic_dict(row)
    row.status = payload.status
    row.accession_ref = payload.accession_ref or row.accession_ref
    row.report_summary = payload.report_summary or row.report_summary
    row.critical_result = payload.critical_result
    if payload.status in {"acquired", "collected"}:
        row.acquired_at = utc_now()
    if payload.status == "reported":
        row.reported_at = utc_now()
    row.version += 1
    current = diagnostic_dict(row)
    row.evidence_event_ref = evidence_and_event(session, episode_ref=row.episode_ref, entity_type="diagnostic_work", entity_ref=row.work_ref, action=payload.status, previous=previous, current=current, reason=payload.reason, risk="red" if payload.critical_result else "amber", compliance="diagnostics")
    if payload.critical_result:
        existing = session.exec(select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.result_ref == row.work_ref)).first()
        if not existing:
            session.add(CriticalResultAcknowledgement(result_ref=row.work_ref, referral_episode_id=row.episode_ref, result_type=row.modality, severity="red", summary=row.report_summary or row.requested_test, status="awaiting_acknowledgement", assigned_to="clinical duty owner", assigned_role="clinician"))
    session.add(row)
    session.commit()
    return {"workItem": diagnostic_dict(row)}


class ChainEventCreate(BaseModel):
    specimen_ref: str
    episode_ref: str
    event_type: str
    location_ref: str | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)


@router.post("/sample-chain")
def sample_chain_event(payload: ChainEventCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_episode(session, payload.episode_ref)
    row = SampleChainEvent(event_ref=new_ref("sample"), actor_subject=auth.subject, actor_name=auth.actor_name, **payload.model_dump())
    session.add(row)
    evidence_and_event(session, episode_ref=row.episode_ref, entity_type="sample_chain_event", entity_ref=row.event_ref, action=row.event_type, previous=None, current={"eventRef": row.event_ref, "specimenRef": row.specimen_ref, "eventType": row.event_type, "locationRef": row.location_ref, "detail": row.detail}, reason="sample chain of custody recorded", risk="amber", compliance="diagnostics")
    session.commit()
    return {"event": {"eventRef": row.event_ref, "specimenRef": row.specimen_ref, "eventType": row.event_type, "occurredAt": row.occurred_at.isoformat()}}


class DischargeCreate(BaseModel):
    episode_ref: str
    medication_summary: list[dict[str, Any]] = PydanticField(default_factory=list)
    care_instructions: str = ""
    follow_up: str = ""
    warning_signs: str = ""


class DischargeUpdate(BaseModel):
    expected_version: int
    status: str
    medication_summary: list[dict[str, Any]] | None = None
    care_instructions: str | None = None
    follow_up: str | None = None
    warning_signs: str | None = None
    referring_vet_report_status: str | None = None
    owner_communication_status: str | None = None
    reason: str


def discharge_dict(row: DischargePlan) -> dict[str, Any]:
    return {"planRef": row.plan_ref, "episodeRef": row.episode_ref, "status": row.status, "medicationSummary": row.medication_summary, "careInstructions": row.care_instructions, "followUp": row.follow_up, "warningSigns": row.warning_signs, "referringVetReportStatus": row.referring_vet_report_status, "ownerCommunicationStatus": row.owner_communication_status, "approvedBy": row.approved_by_name, "approvedAt": row.approved_at.isoformat() if row.approved_at else None, "version": row.version, "evidenceEventRef": row.evidence_event_ref}


@router.post("/discharge-plans")
def create_discharge(payload: DischargeCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_episode(session, payload.episode_ref)
    row = DischargePlan(plan_ref=new_ref("discharge"), **payload.model_dump())
    session.add(row)
    session.flush()
    row.evidence_event_ref = evidence_and_event(session, episode_ref=row.episode_ref, entity_type="discharge_plan", entity_ref=row.plan_ref, action="created", previous=None, current=discharge_dict(row), reason="discharge plan created", risk="amber")
    session.commit()
    return {"plan": discharge_dict(row)}


@router.patch("/discharge-plans/{plan_ref}")
def update_discharge(plan_ref: str, payload: DischargeUpdate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = session.exec(select(DischargePlan).where(DischargePlan.plan_ref == plan_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="discharge plan not found")
    require_version(row.version, payload.expected_version, "discharge plan")
    previous = discharge_dict(row)
    for field in ("medication_summary", "care_instructions", "follow_up", "warning_signs", "referring_vet_report_status", "owner_communication_status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    status = payload.status.lower().strip()
    if status == "approved":
        if auth.role not in PRESCRIBER_ROLES:
            raise HTTPException(status_code=403, detail="clinician approval required")
        missing = []
        if not row.care_instructions: missing.append("care_instructions")
        if not row.warning_signs: missing.append("warning_signs")
        if row.owner_communication_status != "completed": missing.append("owner_communication")
        if row.referring_vet_report_status not in {"completed", "sent"}: missing.append("referring_vet_report")
        due_meds = session.exec(select(MedicationAdministration).where(MedicationAdministration.episode_ref == row.episode_ref, MedicationAdministration.status == "due")).all()
        if due_meds: missing.append("due_medication_administrations")
        if missing:
            raise HTTPException(status_code=409, detail={"message": "discharge gates incomplete", "missing": missing})
        row.approved_by_subject = auth.subject
        row.approved_by_name = auth.actor_name
        row.approved_at = utc_now()
    row.status = status
    row.version += 1
    row.updated_at = utc_now()
    current = discharge_dict(row)
    row.evidence_event_ref = evidence_and_event(session, episode_ref=row.episode_ref, entity_type="discharge_plan", entity_ref=row.plan_ref, action=status, previous=previous, current=current, reason=payload.reason, risk="amber", compliance="clinical_governance")
    session.add(row)
    session.commit()
    return {"plan": discharge_dict(row)}


@router.get("/dashboard")
def dashboard(episode_ref: str | None = None, session: Session = Depends(get_session), _: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    def filtered(model: Any, field: Any):
        query = select(model)
        if episode_ref:
            query = query.where(field == episode_ref)
        return session.exec(query).all()
    orders = filtered(MedicationOrder, MedicationOrder.episode_ref)
    administrations = filtered(MedicationAdministration, MedicationAdministration.episode_ref)
    anaesthesia = filtered(AnaesthesiaRecord, AnaesthesiaRecord.episode_ref)
    observations = filtered(ClinicalObservation, ClinicalObservation.episode_ref)
    tasks = filtered(TreatmentTask, TreatmentTask.episode_ref)
    diagnostics = filtered(DiagnosticWorkItem, DiagnosticWorkItem.episode_ref)
    discharges = filtered(DischargePlan, DischargePlan.episode_ref)
    inventory = session.exec(select(InventoryItem)).all()
    return {
        "summary": {
            "activeMedicationOrders": len([row for row in orders if row.status == "active"]),
            "overdueAdministrations": len([row for row in administrations if row.status == "due" and row.scheduled_at < utc_now()]),
            "redObservations": len([row for row in observations if row.concern_level == "red" and row.escalation_status == "pending"]),
            "overdueTasks": len([row for row in tasks if row.status != "completed" and row.due_at < utc_now()]),
            "criticalDiagnostics": len([row for row in diagnostics if row.critical_result and row.status == "reported"]),
            "lowStockItems": len([row for row in inventory if row.quantity_on_hand <= row.reorder_level]),
            "unapprovedDischarges": len([row for row in discharges if row.status != "approved"]),
        },
        "medicationOrders": [med_order_dict(row) for row in orders],
        "administrations": [administration_dict(row) for row in administrations],
        "anaesthesia": [anaesthesia_dict(row) for row in anaesthesia],
        "observations": [{"observationRef": row.observation_ref, "episodeRef": row.episode_ref, "type": row.observation_type, "values": row.values, "concernLevel": row.concern_level, "escalationStatus": row.escalation_status, "recordedAt": row.recorded_at.isoformat()} for row in observations],
        "tasks": [{"taskRef": row.task_ref, "episodeRef": row.episode_ref, "title": row.title, "status": row.status, "dueAt": row.due_at.isoformat(), "priority": row.priority, "version": row.version} for row in tasks],
        "diagnostics": [diagnostic_dict(row) for row in diagnostics],
        "dischargePlans": [discharge_dict(row) for row in discharges],
        "inventory": [{"itemRef": row.item_ref, "name": row.name, "quantityOnHand": row.quantity_on_hand, "unit": row.unit, "reorderLevel": row.reorder_level, "lowStock": row.quantity_on_hand <= row.reorder_level, "version": row.version} for row in inventory],
    }
