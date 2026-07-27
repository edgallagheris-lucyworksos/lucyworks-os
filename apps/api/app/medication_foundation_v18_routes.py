from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import (
    AuthContext,
    CLINICAL_ROLES,
    PRESCRIBER_ROLES,
    require_authenticated,
    require_roles,
)
from app.clinical_execution_models import MedicationOrder
from app.database import get_session
from app.detailed_hospital_completion_routes import (
    MedicationOrderFromReview,
    prescribe_from_safety_review,
)
from app.detailed_hospital_models import (
    FormularyDoseRuleV8,
    FormularyMedicineV8,
    MedicationSafetyReviewV8,
    PatientAllergyV8,
    PatientClinicalRecordV8,
    PatientProblemV8,
    PatientWeightV8,
)
from app.detailed_hospital_routes import record_evidence, require_episode, require_patient, row_dict
from app.hospital_ops_models import CanonicalEpisodeState
from app.medication_foundation_v18_models import (
    DoseCalculationV18,
    MedicationProposalV18,
    MedicationProtocolV18,
    ProductImportBatchV18,
    VeterinaryProductV18,
)


router = APIRouter(prefix="/api/v18/medications", tags=["medication-foundation-v18"])
CATALOGUE_ADMIN_ROLES = {"admin", "clinical_director", "governance_lead", "hospital_director"}
PROTOCOL_GOVERNANCE_ROLES = set(PRESCRIBER_ROLES) | {"governance_lead"}
VMD_XML_URL = "https://www.vmd.defra.gov.uk/productinformationdatabase/downloads/VMD_ProductInformationDatabase.xml"
MAX_XML_BYTES = 100 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def species_key(value: str) -> str:
    item = normalise(value)
    aliases = {
        "dogs": "dog", "canine": "dog", "cats": "cat", "feline": "cat",
        "horses": "horse", "equine": "horse", "rabbits": "rabbit",
        "pigs": "pig", "swine": "pig", "cattle": "cattle", "bovine": "cattle",
    }
    return aliases.get(item, item[:-1] if item.endswith("s") and len(item) > 3 else item)


