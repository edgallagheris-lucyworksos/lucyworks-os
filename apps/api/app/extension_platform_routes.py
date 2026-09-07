from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends

from app.auth import AuthContext, require_authenticated
from app.extension_registry import connector_catalogue, module_catalogue
from app.integration_agent_gateway import public_connector

router = APIRouter(prefix="/api/platform", tags=["extension-platform"])


@router.get("/modules")
def modules(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"modules": [asdict(item) for item in module_catalogue()]}


@router.get("/connectors")
def connectors(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {"connectors": [public_connector(item) for item in connector_catalogue()]}


@router.get("/extension-contract")
def extension_contract(auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "rules": {
            "canonicalStateOnly": True,
            "commandsForMutation": True,
            "eventsAreFacts": True,
            "aiDirectWrites": False,
            "externalWriteDefault": False,
            "purposeScopedConnectors": True,
            "consequentialActionsRequireEvidence": True,
        },
        "moduleCount": len(module_catalogue()),
        "connectorCount": len(connector_catalogue()),
    }
