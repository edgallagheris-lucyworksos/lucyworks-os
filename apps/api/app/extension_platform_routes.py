from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth import AuthContext, require_authenticated
from app.database import get_session
from app.extension_registry import connector_definition_catalogue, module_catalogue
from app.integration_agent_gateway import connectors_for_active_context, public_connector

router = APIRouter(prefix="/api/platform", tags=["extension-platform"])


@router.get("/modules")
def modules(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"modules": [asdict(item) for item in module_catalogue()]}


@router.get("/connector-definitions")
def connector_definitions(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"connectorDefinitions": [asdict(item) for item in connector_definition_catalogue()]}


@router.get("/connectors")
def connectors(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context, rows = connectors_for_active_context(session, auth)
    return {
        "scope": context.as_dict(),
        "connectors": [public_connector(item) for item in rows],
    }


@router.get("/extension-contract")
def extension_contract(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context, connectors = connectors_for_active_context(session, auth)
    return {
        "version": "1.1.0",
        "scope": context.as_dict(),
        "controls": [
            {
                "id": "registry-runtime-authority",
                "status": "enforced_and_tested",
                "implementation": "Disabled declarations cannot be executable; executable commands require resolvable handlers and acceptance-test references.",
            },
            {
                "id": "canonical-event-envelope",
                "status": "enforced_and_tested",
                "implementation": "Fact naming, site scope, durable V7 persistence, actor attribution and idempotency are enforced by the publisher.",
            },
            {
                "id": "connector-write-authority",
                "status": "enforced_and_tested",
                "implementation": "Runtime authority is persisted and site-scoped in V28; only declared reads in shadow or read_only mode are accepted.",
            },
            {
                "id": "external-write-back",
                "status": "unsupported",
                "implementation": "The extension gateway exposes no execute mode or caller-controlled write bypass.",
            },
            {
                "id": "canonical-state-and-ai-policy",
                "status": "declared_architecture_rule",
                "implementation": "Extensions and AI must use canonical command and evidence paths; this endpoint does not claim system-wide proof.",
            },
        ],
        "proof": "apps/api/extension_platform_smoke_test.py",
        "moduleCount": len(module_catalogue()),
        "connectorDefinitionCount": len(connector_definition_catalogue()),
        "siteConnectorCount": len(connectors),
    }