def stable_ref(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def product_source_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def decimal(value: float | int | str) -> Decimal:
    return Decimal(str(value))


def rounded(value: Decimal, places: str = "0.000001") -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def round_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    if increment <= 0:
        raise HTTPException(status_code=422, detail="rounding increment must be greater than zero")
    return (value / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * increment


class CatalogueProductInput(BaseModel):
    source_product_id: str
    territory: str
    product_name: str
    marketing_authorisation_holder: str | None = None
    distribution_category: str | None = None
    authorisation_status: str = "current"
    pharmaceutical_form: str | None = None
    active_substances: list[str] = PydanticField(default_factory=list)
    target_species: list[str] = PydanticField(default_factory=list)
    routes: list[str] = PydanticField(default_factory=list)
    strengths: list[dict[str, Any]] = PydanticField(default_factory=list)
    concentration_mg_per_ml: float | None = None
    contraindications: list[dict[str, Any]] = PydanticField(default_factory=list)
    warnings: list[dict[str, Any]] = PydanticField(default_factory=list)
    withdrawal_periods: list[dict[str, Any]] = PydanticField(default_factory=list)
    spc_version: str | None = None
    source_updated_at: datetime | None = None
    source_url: str | None = None


class CatalogueImportRequest(BaseModel):
    source_name: str = "VMD Product Information Database"
    source_url: str
    source_sha256: str
    source_format: str = "xml"
    schema_fingerprint: str
    products: list[CatalogueProductInput]


class ProtocolCreate(BaseModel):
    organisation_ref: str = "reference"
    product_ref: str | None = None
    generic_name: str
    species: str
    indication: str
    route: str
    recommended_mg_per_kg: float
    minimum_mg_per_kg: float | None = None
    maximum_mg_per_kg: float | None = None
    maximum_single_dose_mg: float | None = None
    interval_hours: float | None = None
    concentration_override_mg_per_ml: float | None = None
    renal_adjustment: str | None = None
    hepatic_adjustment: str | None = None
    source_type: str
    source_reference: str
    source_version: str
    review_due_at: datetime | None = None
    reason: str


class ProtocolApprove(BaseModel):
    expected_version: int
    reason: str


class DoseCalculateRequest(BaseModel):
    episode_ref: str
    product_ref: str
    protocol_ref: str
    requested_mg_per_kg: float | None = None
    rounding_increment_ml: float = 0.01
    reason: str = "Deterministic patient-specific dose calculation"


class CalculationReviewRequest(BaseModel):
    frequency: str
    reason: str


class ProposalPrescribeRequest(BaseModel):
    expected_version: int
    frequency: str
    starts_at: datetime
    ends_at: datetime | None = None
    scheduled_times: list[datetime] = PydanticField(default_factory=list)
    reason: str


def _tag(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.rsplit("}", 1)[-1].lower())


def _texts(node: ElementTree.Element, aliases: set[str]) -> list[str]:
    out: list[str] = []
    for child in node.iter():
        if _tag(child.tag) in aliases and child.text and child.text.strip():
            value = child.text.strip()
            if value not in out:
                out.append(value)
    return out


def _first(node: ElementTree.Element, aliases: set[str]) -> str | None:
    values = _texts(node, aliases)
    return values[0] if values else None


def infer_concentration_mg_per_ml(product_name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|micrograms?|mcg|µg|g)\s*/\s*(ml|mL)\b", product_name, re.I)
    if not match:
        return None
    amount = Decimal(match.group(1))
    unit = match.group(2).lower()
    if unit == "g":
        amount *= Decimal("1000")
    elif unit in {"microgram", "micrograms", "mcg", "µg"}:
        amount /= Decimal("1000")
    return rounded(amount)


def parse_vmd_xml(raw: bytes, source_url: str = VMD_XML_URL) -> tuple[str, list[CatalogueProductInput]]:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise HTTPException(status_code=422, detail=f"VMD XML could not be parsed: {exc}") from exc

    all_tags = sorted({_tag(node.tag) for node in root.iter()})
    schema_fingerprint = hashlib.sha256("|".join(all_tags).encode("utf-8")).hexdigest()
    name_aliases = {"productname", "name", "producttitle"}
    id_aliases = {"vmnumber", "vmno", "marketingauthorisationnumber", "authorisationnumber"}
    territory_aliases = {"territory", "authorisationterritory"}
    holder_aliases = {"maholder", "marketingauthorisationholder", "authorisationholder"}
    category_aliases = {"distributioncategory", "legalcategory"}
    form_aliases = {"pharmaceuticalform", "dosageform"}
    active_aliases = {"activesubstance", "activesubstances", "activeingredient", "activeingredients"}
    species_aliases = {"targetspecies", "species"}
    route_aliases = {"routeofadministration", "administrationroute", "routesofadministration"}
    status_aliases = {"authorisationstatus", "status"}
    updated_aliases = {"lastupdated", "updateddate", "dateupdated", "spcdate"}

    products: list[CatalogueProductInput] = []
    seen: set[tuple[str, str]] = set()
    for node in root.iter():
        direct_tags = {_tag(child.tag) for child in list(node)}
        if not (direct_tags & name_aliases and direct_tags & id_aliases):
            continue
        product_name = _first(node, name_aliases)
        source_product_id = _first(node, id_aliases)
        if not product_name or not source_product_id:
            continue
        territory = _first(node, territory_aliases) or "United Kingdom"
        key = (normalise(territory), normalise(source_product_id))
        if key in seen:
            continue
        seen.add(key)
        updated_text = _first(node, updated_aliases)
        updated_at = None
        if updated_text:
            try:
                updated_at = datetime.fromisoformat(updated_text.replace("Z", "+00:00"))
            except ValueError:
                updated_at = None
        products.append(CatalogueProductInput(
            source_product_id=source_product_id,
            territory=territory,
            product_name=product_name,
            marketing_authorisation_holder=_first(node, holder_aliases),
            distribution_category=_first(node, category_aliases),
            authorisation_status=_first(node, status_aliases) or "current",
            pharmaceutical_form=_first(node, form_aliases),
            active_substances=_texts(node, active_aliases),
            target_species=_texts(node, species_aliases),
            routes=_texts(node, route_aliases),
            concentration_mg_per_ml=infer_concentration_mg_per_ml(product_name),
            source_updated_at=updated_at,
            source_url=source_url,
        ))
    if not products:
        raise HTTPException(status_code=422, detail={
            "message": "No product records were recognised in the VMD XML",
            "schemaFingerprint": schema_fingerprint,
            "detectedTags": all_tags[:100],
        })
    return schema_fingerprint, products


def import_catalogue(session: Session, payload: CatalogueImportRequest, auth: AuthContext) -> dict[str, Any]:
    existing_batch = session.exec(select(ProductImportBatchV18).where(
        ProductImportBatchV18.source_sha256 == payload.source_sha256
    )).first()
    if existing_batch:
        return {"batch": row_dict(existing_batch), "created": False}

    batch_ref = stable_ref("product-import", payload.source_name, payload.source_sha256)
    batch = ProductImportBatchV18(
        batch_ref=batch_ref,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_sha256=payload.source_sha256,
        source_format=payload.source_format,
        schema_fingerprint=payload.schema_fingerprint,
        product_count=len(payload.products),
        imported_by_subject=auth.subject,
        imported_by_name=auth.actor_name,
    )
    created = updated = unchanged = 0
    for item in payload.products:
        canonical = item.model_dump(mode="json")
        item_hash = product_source_hash(canonical)
        row = session.exec(select(VeterinaryProductV18).where(
            VeterinaryProductV18.source_name == payload.source_name,
            VeterinaryProductV18.territory == item.territory,
            VeterinaryProductV18.source_product_id == item.source_product_id,
        )).first()
        if row and row.source_hash == item_hash:
            unchanged += 1
            continue
        if not row:
            row = VeterinaryProductV18(
                product_ref=stable_ref("product", payload.source_name, item.territory, item.source_product_id),
                source_name=payload.source_name,
                source_product_id=item.source_product_id,
                territory=item.territory,
                product_name=item.product_name,
                source_hash=item_hash,
                imported_batch_ref=batch_ref,
            )
            created += 1
        else:
            row.version += 1
            updated += 1
        for key, value in canonical.items():
            setattr(row, key, value)
        row.source_hash = item_hash
        row.imported_batch_ref = batch_ref
        row.updated_at = utc_now()
        session.add(row)

    batch.created_count = created
    batch.updated_count = updated
    batch.unchanged_count = unchanged
    session.add(batch)
    session.flush()
    batch.evidence_event_ref = record_evidence(
        session,
        entity_type="product_import_batch",
        entity_ref=batch_ref,
        action="import_catalogue",
        episode_ref=None,
        patient_ref=None,
        previous=None,
        current=row_dict(batch),
        reason=f"Imported versioned veterinary product catalogue from {payload.source_name}",
        risk="amber",
        domain="medication",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return {"batch": row_dict(batch), "created": True}


def ensure_formulary_bridge(session: Session, protocol: MedicationProtocolV18, product: VeterinaryProductV18 | None) -> None:
    medicine_ref = product.product_ref if product else stable_ref("medicine", protocol.organisation_ref, protocol.generic_name)
    medicine = session.exec(select(FormularyMedicineV8).where(
        FormularyMedicineV8.medicine_ref == medicine_ref
    )).first()
    if not medicine:
        medicine = FormularyMedicineV8(
            medicine_ref=medicine_ref,
            generic_name=protocol.generic_name,
            brand_names=[product.product_name] if product else [],
            routes=[protocol.route],
            contraindications=product.contraindications if product else [],
            interactions=[],
            status="approved",
            approved_by_subject=protocol.approved_by_subject,
            approved_at=protocol.approved_at,
        )
    else:
        medicine.generic_name = protocol.generic_name
        medicine.brand_names = sorted(set((medicine.brand_names or []) + ([product.product_name] if product else [])))
        medicine.routes = sorted(set((medicine.routes or []) + [protocol.route]))
        medicine.contraindications = product.contraindications if product else medicine.contraindications
        medicine.status = "approved"
        medicine.approved_by_subject = protocol.approved_by_subject
        medicine.approved_at = protocol.approved_at
        medicine.version += 1
    session.add(medicine)

    rule_ref = f"v18-{protocol.protocol_ref}"
    rule = session.exec(select(FormularyDoseRuleV8).where(FormularyDoseRuleV8.rule_ref == rule_ref)).first()
    if not rule:
        rule = FormularyDoseRuleV8(
            rule_ref=rule_ref,
            medicine_ref=medicine_ref,
            species=protocol.species,
            indication=protocol.indication,
            route=protocol.route,
            minimum_mg_per_kg=protocol.minimum_mg_per_kg,
            maximum_mg_per_kg=protocol.maximum_mg_per_kg,
            maximum_single_dose_mg=protocol.maximum_single_dose_mg,
            minimum_interval_hours=protocol.interval_hours,
            renal_adjustment=protocol.renal_adjustment,
            hepatic_adjustment=protocol.hepatic_adjustment,
            source_reference=f"{protocol.source_type}:{protocol.source_reference}@{protocol.source_version}",
            status="approved",
        )
    else:
        rule.minimum_mg_per_kg = protocol.minimum_mg_per_kg
        rule.maximum_mg_per_kg = protocol.maximum_mg_per_kg
        rule.maximum_single_dose_mg = protocol.maximum_single_dose_mg
        rule.minimum_interval_hours = protocol.interval_hours
        rule.source_reference = f"{protocol.source_type}:{protocol.source_reference}@{protocol.source_version}"
        rule.status = "approved"
        rule.version += 1
    session.add(rule)


@router.get("/catalogue")
def list_catalogue(
    q: str | None = None,
    territory: str | None = None,
    species: str | None = None,
    status: str | None = "current",
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(VeterinaryProductV18).order_by(VeterinaryProductV18.product_name)).all()
    if q:
        term = normalise(q)
        rows = [row for row in rows if term in normalise(row.product_name)
                or term in normalise(row.source_product_id)
                or any(term in normalise(item) for item in row.active_substances)]
    if territory:
        rows = [row for row in rows if normalise(row.territory) == normalise(territory)]
    if species:
        requested = species_key(species)
        rows = [row for row in rows if requested in {species_key(item) for item in row.target_species}]
    if status:
        rows = [row for row in rows if normalise(row.authorisation_status) == normalise(status)]
    return {"products": [row_dict(row) for row in rows[:limit]], "count": min(len(rows), limit), "totalMatched": len(rows)}


@router.post("/catalogue/import")
def import_catalogue_endpoint(
    payload: CatalogueImportRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CATALOGUE_ADMIN_ROLES)),
) -> dict[str, Any]:
    return import_catalogue(session, payload, auth)


@router.post("/catalogue/sync-vmd")
def sync_vmd_catalogue(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CATALOGUE_ADMIN_ROLES)),
) -> dict[str, Any]:
    parsed = urlparse(VMD_XML_URL)
    if parsed.scheme != "https" or parsed.hostname != "www.vmd.defra.gov.uk":
        raise HTTPException(status_code=500, detail="VMD source allowlist is invalid")
    request = Request(VMD_XML_URL, headers={"User-Agent": "LucyWorksOS/18 veterinary-product-sync"})
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read(MAX_XML_BYTES + 1)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to download the VMD product snapshot: {exc}") from exc
    if len(raw) > MAX_XML_BYTES:
        raise HTTPException(status_code=413, detail="VMD product snapshot exceeds the configured import limit")
    source_sha = hashlib.sha256(raw).hexdigest()
    schema_fingerprint, products = parse_vmd_xml(raw)
    return import_catalogue(session, CatalogueImportRequest(
        source_url=VMD_XML_URL,
        source_sha256=source_sha,
        schema_fingerprint=schema_fingerprint,
        products=products,
    ), auth)


