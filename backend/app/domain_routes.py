from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    AuditEvent,
    Blocker,
    DischargeReadiness,
    Episode,
    EthicsFlag,
    OwnerCommsRequirement,
    PharmacyRequest,
    StockItem,
    StockOrder,
    TriageAssessment,
    WorkItem,
)

router = APIRouter()


def log(session: Session, actor: str, action: str, entity: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity, entity_id=entity_id, summary=summary))
    session.commit()


def episode_ref(session: Session, episode_id: int | None):
    if not episode_id:
        return None
    ep = session.get(Episode, episode_id)
    return ep.episode_ref if ep else None


def make_work(session: Session, title: str, input_type: str, source: str, category: str, description: str, urgency: str, owner_role: str, ep_ref: str | None = None):
    item = WorkItem(title=title, input_type=input_type, source=source, category=category, description=description, urgency=urgency, owner_role=owner_role, linked_episode_ref=ep_ref, status="new")
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def has_open_work(session: Session, title: str, ep_ref: str | None):
    rows = session.exec(select(WorkItem).where(WorkItem.title == title)).all()
    return any((row.linked_episode_ref == ep_ref) and row.status != "done" for row in rows)


@router.get("/api/discharge-readiness")
def list_discharge(session: Session = Depends(get_session)):
    return session.exec(select(DischargeReadiness).order_by(DischargeReadiness.created_at.desc())).all()


@router.post("/api/discharge-readiness")
def create_discharge(payload: dict, session: Session = Depends(get_session)):
    discharge = DischargeReadiness(**payload)
    required = [discharge.clinician_signoff, discharge.medication_ready, discharge.owner_updated, discharge.admin_ready, discharge.results_reviewed, discharge.care_instructions_ready]
    discharge.readiness_state = "ready" if all(required) else "blocked"
    session.add(discharge)
    session.commit()
    session.refresh(discharge)

    if discharge.readiness_state == "blocked":
        ep_ref = episode_ref(session, discharge.episode_id)
        blocker = Blocker(episode_id=discharge.episode_id, blocker_type="discharge_readiness", section_name="Discharge", detail=discharge.blocker_summary or "Discharge readiness incomplete", impact="Patient cannot leave safely until discharge chain is complete", urgency=discharge.urgency, owner_role=discharge.owner_role)
        session.add(blocker)
        work = make_work(session, "Discharge readiness blocked", "discharge_blocker", "discharge_readiness", "discharge", blocker.detail, discharge.urgency, discharge.owner_role, ep_ref)
        blocker.linked_work_item_id = work.id
        session.add(blocker)

    session.commit()
    log(session, "Discharge", "created", "discharge_readiness", discharge.id or 0, discharge.readiness_state)
    return discharge


@router.post("/api/discharge-readiness/{readiness_id}/update")
def update_discharge(readiness_id: int, payload: dict, session: Session = Depends(get_session)):
    discharge = session.get(DischargeReadiness, readiness_id)
    if not discharge:
        raise HTTPException(status_code=404, detail="Discharge readiness record not found")
    for key, value in payload.items():
        if hasattr(discharge, key):
            setattr(discharge, key, value)
    required = [discharge.clinician_signoff, discharge.medication_ready, discharge.owner_updated, discharge.admin_ready, discharge.results_reviewed, discharge.care_instructions_ready]
    discharge.readiness_state = "ready" if all(required) else "blocked"
    if discharge.readiness_state == "ready":
        discharge.status = "complete"
        discharge.completed_at = datetime.now(timezone.utc)
    session.add(discharge)
    session.commit()
    log(session, "Discharge", "updated", "discharge_readiness", readiness_id, discharge.readiness_state)
    return discharge


@router.get("/api/pharmacy-requests")
def list_pharmacy(session: Session = Depends(get_session)):
    return session.exec(select(PharmacyRequest).order_by(PharmacyRequest.created_at.desc())).all()


