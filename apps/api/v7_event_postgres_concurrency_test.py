from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func
from sqlmodel import Session, select

from app.database import engine
from app.v7_event_service import publish_event
from app.v7_models import DurableEvent


with Session(engine) as session:
    initial = int(session.exec(select(func.max(DurableEvent.sequence))).one() or 0)

workers = 20
barrier = Barrier(workers)


def create(index: int):
    with Session(engine) as session:
        barrier.wait(timeout=20)
        row = publish_event(
            session,
            event_type="postgres_concurrency_test",
            aggregate_type="concurrency",
            aggregate_ref=f"event-{index}",
            payload={"index": index},
            idempotency_key=f"postgres-event-concurrency-{index}",
        )
        session.commit()
        session.refresh(row)
        return row.event_ref, row.sequence


with ThreadPoolExecutor(max_workers=workers) as executor:
    results = list(executor.map(create, range(workers)))

sequences = sorted(sequence for _, sequence in results)
assert len(set(sequences)) == workers, results
assert sequences == list(range(initial + 1, initial + workers + 1)), (initial, sequences)

same_barrier = Barrier(2)


def create_same(_index: int):
    with Session(engine) as session:
        same_barrier.wait(timeout=20)
        row = publish_event(
            session,
            event_type="postgres_idempotency_test",
            aggregate_type="concurrency",
            aggregate_ref="same-event",
            payload={"same": True},
            idempotency_key="postgres-event-same-idempotency",
        )
        session.commit()
        session.refresh(row)
        return row.event_ref, row.sequence


with ThreadPoolExecutor(max_workers=2) as executor:
    same_results = list(executor.map(create_same, range(2)))

assert same_results[0] == same_results[1], same_results
with Session(engine) as session:
    rows = session.exec(select(DurableEvent).where(DurableEvent.idempotency_key == "postgres-event-same-idempotency")).all()
    assert len(rows) == 1, rows

print("PostgreSQL durable event sequence and idempotency concurrency passed", {"workers": workers, "range": [sequences[0], sequences[-1]], "same": same_results[0]})