@router.get("/protocols")
def list_protocols(
    product_ref: str | None = None,
    species: str | None = None,
    indication: str | None = None,
    status: str | None = "approved",
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(MedicationProtocolV18).order_by(MedicationProtocolV18.generic_name)).all()
    if product_ref:
        rows = [row for row in rows if row.product_ref == product_ref]
    if species:
        rows = [row for row in rows if species_key(row.species) == species_key(species)]
    if indication:
        term = normalise(indication)
        rows = [row for row in rows if term in normalise(row.indication)]
    if status:
        rows = [row for row in rows if row.status == status]
    return {"protocols": [row_dict(row) for row in rows], "count": len(rows)}


@router.post("/protocols")
def create_protocol(
    payload: ProtocolCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PROTOCOL_GOVERNANCE_ROLES)),
) -> dict[str, Any]:
    if payload.recommended_mg_per_kg <= 0:
        raise HTTPException(status_code=422, detail="recommended dose must be greater than zero")
    if payload.minimum_mg_per_kg is not None and payload.recommended_mg_per_kg < payload.minimum_mg_per_kg:
        raise HTTPException(status_code=422, detail="recommended dose is below the protocol minimum")
    if payload.maximum_mg_per_kg is not None and payload.recommended_mg_per_kg > payload.maximum_mg_per_kg:
        raise HTTPException(status_code=422, detail="recommended dose is above the protocol maximum")
    if payload.product_ref:
        product = session.exec(select(VeterinaryProductV18).where(
            VeterinaryProductV18.product_ref == payload.product_ref
        )).first()
        if not product:
            raise HTTPException(status_code=404, detail="catalogue product not found")
    protocol_ref = stable_ref(
        "protocol", payload.organisation_ref, payload.product_ref or payload.generic_name,
        payload.species, payload.indication, payload.route,
        payload.source_reference, payload.source_version,
    )
    existing = session.exec(select(MedicationProtocolV18).where(
        MedicationProtocolV18.protocol_ref == protocol_ref
    )).first()
    if existing:
        return {"protocol": row_dict(existing), "created": False}
    row = MedicationProtocolV18(protocol_ref=protocol_ref, **payload.model_dump(exclude={"reason"}))
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_evidence(
        session, entity_type="medication_protocol", entity_ref=protocol_ref,
        action="create_draft", episode_ref=None, patient_ref=None,
        previous=None, current=row_dict(row), reason=payload.reason,
        risk="amber", domain="medication",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"protocol": row_dict(row), "created": True}


