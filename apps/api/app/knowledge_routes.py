from fastapi import APIRouter

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

SOURCES = [
    {"id": "hospital-sop", "module": "all", "type": "internal_operating_rules"},
    {"id": "governance-guidance", "module": "LucyGov", "type": "governance_reference"},
    {"id": "business-training", "module": "LucyStrategy", "type": "business_process_notes"},
    {"id": "logistics-examples", "module": "LucyOps", "type": "operations_examples"},
]

AGENTS = [
    {"id": "lucy-ops-agent", "module": "LucyOps", "purpose": "resources_theatres_beds_stock"},
    {"id": "lucy-flow-agent", "module": "LucyFlow", "purpose": "patient_movement_blockers_handover"},
    {"id": "lucy-hr-agent", "module": "LucyHR", "purpose": "rota_fatigue_cover"},
    {"id": "lucy-comms-agent", "module": "LucyComms", "purpose": "owner_updates_estimates_insurance"},
    {"id": "lucy-gov-agent", "module": "LucyGov", "purpose": "audit_safety_approval"},
]


@router.get("/sources")
def list_sources():
    return {"sources": SOURCES}


@router.get("/agents")
def list_agents():
    return {"agents": AGENTS}


@router.get("/registry")
def registry():
    return {"sources": SOURCES, "agents": AGENTS}
