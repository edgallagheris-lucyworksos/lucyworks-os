from collections.abc import Generator
import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lucyworks.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

GOVERNANCE_COLUMNS = {
    "consent_status": "VARCHAR",
    "estimate_status": "VARCHAR",
    "insurance_status": "VARCHAR",
    "pharmacy_ready": "BOOLEAN",
    "owner_updated": "BOOLEAN",
    "referring_vet_report_sent": "BOOLEAN",
    "discharge_clear": "BOOLEAN",
}


def _ensure_schedule_state_governance_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "schedulestateblock" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("schedulestateblock")}
    missing = [(name, column_type) for name, column_type in GOVERNANCE_COLUMNS.items() if name not in existing]
    if not missing:
        return
    with engine.begin() as connection:
        for name, column_type in missing:
            connection.execute(text(f"ALTER TABLE schedulestateblock ADD COLUMN {name} {column_type}"))


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_schedule_state_governance_columns()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