@router.patch("/protocols/{protocol_ref}/approve")
def approve_protocol(
    protocol_ref: str,
    payload: ProtocolApprove,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PROTOCOL_GOVERNANCE_ROLES)),
) -> dict[str, Any]:
    query = select(MedicationProtocolV18).where(MedicationProtocolV18.protocol_ref == protocol_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="medication protocol not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale medication protocol", "currentVersion": row.version})
    product = None
    if row.product_ref:
        product = session.exec(select(VeterinaryProductV18).where(
            VeterinaryProductV18.product_ref == row.product_ref
        )).first()
        if not product:
            raise HTTPException(status_code=409, detail="linked catalogue product no longer exists")
        if normalise(product.authorisation_status) != "current":
            raise HTTPException(status_code=409, detail="linked product is not currently authorised")
    previous = row_dict(row)
    row.status = "approved"
    row.approved_by_subject = auth.subject
    row.approved_by_name = auth.actor_name
    row.approved_at = utc_now()
    row.updated_at = utc_now()
    row.version += 1
    ensure_formulary_bridge(session, row, product)
    row.evidence_event_ref = record_evidence(
        session, entity_type="medication_protocol", entity_ref=protocol_ref,
        action="approve", episode_ref=None, patient_ref=None,
        previous=previous, current=row_dict(row), reason=payload.reason,
        risk="amber", domain="medication",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"protocol": row_dict(row)}


