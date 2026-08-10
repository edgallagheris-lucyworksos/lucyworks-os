from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import inspect

from app.database import engine

router = APIRouter(prefix="/api/core", tags=["LucyWorks Core"])

CapabilityState = Literal["ready", "partial", "missing"]


class Capability(BaseModel):
    key: str
    name: str
    state: CapabilityState
    authority: str
    proof: list[str]
    blockers: list[str]


class CoreContract(BaseModel):
    system: str
    contract_version: str
    generated_at: datetime
    overall_state: CapabilityState
    capabilities: list[Capability]
    operating_rule: str


def _mounted_paths(request: Request) -> set[str]:
    return {route.path for route in request.app.routes if getattr(route, "path", None)}


def _tables() -> set[str]:
    return set(inspect(engine).get_table_names())


def _coverage(required: set[str], present: set[str]) -> tuple[list[str], list[str]]:
    found = sorted(required & present)
    missing = sorted(required - present)
    return found, missing


def _state(found: list[str], missing: list[str], *, can_be_ready: bool = False) -> CapabilityState:
    if not found:
        return "missing"
    if not missing and can_be_ready:
        return "ready"
    return "partial"


@router.get("/contract", response_model=CoreContract)
def get_core_contract(request: Request) -> CoreContract:
    paths = _mounted_paths(request)
    tables = _tables()

    lifecycle_paths = {
        "/api/v9/referrals",
        "/api/v9/episodes/{episode_ref}/transition",
        "/api/v9/episodes/{episode_ref}/consents",
        "/api/v9/episodes/{episode_ref}/handovers",
        "/api/v9/episodes/{episode_ref}/closure",
        "/api/v9/episodes/{episode_ref}/command-view",
    }
    lifecycle_tables = {
        "canonicalepisodestate",
        "referralintakev9",
        "consentauthorisationv9",
        "episodehandoverv9",
        "episodetransitionv9",
        "episodeclosurev9",
    }
    scheduler_paths = {
        "/api/hospital-ops/board",
        "/api/day-control/conflicts",
        "/api/day-control/blocks/{block_id}",
    }
    integration_paths = {
        "/api/integrations/connections",
        "/api/v7/integration-retries",
    }

    lifecycle_route_proof, lifecycle_route_gaps = _coverage(lifecycle_paths, paths)
    lifecycle_table_proof, lifecycle_table_gaps = _coverage(lifecycle_tables, tables)
    scheduler_proof, scheduler_gaps = _coverage(scheduler_paths, paths)
    integration_proof, integration_gaps = _coverage(integration_paths, paths)

    lifecycle_blockers = [f"missing route: {path}" for path in lifecycle_route_gaps]
    lifecycle_blockers += [f"missing table: {table}" for table in lifecycle_table_gaps]
    if not lifecycle_blockers:
        lifecycle_blockers.append("proof is synthetic; no real hospital deployment acceptance has passed")

    capabilities = [
        Capability(
            key="canonical_data",
            name="Canonical hospital episode data",
            state=_state(lifecycle_table_proof, lifecycle_table_gaps),
            authority="CanonicalEpisodeState plus v9 referral, consent, handover, transition and closure records",
            proof=[f"table:{name}" for name in lifecycle_table_proof],
            blockers=[f"missing table: {name}" for name in lifecycle_table_gaps]
            or ["parallel legacy and versioned models remain mounted"],
        ),
        Capability(
            key="workflow_engine",
            name="Governed referral-to-closure workflow",
            state=_state(lifecycle_route_proof, lifecycle_route_gaps),
            authority="v9 hospital command transition guard",
            proof=[f"route:{name}" for name in lifecycle_route_proof]
            + ["test:hospital_command_v9_smoke_test.py"],
            blockers=lifecycle_blockers,
        ),
        Capability(
            key="rules_and_permissions",
            name="Identity, permissions and governed approvals",
            state="partial" if "/api/auth/dev-login" in paths else "missing",
            authority="verified identity middleware, role checks and checkpoint approvals",
            proof=["authenticated v9 lifecycle test", "blocked transition assertions", "stale-write rejection"],
            blockers=["development login and legacy-test bypass must remain impossible in production"],
        ),
        Capability(
            key="resource_scheduler",
            name="Rota and resource scheduler",
            state=_state(scheduler_proof, scheduler_gaps),
            authority="hospital operations board, conflict engine and day-control assignment routes",
            proof=[f"route:{name}" for name in scheduler_proof],
            blockers=[f"missing route: {name}" for name in scheduler_gaps]
            or ["lifecycle-to-schedule ripple effects are not covered by the v9 closure test"],
        ),
        Capability(
            key="event_propagation",
            name="Durable event propagation",
            state="partial" if "durableevent" in tables else "missing",
            authority="durable event and event-driven automation layers",
            proof=["table:durableevent"] if "durableevent" in tables else [],
            blockers=["delivery, retry and idempotency are not proven inside one referral-to-closure acceptance run"],
        ),
        Capability(
            key="command_surface",
            name="Hospital command surface",
            state="partial" if "/api/v9/episodes/{episode_ref}/command-view" in paths else "missing",
            authority="v9 command view and /hospital-board frontend",
            proof=["route:/api/v9/episodes/{episode_ref}/command-view"],
            blockers=["multiple command, readiness and legacy surfaces remain visible"],
        ),
        Capability(
            key="integrations",
            name="External integrations",
            state=_state(integration_proof, integration_gaps),
            authority="integration connection, envelope and retry services",
            proof=[f"route:{name}" for name in integration_proof],
            blockers=[f"missing route: {name}" for name in integration_gaps]
            or ["no live PIMS, laboratory, imaging or finance acceptance evidence"],
        ),
        Capability(
            key="system_proof",
            name="End-to-end system proof",
            state="partial" if not lifecycle_route_gaps and not lifecycle_table_gaps else "missing",
            authority="hospital_command_v9_smoke_test.py plus dedicated core acceptance CI",
            proof=(
                [
                    "referral creation and acceptance",
                    "guarded triage, consult and admission",
                    "consent and accountable handover",
                    "ward and discharge evidence gates",
                    "closure approval, stale-write rejection and final closed state",
                ]
                if not lifecycle_route_gaps and not lifecycle_table_gaps
                else []
            ),
            blockers=[
                "test uses synthetic SQLite data rather than a deployed hospital environment",
                "financial status is asserted but a real invoice/payment integration is not exercised",
                "frontend real-device workflow and cross-department user acceptance remain unproven",
            ],
        ),
    ]

    states = {capability.state for capability in capabilities}
    overall: CapabilityState = "missing" if states == {"missing"} else "partial"
    if states == {"ready"}:
        overall = "ready"

    return CoreContract(
        system="LucyWorksOS",
        contract_version="1.1.0",
        generated_at=datetime.now(timezone.utc),
        overall_state=overall,
        capabilities=capabilities,
        operating_rule=(
            "A capability may be called ready only when runtime authority, schema, governed user action, "
            "audit evidence, automated acceptance and real-site validation all pass."
        ),
    )
