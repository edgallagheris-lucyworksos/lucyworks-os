from collections.abc import Generator
import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lucyworks.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

SCHEDULE_STATE_COLUMNS = {
    "consent_status": "VARCHAR",
    "estimate_status": "VARCHAR",
    "insurance_status": "VARCHAR",
    "pharmacy_ready": "BOOLEAN",
    "owner_updated": "BOOLEAN",
    "referring_vet_report_sent": "BOOLEAN",
    "discharge_clear": "BOOLEAN",
}

# Lightweight compatibility migration for the current SQLite development
# database. Production deployments should use a formal migration tool before
# switching to PostgreSQL.
SQLITE_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "schedulestateblock": SCHEDULE_STATE_COLUMNS,
    "evidenceevent": {
        "correlation_id": "VARCHAR",
        "causation_event_ref": "VARCHAR",
        "idempotency_key": "VARCHAR",
        "request_id": "VARCHAR",
        "entity_type": "VARCHAR",
        "entity_id": "VARCHAR",
        "actor_auth_source": "VARCHAR DEFAULT 'unverified'",
        "human_review_completed_at": "DATETIME",
        "source_system": "VARCHAR DEFAULT 'lucyworks-os'",
        "source_record_ref": "VARCHAR",
        "payload_schema_version": "INTEGER DEFAULT 2",
        "previous_event_hash": "VARCHAR",
        "event_hash": "VARCHAR",
        "occurred_at": "DATETIME",
    },
    "estimateversion": {
        "supersedes_version": "INTEGER",
        "idempotency_key": "VARCHAR",
        "approved_ceiling": "FLOAT",
        "change_reason": "VARCHAR",
        "client_contact_method": "VARCHAR",
        "client_contact_attempted_at": "DATETIME",
        "evidence_event_ref": "VARCHAR",
    },
    "consentrecord": {
        "version": "INTEGER DEFAULT 1",
        "supersedes_consent_ref": "VARCHAR",
        "idempotency_key": "VARCHAR",
        "client_contact_method": "VARCHAR",
        "communication_notes": "VARCHAR",
        "withdrawn_at": "DATETIME",
    },
}


def _ensure_sqlite_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, required_columns in SQLITE_COLUMN_MIGRATIONS.items():
            if table_name not in table_names:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for name, column_type in required_columns.items():
                if name in existing:
                    continue
                connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {column_type}'))


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_sqlite_columns()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
