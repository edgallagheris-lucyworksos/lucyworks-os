from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.catalogue_models import (
    AssignmentImportRecord,
    CatalogueImportRun,
    DiagnosticCatalogueItem,
    FormularyCatalogueItem,
    ProcedureCatalogueItem,
)
from app.database import get_session
from app.models import AuditEvent, ProcedureType, StockItem

router = APIRouter()


class ProcedureRow(BaseModel):
    code: str
    name: str
    specialty: str
    duration_est_minutes: int = 0
    kit_list: str = ""
    staffing_requirements: str = ""
    risks: str = ""
    SOP_link: str = ""


class FormularyRow(BaseModel):
    drug_id: str
    name: str
    species_allowed: str = ""
    dose_ranges: str = ""
    routes: str = ""
    interactions: str = ""
    CD_schedule: str = "None"
    storage: str = ""


class DiagnosticRow(BaseModel):
    test_code: str
    name: str
    species: str = ""
    method: str = ""
    ref_range_low: float | None = None
    ref_range_high: float | None = None
    auto_flag_rules: str = ""


class AssignmentRow(BaseModel):
    date: str = ""
    case_id: str = ""
    species: str = ""
    procedure_type: str = ""
    priority: str = ""
    triage_score: str = ""
    assigned_vet_id: str = ""
    assigned_nurse_id: str = ""
    rota_risk: str = ""
    safeguarding_path: str = ""


class CataloguePayload(BaseModel):
    procedures: list[ProcedureRow] = []
    formulary: list[FormularyRow] = []
    diagnostics: list[DiagnosticRow] = []
    assignments: list[AssignmentRow] = []
    actor_name: str = "System"


def audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
    session.commit()


def bool_from_text(value: str, needle: str) -> bool:
    return needle.lower() in (value or "").lower()


def upsert_procedure(session: Session, row: ProcedureRow) -> ProcedureCatalogueItem:
    item = session.exec(select(ProcedureCatalogueItem).where(ProcedureCatalogueItem.code == row.code)).first()
    if not item:
        item = ProcedureCatalogueItem(code=row.code, name=row.name, specialty=row.specialty)
    item.name = row.name
    item.specialty = row.specialty
    item.duration_est_minutes = row.duration_est_minutes
    item.kit_list = row.kit_list
    item.staffing_requirements = row.staffing_requirements
    item.risks = row.risks
    item.sop_link = row.SOP_link
    session.add(item)

    existing_type = session.exec(select(ProcedureType).where(ProcedureType.name == row.name)).first()
    if not existing_type:
        room_type = "theatre"
        if row.specialty.lower() in {"ecc"}:
            room_type = "resus"
        if row.specialty.lower() in {"ophtho", "dental", "exotics"}:
            room_type = "theatre"
        session.add(ProcedureType(
            name=row.name,
            department=row.specialty,
            default_duration_min=row.duration_est_minutes,
            prep_min=15,
            anaesthesia_min=15 if row.specialty.lower() not in {"ecc"} else 0,
            recovery_min=30,
            cleaning_min=15,
            required_role="clinician",
            required_room_type=room_type,
        ))
    return item


def upsert_formulary(session: Session, row: FormularyRow) -> FormularyCatalogueItem:
    item = session.exec(select(FormularyCatalogueItem).where(FormularyCatalogueItem.drug_id == row.drug_id)).first()
    if not item:
        item = FormularyCatalogueItem(drug_id=row.drug_id, name=row.name)
    item.name = row.name
    item.species_allowed = row.species_allowed
    item.dose_ranges = row.dose_ranges
    item.routes = row.routes
    item.interactions = row.interactions
    item.cd_schedule = row.CD_schedule or "None"
    item.storage = row.storage
    item.restricted_flag = item.cd_schedule.lower() not in {"", "none", "nan"}
    item.cold_chain_flag = bool_from_text(row.storage, "refrigerate") or bool_from_text(row.storage, "cold")
    item.locked_storage_flag = bool_from_text(row.storage, "locked") or item.restricted_flag
    session.add(item)

    existing_stock = session.exec(select(StockItem).where(StockItem.name == row.name)).first()
    if not existing_stock:
        session.add(StockItem(
            name=row.name,
            category="controlled_or_restricted" if item.restricted_flag else "formulary",
            location="Controlled Drug Cabinet" if item.locked_storage_flag else "Cold Chain Fridge" if item.cold_chain_flag else "Pharmacy",
            current_quantity=0,
            reorder_threshold=1,
            authorised_supplier="authorised veterinary wholesaler",
            compliance_note="Formulary import; clinical decisions remain with licensed veterinary professionals.",
        ))
    return item


