from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

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


CAPABILITIES = [
    Capability(
        key="canonical_data",
        name="Canonical hospital data",
        state="partial",
        authority="episode, patient, staff, room and resource records",
        proof=["domain routes", "episode-state routes", "hospital operations routes"],
        blockers=["multiple versioned route families remain mounted", "canonical write ownership is not yet singular"],
    ),
    Capability(
        key="workflow_engine",
        name="Workflow engine",
        state="partial",
        authority="workflow actions and event-driven automation",
        proof=["workflow action routes", "event-driven automation v22"],
        blockers=["end-to-end admission-to-discharge contract is not yet proven by one test"],
    ),
    Capability(
        key="rules_and_permissions",
        name="Rules and permissions",
        state="partial",
        authority="verified identity, role scope and safety controls",
        proof=["verified identity middleware", "access-control routes", "safety-control v25"],
        blockers=["legacy test bypass exists", "role-specific approval matrix needs one canonical source"],
    ),
    Capability(
        key="resource_scheduler",
        name="Rota and resource scheduler",
        state="partial",
        authority="scheduler, conflict engine and day-control assignments",
        proof=["scheduler routes", "conflict engine routes", "day-control assignment routes"],
        blockers=["whole-hospital ripple effects are not yet proven transactionally"],
    ),
    Capability(
        key="event_propagation",
        name="Event propagation",
        state="partial",
        authority="event-driven automation and realtime routes",
        proof=["event-driven automation v22", "realtime routes"],
        blockers=["delivery guarantees and idempotency need explicit system-level proof"],
    ),
    Capability(
        key="command_surface",
        name="Single hospital command surface",
        state="partial",
        authority="hospital board and hospital command routes",
        proof=["/hospital-board", "hospital command routes", "master board v11"],
        blockers=["multiple command/readiness surfaces remain", "one board is not yet the sole operational entry point"],
    ),
    Capability(
        key="integrations",
        name="External integrations",
        state="partial",
        authority="integration routes and retry runtime",
        proof=["integration routes", "integration retry runtime"],
        blockers=["real PIMS, lab, imaging and finance connections require site credentials and acceptance tests"],
    ),
    Capability(
        key="system_proof",
        name="End-to-end system proof",
        state="missing",
        authority="one deterministic acceptance suite",
        proof=[],
        blockers=["no single test currently proves intake through discharge, billing evidence and audit trail"],
    ),
]


@router.get("/contract", response_model=CoreContract)
def get_core_contract() -> CoreContract:
    states = {capability.state for capability in CAPABILITIES}
    overall: CapabilityState = "missing" if states == {"missing"} else "partial"
    if states == {"ready"}:
        overall = "ready"

    return CoreContract(
        system="LucyWorks OS",
        contract_version="1.0.0",
        generated_at=datetime.now(timezone.utc),
        overall_state=overall,
        capabilities=CAPABILITIES,
        operating_rule=(
            "No module may claim ready until its canonical authority, user action path, "
            "audit evidence and automated acceptance test all pass."
        ),
    )
