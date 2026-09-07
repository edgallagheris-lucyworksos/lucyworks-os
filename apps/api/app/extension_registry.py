from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Lifecycle = Literal["experimental", "pilot", "production", "disabled"]
AccessMode = Literal["read", "propose", "execute"]


@dataclass(frozen=True)
class ModuleManifest:
    module_id: str
    name: str
    version: str
    lifecycle: Lifecycle
    reads: tuple[str, ...] = ()
    mutates: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    subscribes: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    ui_routes: tuple[str, ...] = ()
    integrations: tuple[str, ...] = ()
    feature_flag: str | None = None


@dataclass(frozen=True)
class ConnectorManifest:
    connector_id: str
    name: str
    version: str
    supplier: str
    mode: AccessMode = "read"
    data_classes: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    purpose: str = ""
    enabled: bool = False


MODULES: dict[str, ModuleManifest] = {}
CONNECTORS: dict[str, ConnectorManifest] = {}


def register_module(manifest: ModuleManifest) -> ModuleManifest:
    if manifest.module_id in MODULES:
        raise ValueError(f"duplicate module_id: {manifest.module_id}")
    if manifest.mutates and not manifest.commands:
        raise ValueError("modules that mutate canonical state must declare commands")
    MODULES[manifest.module_id] = manifest
    return manifest


def register_connector(manifest: ConnectorManifest) -> ConnectorManifest:
    if manifest.connector_id in CONNECTORS:
        raise ValueError(f"duplicate connector_id: {manifest.connector_id}")
    if manifest.mode == "execute" and not manifest.allowed_actions:
        raise ValueError("execute connectors must declare allowed_actions")
    CONNECTORS[manifest.connector_id] = manifest
    return manifest


def module_catalogue() -> list[ModuleManifest]:
    return sorted(MODULES.values(), key=lambda item: item.module_id)


def connector_catalogue() -> list[ConnectorManifest]:
    return sorted(CONNECTORS.values(), key=lambda item: item.connector_id)


register_module(ModuleManifest(
    module_id="lucy.capture", name="LucyCapture", version="0.1.0", lifecycle="experimental",
    reads=("patient", "episode", "medication", "result"),
    mutates=(), commands=("clinical.propose_update",),
    emits=("clinical.draft_created",), subscribes=("patient.context_changed",),
    capabilities=("clinical.capture",), ui_routes=("/input",), feature_flag="LUCY_CAPTURE_ENABLED",
))
register_module(ModuleManifest(
    module_id="lucy.pharmacy", name="LucyPharmacy", version="0.1.0", lifecycle="experimental",
    reads=("patient", "episode", "medication", "resource"),
    mutates=("medication",), commands=("medication.prescribe", "medication.administer", "medication.discontinue"),
    emits=("medication.prescribed", "medication.administered", "medication.discontinued"),
    subscribes=("patient.weight_changed", "procedure.scheduled"),
    capabilities=("medication.manage",), feature_flag="LUCY_PHARMACY_ENABLED",
))
register_module(ModuleManifest(
    module_id="lucy.insurance", name="LucyInsurance", version="0.1.0", lifecycle="experimental",
    reads=("patient", "episode", "estimate", "financial_authority"),
    mutates=("financial_authority",), commands=("insurance.record_authority",),
    emits=("insurance.authority_changed",), subscribes=("estimate.changed", "estimate.threshold_crossed"),
    capabilities=("finance.authority",), feature_flag="LUCY_INSURANCE_ENABLED",
))
register_module(ModuleManifest(
    module_id="lucy.disruption", name="LucyDisruption", version="0.1.0", lifecycle="experimental",
    reads=("patient", "episode", "staff", "room", "resource", "work_item"),
    mutates=(), commands=("replan.propose",),
    emits=("replan.proposed",), subscribes=("emergency.declared", "surgery.overran", "staff.unavailable"),
    capabilities=("hospital.replan",), feature_flag="LUCY_DISRUPTION_ENABLED",
))