def upsert_diagnostic(session: Session, row: DiagnosticRow) -> DiagnosticCatalogueItem:
    item = session.exec(select(DiagnosticCatalogueItem).where(DiagnosticCatalogueItem.test_code == row.test_code)).first()
    if not item:
        item = DiagnosticCatalogueItem(test_code=row.test_code, name=row.name)
    item.name = row.name
    item.species = row.species
    item.method = row.method
    item.ref_range_low = row.ref_range_low
    item.ref_range_high = row.ref_range_high
    item.auto_flag_rules = row.auto_flag_rules
    session.add(item)
    return item


def add_assignment(session: Session, row: AssignmentRow) -> AssignmentImportRecord:
    item = AssignmentImportRecord(**row.model_dump())
    session.add(item)
    return item


@router.post("/api/catalogues/import")
def import_catalogues(payload: CataloguePayload, session: Session = Depends(get_session)):
    counts = {"procedures": 0, "formulary": 0, "diagnostics": 0, "assignments": 0}
    for row in payload.procedures:
        upsert_procedure(session, row)
        counts["procedures"] += 1
    for row in payload.formulary:
        upsert_formulary(session, row)
        counts["formulary"] += 1
    for row in payload.diagnostics:
        upsert_diagnostic(session, row)
        counts["diagnostics"] += 1
    for row in payload.assignments:
        add_assignment(session, row)
        counts["assignments"] += 1
    total = sum(counts.values())
    run = CatalogueImportRun(source_name="api_payload", row_count=total, imported_count=total, notes=str(counts))
    session.add(run)
    session.commit()
    session.refresh(run)
    audit(session, payload.actor_name, "imported", "catalogue_import", run.id or 0, f"Imported catalogues {counts}")
    return {"ok": True, "counts": counts, "run": run}


@router.get("/api/catalogues")
def get_catalogues(session: Session = Depends(get_session)):
    procedures = session.exec(select(ProcedureCatalogueItem).where(ProcedureCatalogueItem.active == True).order_by(ProcedureCatalogueItem.specialty, ProcedureCatalogueItem.name)).all()
    formulary = session.exec(select(FormularyCatalogueItem).where(FormularyCatalogueItem.active == True).order_by(FormularyCatalogueItem.name)).all()
    diagnostics = session.exec(select(DiagnosticCatalogueItem).where(DiagnosticCatalogueItem.active == True).order_by(DiagnosticCatalogueItem.method, DiagnosticCatalogueItem.name)).all()
    assignments = session.exec(select(AssignmentImportRecord).order_by(AssignmentImportRecord.imported_at.desc())).all()
    return {
        "summary": {
            "procedures": len(procedures),
            "formulary": len(formulary),
            "diagnostics": len(diagnostics),
            "assignments": len(assignments),
            "restricted_formulary": len([x for x in formulary if x.restricted_flag]),
            "cold_chain": len([x for x in formulary if x.cold_chain_flag]),
        },
        "procedures": procedures,
        "formulary": formulary,
        "diagnostics": diagnostics,
        "assignments": assignments,
    }


@router.get("/api/catalogues/procedures")
def get_procedure_catalogue(session: Session = Depends(get_session)):
    return session.exec(select(ProcedureCatalogueItem).where(ProcedureCatalogueItem.active == True).order_by(ProcedureCatalogueItem.specialty, ProcedureCatalogueItem.name)).all()


@router.get("/api/catalogues/formulary")
def get_formulary_catalogue(session: Session = Depends(get_session)):
    return session.exec(select(FormularyCatalogueItem).where(FormularyCatalogueItem.active == True).order_by(FormularyCatalogueItem.name)).all()


@router.get("/api/catalogues/diagnostics")
def get_diagnostic_catalogue(session: Session = Depends(get_session)):
    return session.exec(select(DiagnosticCatalogueItem).where(DiagnosticCatalogueItem.active == True).order_by(DiagnosticCatalogueItem.method, DiagnosticCatalogueItem.name)).all()


@router.get("/api/catalogues/import-runs")
def get_import_runs(session: Session = Depends(get_session)):
    return session.exec(select(CatalogueImportRun).order_by(CatalogueImportRun.imported_at.desc())).all()
