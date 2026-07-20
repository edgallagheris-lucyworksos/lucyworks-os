from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext
from app.database import engine
from app import hospital_ops_runtime_patch as _runtime_patch  # noqa: F401
from app import hospital_ops_service as service
from app.hospital_ops_models import OperationalBlock


auth = AuthContext(
    subject="concurrency-test-ops",
    actor_id="concurrency-test-ops",
    actor_name="Concurrency Test Ops",
    role="ops_manager",
    auth_source="ci_verified_identity",
    verified=True,
)

with Session(engine) as session:
    service.ensure_default_premises_and_areas(session, "concurrency-premises")
    service.create_block(
        session,
        {
            "blockRef": "concurrency-block",
            "premisesRef": "concurrency-premises",
            "patientName": "Concurrency Patient",
            "procedureName": "MRI",
            "blockType": "imaging",
            "areaRef": "mri",
            "startsAt": datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc),
            "endsAt": datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
            "gates": {"consent": "approved", "estimate": "approved", "pharmacy": "ready"},
            "idempotencyKey": "concurrency-block-create",
        },
        auth,
    )
    session.commit()

barrier = Barrier(2)


def competing_update(label: str, start_hour: int):
    with Session(engine) as session:
        barrier.wait(timeout=10)
        try:
            row, command = service.patch_block(
                session,
                "concurrency-block",
                {
                    "expectedVersion": 1,
                    "commandType": "ConcurrentMoveTest",
                    "action": f"concurrent update {label}",
                    "startsAt": datetime(2026, 7, 20, start_hour, 0, tzinfo=timezone.utc),
                    "endsAt": datetime(2026, 7, 20, start_hour + 1, 0, tzinfo=timezone.utc),
                    "reason": "PostgreSQL row-lock concurrency test",
                    "idempotencyKey": f"concurrency-update-{label}",
                },
                auth,
            )
            session.commit()
            return {"status": "success", "version": row.version, "commandRef": command.command_ref}
        except HTTPException as exc:
            session.rollback()
            return {"status": "http_error", "code": exc.status_code, "detail": exc.detail}


with ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(lambda args: competing_update(*args), [("a", 10), ("b", 11)]))

successes = [result for result in results if result["status"] == "success"]
stale = [result for result in results if result.get("code") == 409 and isinstance(result.get("detail"), dict) and result["detail"].get("code") == "stale_version"]
assert len(successes) == 1, results
assert len(stale) == 1, results
assert successes[0]["version"] == 2, results

with Session(engine) as session:
    final = session.exec(select(OperationalBlock).where(OperationalBlock.block_ref == "concurrency-block")).one()
    assert final.version == 2, final
    assert final.last_command_ref == successes[0]["commandRef"], final

print("PostgreSQL row-lock concurrency test passed", results)
