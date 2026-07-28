from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlmodel import Session, select

from app.clinical_execution_models import ClinicalObservation
from app.control_plane_models import CriticalResultAcknowledgement
from app.database import engine
from app.event_driven_automation_v22_models import AutomationRuntimeConfigV22
from app.event_driven_automation_v22_service import dispatch_source, scan_and_dispatch
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock

logger = logging.getLogger("lucyworks.automation.v22")
_PENDING_KEY = "lucyworks_v22_automation_sources"
_LISTENERS_INSTALLED = False
_BACKGROUND_TASK: asyncio.Task[Any] | None = None
_STOP_EVENT: asyncio.Event | None = None
_LAST_SCAN: dict[str, float] = {}


def _source_identity(value: Any) -> tuple[str, str] | None:
    if isinstance(value, ClinicalObservation) and value.observation_ref:
        return "observation", value.observation_ref
    if isinstance(value, CriticalResultAcknowledgement) and value.result_ref:
        return "critical_result", value.result_ref
    if isinstance(value, CanonicalEpisodeState) and value.episode_ref:
        return "evidence_gap", value.episode_ref
    if isinstance(value, OperationalBlock) and value.block_ref:
        return "operational_delay", value.block_ref
    return None


def _capture_sources(session: SQLAlchemySession, _flush_context: Any) -> None:
    pending = session.info.setdefault(_PENDING_KEY, set())
    for value in list(session.new) + list(session.dirty):
        identity = _source_identity(value)
        if identity:
            pending.add(identity)


def _clear_sources(session: SQLAlchemySession) -> None:
    session.info.pop(_PENDING_KEY, None)


def _dispatch_after_commit(session: SQLAlchemySession) -> None:
    pending = list(session.info.pop(_PENDING_KEY, set()))
    if not pending:
        return
    for source_type, source_ref in pending:
        try:
            dispatch_source(source_type, source_ref)
        except Exception:
            # The source transaction has already committed. Automation failure must
            # never unwind or corrupt that clinical or operational source write.
            logger.exception(
                "v22 automation dispatch failed after source commit",
                extra={"source_type": source_type, "source_ref": source_ref},
            )


def install_session_listeners() -> None:
    global _LISTENERS_INSTALLED
    if _LISTENERS_INSTALLED:
        return
    event.listen(SQLAlchemySession, "after_flush", _capture_sources)
    event.listen(SQLAlchemySession, "after_commit", _dispatch_after_commit)
    event.listen(SQLAlchemySession, "after_rollback", _clear_sources)
    _LISTENERS_INSTALLED = True


def run_background_scan_once() -> int:
    now = time.monotonic()
    with Session(engine) as session:
        rows = session.exec(
            select(AutomationRuntimeConfigV22).where(
                AutomationRuntimeConfigV22.background_scan_enabled == True  # noqa: E712
            )
        ).all()
        configs = [
            {
                "premisesRef": row.premises_ref,
                "mode": row.mode,
                "interval": max(30, row.scan_interval_seconds),
            }
            for row in rows
            if row.mode != "disabled"
        ]

    processed = 0
    for config in configs:
        premises_ref = config["premisesRef"]
        last = _LAST_SCAN.get(premises_ref, 0.0)
        if now - last < config["interval"]:
            continue
        _LAST_SCAN[premises_ref] = now
        try:
            rows = scan_and_dispatch(
                premises_ref=premises_ref,
                operational_date=date.today(),
                source_types={"critical_result", "operational_delay"},
            )
            processed += len(rows)
        except Exception:
            logger.exception(
                "v22 background automation scan failed",
                extra={"premises_ref": premises_ref},
            )
    return processed


async def _background_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(run_background_scan_once)
        except Exception:
            logger.exception("v22 background automation loop failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pass


def install_event_driven_automation_v22(app: Any) -> None:
    install_session_listeners()

    @app.on_event("startup")
    async def start_event_driven_automation_v22() -> None:
        global _BACKGROUND_TASK, _STOP_EVENT
        if _BACKGROUND_TASK and not _BACKGROUND_TASK.done():
            return
        _STOP_EVENT = asyncio.Event()
        _BACKGROUND_TASK = asyncio.create_task(_background_loop(_STOP_EVENT))

    @app.on_event("shutdown")
    async def stop_event_driven_automation_v22() -> None:
        global _BACKGROUND_TASK, _STOP_EVENT
        if _STOP_EVENT:
            _STOP_EVENT.set()
        if _BACKGROUND_TASK:
            try:
                await asyncio.wait_for(_BACKGROUND_TASK, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                _BACKGROUND_TASK.cancel()
        _BACKGROUND_TASK = None
        _STOP_EVENT = None
