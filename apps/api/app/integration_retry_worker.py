from __future__ import annotations

import logging
import os
import signal
import time
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.database import engine
from app.v7_integration_retry_routes import process_job
from app.v7_models import IntegrationRetryJob

logger = logging.getLogger("lucyworks.integration_retry_worker")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

STOP = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stop_worker(_signum, _frame) -> None:
    global STOP
    STOP = True


def claim_due_jobs(session: Session, limit: int) -> list[IntegrationRetryJob]:
    query = (
        select(IntegrationRetryJob)
        .where(IntegrationRetryJob.status == "queued")
        .where(IntegrationRetryJob.next_attempt_at <= utc_now())
        .order_by(IntegrationRetryJob.next_attempt_at, IntegrationRetryJob.id)
        .limit(limit)
    )
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    return list(session.exec(query).all())


def process_batch(limit: int) -> int:
    with Session(engine) as session:
        jobs = claim_due_jobs(session, limit)
        for job in jobs:
            process_job(session, job)
        session.commit()
        return len(jobs)


def main() -> None:
    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    interval = max(1.0, float(os.getenv("INTEGRATION_RETRY_POLL_SECONDS", "5")))
    batch_size = max(1, min(100, int(os.getenv("INTEGRATION_RETRY_BATCH_SIZE", "20"))))
    logger.info("integration retry worker started interval=%ss batch=%s", interval, batch_size)
    while not STOP:
        try:
            processed = process_batch(batch_size)
            if processed:
                logger.info("processed %s due integration retry jobs", processed)
                continue
        except Exception:
            logger.exception("integration retry worker batch failed")
        time.sleep(interval)
    logger.info("integration retry worker stopped")


if __name__ == "__main__":
    main()
