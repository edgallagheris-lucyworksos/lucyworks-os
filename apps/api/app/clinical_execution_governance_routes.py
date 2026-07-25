from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, PRESCRIBER_ROLES, SENIOR_ROLES, require_authenticated
from app.clinical_execution_models import (
    AnaesthesiaRecord,
    ClinicalObservation,
    ControlledDrugLedgerEntry,
    DischargePlan,
    InventoryItem,
    InventoryMovement,
    MedicationAdministration,
)
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock
from app.v7_event_service import publish_event

router = APIRouter(prefix="/api/clinical-execution/governed", tags=["clinical-execution-governance"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def require_version(current: int, expected: int, entity: str) -> None:
    if current != expected:
        raise HTTPException(status_code=409, detail={"message": f"stale {entity}", "currentVersion": current})


def evidence_event(
    session: Session,
    *,
    episode_ref: str | None,
    entity_type: str,
    entity_ref: str,
    action: str,
    previous: Any,
    current: Any,
    reason: str,
    risk: str = "amber",
    compliance_domain: str = "clinical_governance",
) -> str:
    evidence, _ = create_evidence_event(
        session,
        event_type=f"governed_{entity_type}_{action}",
        action=action,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        compliance_domain=compliance_domain,
        risk_level=risk,
        source_module="clinical-execution-governed-v8",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or entity_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"governed:{entity_type}:{entity_ref}:{action}:{current.get('version', 'event') if isinstance(current, dict) else 'event'}",
    )
    publish_event(
        session,
        event_type=f"governed_{entity_type}_{action}",
        aggregate_type=entity_type,
        aggregate_ref=entity_ref,
        payload=current if isinstance(current, dict) else {"value": current},
        severity="error" if risk == "red" else "warning" if risk == "amber" else "info",
        correlation_id=episode_ref,
        idempotency_key=f"governed-event:{evidence.event_ref}",
    )
    return evidence.event_ref


class GovernedAnaesthesiaCreate(BaseModel):
    episode_ref: str
    block_ref: str | None = None
    anaesthetist_subject: str | None = None
    asa_status: str | None = None
    airway_plan: str | None = None
    analgesia_plan: str | None = None
    checklist: dict[str, Any] = PydanticField(default_factory=dict)
    reason: str = "anaesthesia plan recorded"


def anaesthesia_dict(row: AnaesthesiaRecord) -> dict[str, Any]:
    return {
        "recordRef": row.record_ref,
        "episodeRef": row.episode_ref,
        "blockRef": row.block_ref,
        "responsibleClinicianSubject": row.responsible_clinician_subject,
        "responsibleClinicianName": row.responsible_clinician_name,
        "anaesthetistSubject": row.anaesthetist_subject,
        "asaStatus": row.asa_status,
        "airwayPlan": row.airway_plan,
        "analgesiaPlan": row.analgesia_plan,
        "status": row.status,
        "checklist": row.checklist,
        "complications": row.complications,
        "version": row.version,
        "evidenceEventRef": row.evidence_event_ref,
    }


@router.post("/anaesthesia")
def create_governed_anaesthesia(
    payload: GovernedAnaesthesiaCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in PRESCRIBER_ROLES:
        raise HTTPException(status_code=403, detail="verified clinician authority required")
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == payload.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    if payload.block_ref and not session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == payload.block_ref)).first():
        raise HTTPException(status_code=404, detail="operational block not found")
    row = AnaesthesiaRecord(
        record_ref=new_ref("anaesthesia"),
        episode_ref=payload.episode_ref,
        block_ref=payload.block_ref,
        responsible_clinician_subject=auth.subject,
        responsible_clinician_name=auth.actor_name,
        anaesthetist_subject=payload.anaesthetist_subject,
        asa_status=payload.asa_status,
        airway_plan=payload.airway_plan,
        analgesia_plan=payload.analgesia_plan,
        checklist=payload.checklist,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = evidence_event(
        session,
        episode_ref=row.episode_ref,
        entity_type="anaesthesia_record",
        entity_ref=row.record_ref,
        action="planned",
        previous=None,
        current=anaesthesia_dict(row),
        reason=payload.reason,
    )
    session.commit()
    session.refresh(row)
    return {"record": anaesthesia_dict(row)}


class EscalationUpdate(BaseModel):
    expected_version: int
    status: str
    note: str
    escalated_to_role: str | None = None


@router.patch("/observations/{observation_ref}/escalation")
def update_observation_escalation(
    observation_ref: str,
    payload: EscalationUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = session.exec(select(ClinicalObservation).where(ClinicalObservation.observation_ref == observation_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="clinical observation not found")
    require_version(row.version, payload.expected_version, "clinical observation")
    status = payload.status.lower().strip()
    if status not in {"acknowledged", "escalated", "resolved"}:
        raise HTTPException(status_code=400, detail="unsupported escalation status")
    if status == "resolved" and auth.role not in PRESCRIBER_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinician or senior authority required to resolve escalation")
    previous = {
        "escalationStatus": row.escalation_status,
        "escalatedToRole": row.escalated_to_role,
        "version": row.version,
    }
    row.escalation_status = status
    row.escalated_to_role = payload.escalated_to_role or row.escalated_to_role
    row.escalation_note = payload.note
    if status == "resolved":
        row.resolved_by_subject = auth.subject
        row.resolved_at = utc_now()
    row.version += 1
    current = {
        "observationRef": row.observation_ref,
        "episodeRef": row.episode_ref,
        "concernLevel": row.concern_level,
        "escalationStatus": row.escalation_status,
        "escalatedToRole": row.escalated_to_role,
        "note": row.escalation_note,
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "version": row.version,
    }
    row.evidence_event_ref = evidence_event(
        session,
        episode_ref=row.episode_ref,
        entity_type="clinical_observation_escalation",
        entity_ref=row.observation_ref,
        action=status,
        previous=previous,
        current=current,
        reason=payload.note,
        risk="red" if row.concern_level == "red" else "amber",
    )
    session.add(row)
    session.commit()
    return {"observation": current}


class DiscrepancyResolution(BaseModel):
    expected_version: int
    resolution: str
    witness_subject: str


@router.patch("/controlled-drugs/{entry_ref}/discrepancy")
def resolve_controlled_drug_discrepancy(
    entry_ref: str,
    payload: DiscrepancyResolution,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior authority required")
    row = session.exec(select(ControlledDrugLedgerEntry).where(ControlledDrugLedgerEntry.entry_ref == entry_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="controlled-drug entry not found")
    require_version(row.version, payload.expected_version, "controlled-drug entry")
    if not row.discrepancy:
        raise HTTPException(status_code=409, detail="entry has no discrepancy")
    previous = {"discrepancyStatus": row.discrepancy_status, "version": row.version}
    row.discrepancy_status = "resolved"
    row.discrepancy_resolution = payload.resolution
    row.discrepancy_resolved_by_subject = auth.subject
    row.discrepancy_resolved_at = utc_now()
    row.version += 1
    current = {
        "entryRef": row.entry_ref,
        "discrepancyStatus": row.discrepancy_status,
        "resolution": row.discrepancy_resolution,
        "resolvedBy": auth.actor_name,
        "witnessSubject": payload.witness_subject,
        "resolvedAt": row.discrepancy_resolved_at.isoformat(),
        "version": row.version,
    }
    row.evidence_event_ref = evidence_event(
        session,
        episode_ref=row.episode_ref,
        entity_type="controlled_drug_discrepancy",
        entity_ref=row.entry_ref,
        action="resolved",
        previous=previous,
        current=current,
        reason=payload.resolution,
        risk="red",
        compliance_domain="medication",
    )
    session.add(row)
    session.commit()
    return {"entry": current}


class InventoryMovementCreate(BaseModel):
    item_ref: str
    movement_type: str
    quantity_change: float
    expected_item_version: int
    reason: str
    episode_ref: str | None = None


@router.post("/inventory-movements")
def create_inventory_movement(
    payload: InventoryMovementCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    item = session.exec(select(InventoryItem).where(InventoryItem.item_ref == payload.item_ref)).first()
    if not item:
        raise HTTPException(status_code=404, detail="inventory item not found")
    require_version(item.version, payload.expected_item_version, "inventory item")
    previous_quantity = item.quantity_on_hand
    new_quantity = previous_quantity + payload.quantity_change
    if new_quantity < -0.0001:
        raise HTTPException(status_code=409, detail="inventory movement would create negative stock")
    item.quantity_on_hand = new_quantity
    item.version += 1
    item.updated_at = utc_now()
    movement = InventoryMovement(
        movement_ref=new_ref("stockmove"),
        item_ref=item.item_ref,
        movement_type=payload.movement_type,
        quantity_change=payload.quantity_change,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        reason=payload.reason,
        episode_ref=payload.episode_ref,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
    )
    session.add(item)
    session.add(movement)
    session.flush()
    current = {
        "movementRef": movement.movement_ref,
        "itemRef": item.item_ref,
        "movementType": movement.movement_type,
        "quantityChange": movement.quantity_change,
        "previousQuantity": previous_quantity,
        "newQuantity": new_quantity,
        "itemVersion": item.version,
        "lowStock": new_quantity <= item.reorder_level,
    }
    movement.evidence_event_ref = evidence_event(
        session,
        episode_ref=payload.episode_ref,
        entity_type="inventory_movement",
        entity_ref=movement.movement_ref,
        action=payload.movement_type,
        previous={"quantity": previous_quantity, "itemVersion": payload.expected_item_version},
        current=current,
        reason=payload.reason,
        risk="amber" if current["lowStock"] else "green",
        compliance_domain="pharmacy",
    )
    session.commit()
    return {"movement": current, "evidenceEventRef": movement.evidence_event_ref}


class GovernedDischargeUpdate(BaseModel):
    expected_version: int
    status: str
    medication_summary: list[dict[str, Any]] | None = None
    care_instructions: str | None = None
    follow_up: str | None = None
    warning_signs: str | None = None
    referring_vet_report_status: str | None = None
    referring_vet_report_evidence_ref: str | None = None
    owner_communication_status: str | None = None
    owner_communication_evidence_ref: str | None = None
    reason: str


def discharge_dict(row: DischargePlan) -> dict[str, Any]:
    return {
        "planRef": row.plan_ref,
        "episodeRef": row.episode_ref,
        "status": row.status,
        "medicationSummary": row.medication_summary,
        "careInstructions": row.care_instructions,
        "followUp": row.follow_up,
        "warningSigns": row.warning_signs,
        "referringVetReportStatus": row.referring_vet_report_status,
        "referringVetReportEvidenceRef": row.referring_vet_report_evidence_ref,
        "ownerCommunicationStatus": row.owner_communication_status,
        "ownerCommunicationEvidenceRef": row.owner_communication_evidence_ref,
        "approvedBy": row.approved_by_name,
        "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
        "version": row.version,
        "evidenceEventRef": row.evidence_event_ref,
    }


@router.patch("/discharge-plans/{plan_ref}")
def update_governed_discharge(
    plan_ref: str,
    payload: GovernedDischargeUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = session.exec(select(DischargePlan).where(DischargePlan.plan_ref == plan_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="discharge plan not found")
    require_version(row.version, payload.expected_version, "discharge plan")
    previous = discharge_dict(row)
    for field_name in (
        "medication_summary",
        "care_instructions",
        "follow_up",
        "warning_signs",
        "referring_vet_report_status",
        "referring_vet_report_evidence_ref",
        "owner_communication_status",
        "owner_communication_evidence_ref",
    ):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(row, field_name, value)
    status = payload.status.lower().strip()
    if status == "approved":
        if auth.role not in PRESCRIBER_ROLES:
            raise HTTPException(status_code=403, detail="verified clinician approval required")
        missing: list[str] = []
        if not row.care_instructions:
            missing.append("care_instructions")
        if not row.warning_signs:
            missing.append("warning_signs")
        if row.owner_communication_status != "completed":
            missing.append("owner_communication")
        if not row.owner_communication_evidence_ref:
            missing.append("owner_communication_evidence")
        if row.referring_vet_report_status not in {"completed", "sent"}:
            missing.append("referring_vet_report")
        if not row.referring_vet_report_evidence_ref:
            missing.append("referring_vet_report_evidence")
        due_meds = session.exec(select(MedicationAdministration).where(MedicationAdministration.episode_ref == row.episode_ref, MedicationAdministration.status == "due")).all()
        if due_meds:
            missing.append("due_medication_administrations")
        if missing:
            raise HTTPException(status_code=409, detail={"message": "discharge gates incomplete", "missing": missing})
        row.approved_by_subject = auth.subject
        row.approved_by_name = auth.actor_name
        row.approved_at = utc_now()
    row.status = status
    row.version += 1
    row.updated_at = utc_now()
    current = discharge_dict(row)
    row.evidence_event_ref = evidence_event(
        session,
        episode_ref=row.episode_ref,
        entity_type="discharge_plan",
        entity_ref=row.plan_ref,
        action=status,
        previous=previous,
        current=current,
        reason=payload.reason,
        risk="amber",
    )
    session.add(row)
    session.commit()
    return {"plan": discharge_dict(row)}
