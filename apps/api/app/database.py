from collections.abc import Generator
import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine


def _normalise_database_url(value: str) -> str:
    value = value.strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://") and "+" not in value.split("://", 1)[0]:
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


DATABASE_URL = _normalise_database_url(os.getenv("DATABASE_URL", "sqlite:///./lucyworks.db"))
IS_SQLITE = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() in {"1", "true", "yes"},
    connect_args=connect_args,
    pool_pre_ping=not IS_SQLITE,
)

SCHEDULE_STATE_COLUMNS = {
    "consent_status": "VARCHAR",
    "estimate_status": "VARCHAR",
    "insurance_status": "VARCHAR",
    "pharmacy_ready": "BOOLEAN",
    "owner_updated": "BOOLEAN",
    "referring_vet_report_sent": "BOOLEAN",
    "discharge_clear": "BOOLEAN",
}

# Temporary compatibility for old local SQLite files. Production databases are
# migrated with Alembic and never altered through this map.
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


def _truthy(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _ensure_sqlite_columns() -> None:
    if not IS_SQLITE:
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
    auto_create = _truthy("AUTO_CREATE_SCHEMA", IS_SQLITE)
    if auto_create:
        SQLModel.metadata.create_all(engine)
        _ensure_sqlite_columns()
        return

    # Production schema creation is intentionally disabled. This catches a
    # deployment that forgot `alembic upgrade head` before serving traffic.
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        raise RuntimeError("database is not migrated; run 'alembic upgrade head' before starting LucyWorks")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
