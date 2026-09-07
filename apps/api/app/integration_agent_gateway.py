from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from app.extension_registry import CONNECTORS, ConnectorManifest, register_connector


def ensure_connector(
    connector_id: str,
    *,
    name: str,
    supplier: str,
    version: str = "0.1.0",
    data_classes: tuple[str, ...] = (),
    purpose: str,
) -> ConnectorManifest:
    existing = CONNECTORS.get(connector_id)
    if existing:
        return existing
    return register_connector(ConnectorManifest(
        connector_id=connector_id,
        name=name,
        version=version,
        supplier=supplier,
        mode="read",
        data_classes=data_classes,
        allowed_actions=(),
        purpose=purpose,
        enabled=False,
    ))


def authorise_gateway_call(connector_id: str, *, action: str, write: bool = False) -> ConnectorManifest:
    connector = CONNECTORS.get(connector_id)
    if not connector or not connector.enabled:
        raise HTTPException(status_code=403, detail="connector is not approved and enabled")
    if write:
        if connector.mode != "execute" or action not in connector.allowed_actions:
            raise HTTPException(status_code=403, detail="connector has no authority to execute this action")
    return connector


def public_connector(manifest: ConnectorManifest) -> dict[str, Any]:
    data = asdict(manifest)
    data["writeAllowed"] = manifest.mode == "execute"
    return data


ensure_connector(
    "pims.generic.read",
    name="Generic PIMS read adapter",
    supplier="LucyWorks",
    data_classes=("patient", "episode", "appointment", "clinical_record"),
    purpose="Read authorised source-system data into canonical hospital context.",
)
ensure_connector(
    "pacs.dicom.read",
    name="PACS/DICOM read adapter",
    supplier="LucyWorks",
    data_classes=("diagnostic_order", "study", "result"),
    purpose="Resolve authorised imaging studies and reports without exposing PACS internals.",
)