def episode_patient(session: Session, episode_ref: str) -> tuple[CanonicalEpisodeState, PatientClinicalRecordV8]:
    episode = require_episode(session, episode_ref)
    if not episode.patient_ref:
        raise HTTPException(status_code=409, detail="episode is not linked to a canonical patient")
    patient = require_patient(session, episode.patient_ref)
    return episode, patient


def latest_weight(session: Session, patient_ref: str) -> PatientWeightV8:
    row = session.exec(select(PatientWeightV8).where(
        PatientWeightV8.patient_ref == patient_ref
    ).order_by(PatientWeightV8.measured_at.desc())).first()
    if not row:
        raise HTTPException(status_code=409, detail="a verified current weight is required before dose calculation")
    return row


@router.get("/episodes/{episode_ref}/workspace")
def medication_workspace(
    episode_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*CLINICAL_ROLES)),
) -> dict[str, Any]:
    episode, patient = episode_patient(session, episode_ref)
    weight = session.exec(select(PatientWeightV8).where(
        PatientWeightV8.patient_ref == patient.patient_ref
    ).order_by(PatientWeightV8.measured_at.desc())).first()
    allergies = session.exec(select(PatientAllergyV8).where(
        PatientAllergyV8.patient_ref == patient.patient_ref,
        PatientAllergyV8.status == "active",
    )).all()
    active_orders = session.exec(select(MedicationOrder).where(
        MedicationOrder.patient_ref == patient.patient_ref,
        MedicationOrder.status == "active",
    )).all()
    calculations = session.exec(select(DoseCalculationV18).where(
        DoseCalculationV18.episode_ref == episode_ref
    ).order_by(DoseCalculationV18.created_at.desc())).all()
    proposals = session.exec(select(MedicationProposalV18).where(
        MedicationProposalV18.episode_ref == episode_ref
    ).order_by(MedicationProposalV18.created_at.desc())).all()
    return {
        "episode": row_dict(episode), "patient": row_dict(patient),
        "weight": row_dict(weight) if weight else None,
        "allergies": [row_dict(row) for row in allergies],
        "activeOrders": [row_dict(row) for row in active_orders],
        "calculations": [row_dict(row) for row in calculations[:20]],
        "proposals": [row_dict(row) for row in proposals[:20]],
        "clinicalBoundary": "LucyWorks calculates from versioned data and exposes warnings. A permitted veterinary prescriber remains responsible for the prescription.",
    }