@router.post("/api/pharmacy-requests")
def create_pharmacy(payload: dict, session: Session = Depends(get_session)):
    req = PharmacyRequest(**payload)
    session.add(req)
    session.commit()
    session.refresh(req)
    ep_ref = episode_ref(session, req.episode_id)
    make_work(session, f"Pharmacy request: {req.medication_name}", "pharmacy", "pharmacy", "pharmacy", req.compliance_note or f"{req.request_type} {req.medication_name}", req.urgency, req.owner_role, ep_ref)
    log(session, "Pharmacy", "created", "pharmacy_request", req.id or 0, req.medication_name)
    return req


@router.post("/api/pharmacy-requests/{request_id}/complete")
def complete_pharmacy(request_id: int, session: Session = Depends(get_session)):
    req = session.get(PharmacyRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Pharmacy request not found")
    req.status = "complete"
    req.completed_at = datetime.now(timezone.utc)
    session.add(req)
    session.commit()
    log(session, "Pharmacy", "completed", "pharmacy_request", request_id, req.medication_name)
    return req


@router.get("/api/stock-items")
def list_stock_items(session: Session = Depends(get_session)):
    return session.exec(select(StockItem).order_by(StockItem.category, StockItem.name)).all()


@router.post("/api/stock-items")
def create_stock_item(payload: dict, session: Session = Depends(get_session)):
    item = StockItem(**payload)
    session.add(item)
    session.commit()
    session.refresh(item)
    log(session, "Stock", "created", "stock_item", item.id or 0, item.name)
    return item


@router.get("/api/stock-orders")
def list_stock_orders(session: Session = Depends(get_session)):
    return session.exec(select(StockOrder).order_by(StockOrder.created_at.desc())).all()


@router.post("/api/stock-orders")
def create_stock_order(payload: dict, session: Session = Depends(get_session)):
    order = StockOrder(**payload)
    session.add(order)
    session.commit()
    session.refresh(order)
    ep_ref = episode_ref(session, order.episode_id)
    make_work(session, f"Stock order needed: {order.item_name}", "stock", "stock", "stock", order.reason, order.urgency, "nurse", ep_ref)
    log(session, "Stock", "created", "stock_order", order.id or 0, order.item_name)
    return order


@router.post("/api/stock-orders/{order_id}/complete")
def complete_stock_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(StockOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Stock order not found")
    order.status = "complete"
    order.completed_at = datetime.now(timezone.utc)
    session.add(order)
    session.commit()
    log(session, "Stock", "completed", "stock_order", order_id, order.item_name)
    return order


@router.post("/api/automation/run-domain-links")
def run_domain_links(session: Session = Depends(get_session)):
    created = {"owner_comms": 0, "pharmacy_requests": 0, "stock_orders": 0, "work_items": 0}

    for triage in session.exec(select(TriageAssessment).where(TriageAssessment.status != "resolved")).all():
        ep_ref = episode_ref(session, triage.episode_id)
        if triage.owner_contact_required and triage.episode_id:
            existing = session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.episode_id == triage.episode_id)).all()
            if not any("LucyFlow" in req.reason and req.status != "complete" for req in existing):
                req = OwnerCommsRequirement(episode_id=triage.episode_id, reason="LucyFlow owner update required", required_message=f"Update owner: triage route {triage.route}, urgency {triage.urgency}", owner_role=triage.assigned_owner_role, urgency=triage.urgency, status="due")
                session.add(req)
                created["owner_comms"] += 1
        if "pain" in triage.presenting_signs.lower() and triage.episode_id:
            existing = session.exec(select(PharmacyRequest).where(PharmacyRequest.episode_id == triage.episode_id)).all()
            if not any("Analgesia review" in req.medication_name and req.status != "complete" for req in existing):
                req = PharmacyRequest(episode_id=triage.episode_id, medication_name="Analgesia review", request_type="review", controlled_or_legal_status="clinical_review", authorised_supplier_required=True, quantity="as clinically directed", urgency=triage.urgency, owner_role="clinician", compliance_note="LucyFlow pain language detected; clinician/pharmacy review required")
                session.add(req)
                created["pharmacy_requests"] += 1

    for flag in session.exec(select(EthicsFlag).where(EthicsFlag.status != "resolved")).all():
        ep_ref = episode_ref(session, flag.episode_id)
        title = f"Resolve Lucy Ethics: {flag.flag_type}"
        if not has_open_work(session, title, ep_ref):
            make_work(session, title, "ethics", "lucy_ethics", "ethics", flag.detail, "red" if flag.severity == "high" else "amber", flag.owner_role, ep_ref)
            created["work_items"] += 1

    for discharge in session.exec(select(DischargeReadiness).where(DischargeReadiness.readiness_state != "ready")).all():
        ep_ref = episode_ref(session, discharge.episode_id)
        if not discharge.medication_ready and discharge.episode_id:
            existing = session.exec(select(PharmacyRequest).where(PharmacyRequest.episode_id == discharge.episode_id)).all()
            if not any("Discharge medication" in req.medication_name and req.status != "complete" for req in existing):
                req = PharmacyRequest(episode_id=discharge.episode_id, medication_name="Discharge medication", request_type="dispense", controlled_or_legal_status="standard", authorised_supplier_required=True, quantity="per discharge script", urgency=discharge.urgency, owner_role="nurse", compliance_note="Discharge readiness blocked because medication is not ready")
                session.add(req)
                created["pharmacy_requests"] += 1
        if not discharge.owner_updated and discharge.episode_id:
            existing = session.exec(select(OwnerCommsRequirement).where(OwnerCommsRequirement.episode_id == discharge.episode_id)).all()
            if not any("Discharge owner update" in req.reason and req.status != "complete" for req in existing):
                req = OwnerCommsRequirement(episode_id=discharge.episode_id, reason="Discharge owner update required", required_message="Owner must be updated before discharge can complete", owner_role=discharge.owner_role, urgency=discharge.urgency, status="due")
                session.add(req)
                created["owner_comms"] += 1
        if not has_open_work(session, "Discharge readiness blocked", ep_ref):
            make_work(session, "Discharge readiness blocked", "discharge_blocker", "automation", "discharge", discharge.blocker_summary or "Discharge readiness incomplete", discharge.urgency, discharge.owner_role, ep_ref)
            created["work_items"] += 1

    for item in session.exec(select(StockItem)).all():
        if item.current_quantity <= item.reorder_threshold:
            existing = session.exec(select(StockOrder).where(StockOrder.item_name == item.name)).all()
            if not any(order.status != "complete" for order in existing):
                order = StockOrder(stock_item_id=item.id, item_name=item.name, reason=f"Auto reorder: quantity {item.current_quantity} <= threshold {item.reorder_threshold}", urgency="amber", supplier=item.authorised_supplier, status="needed")
                session.add(order)
                created["stock_orders"] += 1

    session.commit()
    log(session, "Automation", "run", "domain_links", 0, str(created))
    return {"created": created}


@router.get("/api/domain-pressure")
def domain_pressure(session: Session = Depends(get_session)):
    discharge_blocked = len(session.exec(select(DischargeReadiness).where(DischargeReadiness.readiness_state != "ready")).all())
    pharmacy_open = len(session.exec(select(PharmacyRequest).where(PharmacyRequest.status != "complete")).all())
    stock_orders_open = len(session.exec(select(StockOrder).where(StockOrder.status != "complete")).all())
    low_stock = len([item for item in session.exec(select(StockItem)).all() if item.current_quantity <= item.reorder_threshold])
    return {"discharge_blocked": discharge_blocked, "pharmacy_open": pharmacy_open, "stock_orders_open": stock_orders_open, "low_stock": low_stock}
