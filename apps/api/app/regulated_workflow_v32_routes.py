from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.regulated_workflow_v32_models import AIProvenanceV32, ServicePriceV32

router = APIRouter(prefix="/api/v32", tags=["regulated-workflow-v32"])
FINANCIAL_ROLES = ("admin", "ops_manager", "hospital_director", "governance_lead")
CLINICAL_OUTPUT_KINDS = {"clinical_note", "clinical_summary", "differential_support", "discharge_draft", "medication_proposal"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def record_event(
    session: Session,
    auth: AuthContext,
    *,
    action: str,
    entity_type: str,
    entity_ref: str,
    previous: Any,
    current: Any,
    reason: str,
    risk: str = "amber",
    episode_ref: str | None = None,
    patient_ref: str | None = None,
) -> str:
    event, _ = create_evidence_event(
        session,
        event_type=f"v32_{entity_type}_{action}",
        action=action,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        patient_case_id=patient_ref,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        justification="LucyWorks regulated workflow and provenance control",
        evidence_links=[{"type": entity_type, "id": entity_ref}],
        compliance_domain="regulated_workflow",
        risk_level=risk,
        source_module="regulated-workflow-v32",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or entity_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v32:{entity_type}:{entity_ref}:{action}:{current.get('version', current.get('status', 'event')) if isinstance(current, dict) else 'event'}",
    )
    return event.event_ref


class ServicePriceCreate(BaseModel):
    organisationRef: str = "reference"
    premisesRef: str
    serviceCode: str
    serviceName: str
    category: str
    description: str = ""
    lowerPricePence: int
    upperPricePence: int
    vatIncluded: bool = True
    standardDurationMinutes: int | None = None
    inclusions: list[str] = PydanticField(default_factory=list)
    exclusions: list[str] = PydanticField(default_factory=list)
    interpretationIncluded: bool | None = None
    status: str = "draft"
    effectiveFrom: datetime | None = None
    reason: str


class AIProvenanceCreate(BaseModel):
    episodeRef: str | None = None
    patientRef: str | None = None
    sourceEntityType: str
    sourceEntityRef: str
    outputKind: str
    provider: str
    modelName: str
    modelVersion: str | None = None
    generatedAt: datetime | None = None
    inputRefs: list[dict[str, Any]] = PydanticField(default_factory=list)
    clientDataUsed: bool = False
    dataUsePurpose: str = "clinical_assistance"
    legalBasis: str | None = None
    clientConsentRef: str | None = None
    trainingUsePermitted: bool = False
    reason: str = "AI-assisted output registered for governed review"


class AIReview(BaseModel):
    expectedVersion: int
    decision: str
    editSummary: str | None = None
    finalEntityRef: str | None = None
    reason: str


@router.post("/prices")
def create_service_price(
    payload: ServicePriceCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*FINANCIAL_ROLES)),
) -> dict[str, Any]:
    if payload.lowerPricePence < 0 or payload.upperPricePence < payload.lowerPricePence:
        raise HTTPException(status_code=422, detail="invalid service price range")
    if payload.standardDurationMinutes is not None and payload.standardDurationMinutes <= 0:
        raise HTTPException(status_code=422, detail="standard duration must be positive")
    if payload.status not in {"draft", "published"}:
        raise HTTPException(status_code=422, detail="price status must be draft or published")

    latest = session.exec(
        select(ServicePriceV32)
        .where(ServicePriceV32.premises_ref == payload.premisesRef, ServicePriceV32.service_code == payload.serviceCode)
        .order_by(ServicePriceV32.version.desc())
    ).first()
    version = latest.version + 1 if latest else 1
    effective_from = payload.effectiveFrom or utc_now()

    if payload.status == "published" and latest and latest.status == "published" and latest.effective_to is None:
        latest.effective_to = effective_from
        latest.status = "retired"
        session.add(latest)

    row = ServicePriceV32(
        price_ref=new_ref("service-price"),
        organisation_ref=payload.organisationRef,
        premises_ref=payload.premisesRef,
        service_code=payload.serviceCode,
        service_name=payload.serviceName.strip(),
        category=payload.category.strip(),
        description=payload.description.strip(),
        lower_price_pence=payload.lowerPricePence,
        upper_price_pence=payload.upperPricePence,
        vat_included=payload.vatIncluded,
        standard_duration_minutes=payload.standardDurationMinutes,
        inclusions=[item.strip() for item in payload.inclusions if item.strip()],
        exclusions=[item.strip() for item in payload.exclusions if item.strip()],
        interpretation_included=payload.interpretationIncluded,
        status=payload.status,
        version=version,
        effective_from=effective_from,
        created_by_subject=auth.subject,
        approved_by_subject=auth.subject if payload.status == "published" else None,
        approved_at=utc_now() if payload.status == "published" else None,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth,
        action="published" if row.status == "published" else "created",
        entity_type="service_price",
        entity_ref=row.price_ref,
        previous=row_dict(latest) if latest else None,
        current=row_dict(row),
        reason=payload.reason,
        risk="green" if row.status == "published" else "amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"price": row_dict(row)}


@router.get("/prices")
def list_service_prices(
    premises_ref: str | None = Query(default=None),
    status: str = Query(default="published"),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(ServicePriceV32).where(ServicePriceV32.status == status)
    if premises_ref:
        query = query.where(ServicePriceV32.premises_ref == premises_ref)
    rows = session.exec(query.order_by(ServicePriceV32.service_name, ServicePriceV32.version.desc())).all()
    return {"items": [row_dict(row) for row in rows]}


@router.post("/ai-provenance")
def create_ai_provenance(
    payload: AIProvenanceCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if payload.clientDataUsed and not (payload.legalBasis or "").strip():
        raise HTTPException(status_code=409, detail="client-data AI use requires a recorded legal basis")
    if payload.clientDataUsed and payload.trainingUsePermitted and not payload.clientConsentRef:
        raise HTTPException(status_code=409, detail="training use of client data requires explicit client consent evidence")
    if not payload.provider.strip() or not payload.modelName.strip():
        raise HTTPException(status_code=422, detail="AI provider and model name are required")

    row = AIProvenanceV32(
        provenance_ref=new_ref("ai-provenance"),
        episode_ref=payload.episodeRef,
        patient_ref=payload.patientRef,
        source_entity_type=payload.sourceEntityType,
        source_entity_ref=payload.sourceEntityRef,
        output_kind=payload.outputKind,
        provider=payload.provider.strip(),
        model_name=payload.modelName.strip(),
        model_version=payload.modelVersion,
        generated_at=payload.generatedAt or utc_now(),
        generated_by_subject=auth.subject,
        input_refs=payload.inputRefs,
        client_data_used=payload.clientDataUsed,
        data_use_purpose=payload.dataUsePurpose,
        legal_basis=payload.legalBasis,
        client_consent_ref=payload.clientConsentRef,
        training_use_permitted=payload.trainingUsePermitted,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth,
        action="registered",
        entity_type="ai_provenance",
        entity_ref=row.provenance_ref,
        episode_ref=row.episode_ref,
        patient_ref=row.patient_ref,
        previous=None,
        current=row_dict(row),
        reason=payload.reason,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"provenance": row_dict(row), "boundary": "AI output is a draft until an authorised human review is recorded."}


@router.patch("/ai-provenance/{provenance_ref}/review")
def review_ai_provenance(
    provenance_ref: str,
    payload: AIReview,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(AIProvenanceV32).where(AIProvenanceV32.provenance_ref == provenance_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="AI provenance record not found")
    if row.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale AI review", "currentVersion": row.version})
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="AI output has already been reviewed")
    if payload.decision not in {"reviewed", "rejected"}:
        raise HTTPException(status_code=422, detail="decision must be reviewed or rejected")
    if row.output_kind in CLINICAL_OUTPUT_KINDS and auth.role not in set(CLINICAL_ROLES):
        raise HTTPException(status_code=403, detail="clinical AI output requires review by a verified clinical role")
    if payload.decision == "reviewed" and not payload.finalEntityRef:
        raise HTTPException(status_code=409, detail="reviewed AI output must link to the final human-confirmed record")

    previous = row_dict(row)
    row.status = payload.decision
    row.reviewer_subject = auth.subject
    row.reviewer_name = auth.actor_name
    row.reviewer_role = auth.role
    row.reviewed_at = utc_now()
    row.edit_summary = payload.editSummary
    row.final_entity_ref = payload.finalEntityRef
    row.version += 1
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth,
        action=payload.decision,
        entity_type="ai_provenance",
        entity_ref=row.provenance_ref,
        episode_ref=row.episode_ref,
        patient_ref=row.patient_ref,
        previous=previous,
        current=row_dict(row),
        reason=payload.reason,
        risk="green" if payload.decision == "reviewed" else "amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"provenance": row_dict(row)}


@router.get("/ai-provenance/{provenance_ref}")
def get_ai_provenance(
    provenance_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    row = session.exec(select(AIProvenanceV32).where(AIProvenanceV32.provenance_ref == provenance_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="AI provenance record not found")
    return {"provenance": row_dict(row)}