@router.post("/calculate")
def calculate_dose(
    payload: DoseCalculateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES)),
) -> dict[str, Any]:
    episode, patient = episode_patient(session, payload.episode_ref)
    product = session.exec(select(VeterinaryProductV18).where(
        VeterinaryProductV18.product_ref == payload.product_ref
    )).first()
    if not product:
        raise HTTPException(status_code=404, detail="catalogue product not found")
    protocol = session.exec(select(MedicationProtocolV18).where(
        MedicationProtocolV18.protocol_ref == payload.protocol_ref
    )).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="medication protocol not found")
    weight = latest_weight(session, patient.patient_ref)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if protocol.status != "approved":
        blockers.append({"code": "protocol_not_approved", "message": "The selected dose protocol is not approved."})
    if protocol.product_ref and protocol.product_ref != product.product_ref:
        blockers.append({"code": "protocol_product_mismatch", "message": "The dose protocol belongs to a different product."})
    if normalise(product.authorisation_status) != "current":
        blockers.append({"code": "product_not_current", "message": f"Product authorisation status is {product.authorisation_status}."})
    if species_key(protocol.species) != species_key(patient.species):
        blockers.append({"code": "species_mismatch", "message": f"Protocol is for {protocol.species}, patient is {patient.species}."})
    if product.target_species and species_key(patient.species) not in {species_key(item) for item in product.target_species}:
        blockers.append({"code": "product_species_mismatch", "message": "The authorised product species do not include this patient species."})
    if product.routes and normalise(protocol.route) not in {normalise(item) for item in product.routes}:
        blockers.append({"code": "route_mismatch", "message": "The selected route is not listed for this product."})

    weight_age_days = max(0, int((utc_now() - aware(weight.measured_at)).total_seconds() // 86400))
    if weight_age_days > 90:
        blockers.append({"code": "weight_too_old", "message": f"Recorded weight is {weight_age_days} days old."})
    elif weight_age_days > 30:
        warnings.append({"code": "weight_stale", "message": f"Recorded weight is {weight_age_days} days old; confirm it remains clinically appropriate."})

    requested = decimal(payload.requested_mg_per_kg if payload.requested_mg_per_kg is not None else protocol.recommended_mg_per_kg)
    if requested <= 0:
        raise HTTPException(status_code=422, detail="dose in mg/kg must be greater than zero")
    if protocol.minimum_mg_per_kg is not None and requested < decimal(protocol.minimum_mg_per_kg):
        blockers.append({"code": "below_protocol_range", "message": f"Dose is below the approved minimum of {protocol.minimum_mg_per_kg:g} mg/kg."})
    if protocol.maximum_mg_per_kg is not None and requested > decimal(protocol.maximum_mg_per_kg):
        blockers.append({"code": "above_protocol_range", "message": f"Dose exceeds the approved maximum of {protocol.maximum_mg_per_kg:g} mg/kg."})

    dose_mg = requested * decimal(weight.weight_kg)
    if protocol.maximum_single_dose_mg is not None and dose_mg > decimal(protocol.maximum_single_dose_mg):
        blockers.append({"code": "maximum_single_dose", "message": f"Calculated dose exceeds the approved single-dose maximum of {protocol.maximum_single_dose_mg:g} mg."})

    allergy_terms = {normalise(item) for item in product.active_substances + [protocol.generic_name, product.product_name]}
    allergies = session.exec(select(PatientAllergyV8).where(
        PatientAllergyV8.patient_ref == patient.patient_ref,
        PatientAllergyV8.status == "active",
    )).all()
    for allergy in allergies:
        substance = normalise(allergy.substance_name)
        if substance and any(substance in term or term in substance for term in allergy_terms if term):
            target = blockers if allergy.severity == "red" or allergy.confirmed else warnings
            target.append({"code": "allergy_match", "message": f"Recorded allergy/alert matches {allergy.substance_name}: {allergy.reaction}."})

    active_orders = session.exec(select(MedicationOrder).where(
        MedicationOrder.patient_ref == patient.patient_ref,
        MedicationOrder.status == "active",
    )).all()
    for order in active_orders:
        if order.medication_ref == product.product_ref or normalise(order.medication_name) in allergy_terms:
            blockers.append({"code": "duplicate_active_medication", "message": f"An active order already exists: {order.medication_name} ({order.order_ref})."})

    active_problems = session.exec(select(PatientProblemV8).where(
        PatientProblemV8.patient_ref == patient.patient_ref,
        PatientProblemV8.status == "active",
    )).all()
    problem_text = " | ".join(normalise(f"{item.title} {item.description}") for item in active_problems)
    for item in product.contraindications:
        phrase = normalise(item.get("problemContains") or item.get("problem_contains") or item.get("condition"))
        if phrase and phrase in problem_text:
            severity = normalise(item.get("severity")) or "red"
            target = blockers if severity == "red" else warnings
            target.append({"code": "contraindication_match", "message": item.get("message") or f"Contraindication matches active problem: {phrase}."})

    concentration = protocol.concentration_override_mg_per_ml or product.concentration_mg_per_ml
    calculated_volume: Decimal | None = None
    rounded_volume: Decimal | None = None
    increment: Decimal | None = None
    if concentration and concentration > 0:
        calculated_volume = dose_mg / decimal(concentration)
        increment = decimal(payload.rounding_increment_ml)
        rounded_volume = round_to_increment(calculated_volume, increment)
        relative_rounding = abs(rounded_volume - calculated_volume) / calculated_volume if calculated_volume else Decimal("0")
        if relative_rounding > Decimal("0.05"):
            warnings.append({"code": "material_rounding", "message": "Selected volume rounding changes the calculated volume by more than 5%."})
    else:
        warnings.append({"code": "volume_unavailable", "message": "No governed liquid concentration is recorded; LucyWorks calculated the dose in mg only."})

    warnings.extend(product.warnings or [])
    outcome = "blocked" if blockers else "warning" if warnings else "clear"
    calculation_ref = f"calculation-{uuid4().hex}"
    row = DoseCalculationV18(
        calculation_ref=calculation_ref,
        patient_ref=patient.patient_ref,
        episode_ref=episode.episode_ref,
        product_ref=product.product_ref,
        protocol_ref=protocol.protocol_ref,
        weight_ref=weight.weight_ref,
        weight_kg=weight.weight_kg,
        dose_mg_per_kg=rounded(requested),
        calculated_dose_mg=rounded(dose_mg),
        concentration_mg_per_ml=float(concentration) if concentration else None,
        calculated_volume_ml=rounded(calculated_volume) if calculated_volume is not None else None,
        rounded_volume_ml=rounded(rounded_volume) if rounded_volume is not None else None,
        rounding_increment_ml=rounded(increment) if increment is not None else None,
        route=protocol.route,
        indication=protocol.indication,
        outcome=outcome,
        warnings=warnings,
        blockers=blockers,
        source_snapshot={
            "productRef": product.product_ref, "productVersion": product.version,
            "productSourceHash": product.source_hash, "spcVersion": product.spc_version,
            "protocolRef": protocol.protocol_ref, "protocolVersion": protocol.version,
            "protocolSourceType": protocol.source_type,
            "protocolSourceReference": protocol.source_reference,
            "protocolSourceVersion": protocol.source_version,
            "weightRef": weight.weight_ref, "weightMeasuredAt": weight.measured_at.isoformat(),
        },
        calculated_by_subject=auth.subject,
        calculated_by_name=auth.actor_name,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_evidence(
        session, entity_type="dose_calculation", entity_ref=calculation_ref,
        action="calculate", episode_ref=episode.episode_ref, patient_ref=patient.patient_ref,
        previous=None, current=row_dict(row), reason=payload.reason,
        risk="red" if blockers else "amber" if warnings else "green", domain="medication",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"calculation": row_dict(row), "product": row_dict(product),
            "protocol": row_dict(protocol), "patient": row_dict(patient), "weight": row_dict(weight)}


@router.post("/calculations/{calculation_ref}/review")
def review_calculation(
    calculation_ref: str,
    payload: CalculationReviewRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES)),
) -> dict[str, Any]:
    calculation = session.exec(select(DoseCalculationV18).where(
        DoseCalculationV18.calculation_ref == calculation_ref
    )).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="dose calculation not found")
    if calculation.blockers:
        raise HTTPException(status_code=409, detail={"message": "dose calculation is blocked", "blockers": calculation.blockers})
    product = session.exec(select(VeterinaryProductV18).where(
        VeterinaryProductV18.product_ref == calculation.product_ref
    )).first()
    protocol = session.exec(select(MedicationProtocolV18).where(
        MedicationProtocolV18.protocol_ref == calculation.protocol_ref
    )).first()
    if not product or normalise(product.authorisation_status) != "current":
        raise HTTPException(status_code=409, detail="catalogue product is no longer current")
    if not protocol or protocol.status != "approved":
        raise HTTPException(status_code=409, detail="dose protocol is no longer approved")
    existing = session.exec(select(MedicationProposalV18).where(
        MedicationProposalV18.calculation_ref == calculation_ref
    )).first()
    if existing:
        return {"proposal": row_dict(existing), "created": False}

    ensure_formulary_bridge(session, protocol, product)
    safety_ref = stable_ref("review", calculation_ref, auth.subject)
    safety = MedicationSafetyReviewV8(
        review_ref=safety_ref,
        patient_ref=calculation.patient_ref,
        episode_ref=calculation.episode_ref,
        medicine_ref=product.product_ref,
        proposed_dose_mg=calculation.calculated_dose_mg,
        proposed_route=calculation.route,
        proposed_interval_hours=protocol.interval_hours,
        weight_kg=calculation.weight_kg,
        calculated_mg_per_kg=calculation.dose_mg_per_kg,
        outcome="warning" if calculation.warnings else "clear",
        warnings=calculation.warnings,
        blocks_order=False,
        reviewed_by_subject=auth.subject,
    )
    proposal_ref = stable_ref("proposal", calculation_ref)
    proposal = MedicationProposalV18(
        proposal_ref=proposal_ref,
        calculation_ref=calculation_ref,
        safety_review_ref=safety_ref,
        patient_ref=calculation.patient_ref,
        episode_ref=calculation.episode_ref,
        product_ref=calculation.product_ref,
        protocol_ref=calculation.protocol_ref,
        medication_name=product.product_name,
        dose_mg=calculation.calculated_dose_mg,
        volume_ml=calculation.rounded_volume_ml,
        route=calculation.route,
        frequency=payload.frequency,
        status="reviewed",
        created_by_subject=calculation.calculated_by_subject,
        created_by_name=calculation.calculated_by_name,
        reviewed_by_subject=auth.subject,
        reviewed_by_name=auth.actor_name,
        reviewed_at=utc_now(),
    )
    session.add(safety)
    session.add(proposal)
    session.flush()
    proposal.evidence_event_ref = record_evidence(
        session, entity_type="medication_proposal", entity_ref=proposal_ref,
        action="prescriber_review", episode_ref=calculation.episode_ref,
        patient_ref=calculation.patient_ref, previous=None, current=row_dict(proposal),
        reason=payload.reason, risk="amber" if calculation.warnings else "green", domain="medication",
    )
    safety.evidence_event_ref = proposal.evidence_event_ref
    session.add(safety)
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return {"proposal": row_dict(proposal), "safetyReview": row_dict(safety), "created": True}


