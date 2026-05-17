from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProcedureCatalogueItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)
    name: str
    specialty: str
    duration_est_minutes: int = 0
    kit_list: str = ""
    staffing_requirements: str = ""
    risks: str = ""
    sop_link: str = ""
    active: bool = True
    imported_at: datetime = Field(default_factory=utc_now)


class FormularyCatalogueItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    drug_id: str = Field(index=True)
    name: str
    species_allowed: str = ""
    dose_ranges: str = ""
    routes: str = ""
    interactions: str = ""
    cd_schedule: str = "None"
    storage: str = ""
    restricted_flag: bool = False
    cold_chain_flag: bool = False
    locked_storage_flag: bool = False
    active: bool = True
    imported_at: datetime = Field(default_factory=utc_now)


class DiagnosticCatalogueItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    test_code: str = Field(index=True)
    name: str
    species: str = ""
    method: str = ""
    ref_range_low: Optional[float] = None
    ref_range_high: Optional[float] = None
    auto_flag_rules: str = ""
    active: bool = True
    imported_at: datetime = Field(default_factory=utc_now)


class AssignmentImportRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
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
    imported_at: datetime = Field(default_factory=utc_now)


class CatalogueImportRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str
    row_count: int = 0
    imported_count: int = 0
    status: str = "completed"
    notes: str = ""
    imported_at: datetime = Field(default_factory=utc_now)