@router.post("/proposals/{proposal_ref}/prescribe")
def prescribe_proposal(
    proposal_ref: str,
    payload: ProposalPrescribeRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES)),
) -> dict[str, Any]:
    query = select(MedicationProposalV18).where(MedicationProposalV18.proposal_ref == proposal_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    proposal = session.exec(query).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="medication proposal not found")
    if proposal.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale medication proposal", "currentVersion": proposal.version})
    if proposal.status == "prescribed" and proposal.prescription_order_ref:
        order = session.exec(select(MedicationOrder).where(
            MedicationOrder.order_ref == proposal.prescription_order_ref
        )).first()
        return {"proposal": row_dict(proposal), "order": row_dict(order) if order else None, "created": False}
    if proposal.status != "reviewed" or not proposal.safety_review_ref:
        raise HTTPException(status_code=409, detail="proposal must be reviewed by a permitted prescriber before issue")

    previous = row_dict(proposal)
    result = prescribe_from_safety_review(
        proposal.episode_ref,
        MedicationOrderFromReview(
            patient_ref=proposal.patient_ref,
            safety_review_ref=proposal.safety_review_ref,
            medication_name=proposal.medication_name,
            frequency=payload.frequency,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            scheduled_times=payload.scheduled_times,
            reason=payload.reason,
        ),
        session,
        auth,
    )
    order = result["order"]
    proposal.frequency = payload.frequency
    proposal.status = "prescribed"
    proposal.prescription_order_ref = order["order_ref"]
    proposal.version += 1
    proposal.updated_at = utc_now()
    proposal.evidence_event_ref = record_evidence(
        session, entity_type="medication_proposal", entity_ref=proposal_ref,
        action="prescribe", episode_ref=proposal.episode_ref, patient_ref=proposal.patient_ref,
        previous=previous, current=row_dict(proposal), reason=payload.reason,
        risk="amber", domain="medication",
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return {"proposal": row_dict(proposal), **result}
