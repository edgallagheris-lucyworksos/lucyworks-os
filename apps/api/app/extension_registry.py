from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Literal

Lifecycle = Literal["experimental", "pilot", "production", "disabled"]
ConnectorMode = Literal["shadow", "read_only"]


@dataclass(frozen=True)
class CommandHandler:
    command_id: str
    handler_ref: str


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
    executable: bool = False
    command_handlers: tuple[CommandHandler, ...] = ()
    acceptance_tests: tuple[str, ...] = ()
    activation_blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorDefinition:
    definition_id: str
    connector_type: str
    name: str
    version: str
    supplier: str
    data_classes: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    purpose: str
    supported_modes: tuple[ConnectorMode, ...] = ("shadow", "read_only")
    external_write_supported: bool = False


MODULES: dict[str, ModuleManifest] = {}
CONNECTOR_DEFINITIONS: dict[str, ConnectorDefinition] = {}


def _resolve_handler(handler_ref: str) -> None:
    module_name, separator, attribute_path = handler_ref.partition(":")
    if not separator or not module_name or not attribute_path:
        raise ValueError(f"invalid command handler reference: {handler_ref}")
    try:
        target = import_module(module_name)
        for attribute in attribute_path.split("."):
            target = getattr(target, attribute)
    except (AttributeError, ImportError) as exc:
        raise ValueError(f"command handler does not resolve: {handler_ref}") from exc
    if not callable(target):
        raise ValueError(f"command handler is not callable: {handler_ref}")


def register_module(manifest: ModuleManifest) -> ModuleManifest:
    if manifest.module_id in MODULES:
        raise ValueError(f"duplicate module_id: {manifest.module_id}")
    if manifest.mutates and not manifest.commands:
        raise ValueError("modules that mutate canonical state must declare commands")
    if manifest.lifecycle in {"pilot", "production"} and not manifest.executable:
        raise ValueError("pilot and production modules must be executable")
    if manifest.lifecycle == "disabled" and manifest.executable:
        raise ValueError("disabled modules cannot be executable")
    if not manifest.executable and manifest.command_handlers:
        raise ValueError("non-executable modules cannot register command handlers")
    if manifest.executable:
        handlers = {item.command_id: item.handler_ref for item in manifest.command_handlers}
        if len(handlers) != len(manifest.command_handlers):
            raise ValueError("command handlers must have unique command IDs")
        if set(handlers) != set(manifest.commands):
            raise ValueError("every declared command must have exactly one registered handler")
        if not manifest.acceptance_tests:
            raise ValueError("executable modules must declare acceptance tests")
        for handler_ref in handlers.values():
            _resolve_handler(handler_ref)
    MODULES[manifest.module_id] = manifest
    return manifest


def register_connector_definition(definition: ConnectorDefinition) -> ConnectorDefinition:
    if definition.definition_id in CONNECTOR_DEFINITIONS:
        raise ValueError(f"duplicate connector definition: {definition.definition_id}")
    if any(item.connector_type == definition.connector_type for item in CONNECTOR_DEFINITIONS.values()):
        raise ValueError(f"duplicate connector type: {definition.connector_type}")
    if definition.external_write_supported:
        raise ValueError("the extension gateway does not support external write-back")
    if not definition.supported_modes or not set(definition.supported_modes) <= {"shadow", "read_only"}:
        raise ValueError("connector definitions may support shadow and read_only modes only")
    if not definition.allowed_actions or any(not action.endswith(".read") for action in definition.allowed_actions):
        raise ValueError("connector definitions may declare read actions only")
    CONNECTOR_DEFINITIONS[definition.definition_id] = definition
    return definition


def module_catalogue() -> list[ModuleManifest]:
    return sorted(MODULES.values(), key=lambda item: item.module_id)


def connector_definition_catalogue() -> list[ConnectorDefinition]:
    return sorted(CONNECTOR_DEFINITIONS.values(), key=lambda item: item.definition_id)


def connector_definition_for_type(connector_type: str) -> ConnectorDefinition | None:
    return next(
        (item for item in CONNECTOR_DEFINITIONS.values() if item.connector_type == connector_type),
        None,
    )


register_module(ModuleManifest(
    module_id="lucy.capture", name="Clinical capture extension", version="0.1.0", lifecycle="disabled",
    reads=("patient", "episode", "medication", "result"),
    mutates=(), commands=("clinical.propose_update",),
    emits=("clinical.draft_created",), subscribes=("patient.context_changed",),
    capabilities=("clinical.capture",), ui_routes=("/input",), feature_flag="LUCY_CAPTURE_ENABLED",
    activation_blockers=("No canonical command handler is registered.", "No end-to-end acceptance proof is registered."),
))
register_module(ModuleManifest(
    module_id="lucy.pharmacy", name="Pharmacy workflow extension", version="0.1.0", lifecycle="disabled",
    reads=("patient", "episode", "medication", "resource"),
    mutates=("medication",), commands=("medication.prescribe", "medication.administer", "medication.discontinue"),
    emits=("medication.prescribed", "medication.administered", "medication.discontinued"),
    subscribes=("patient.weight_changed", "procedure.scheduled"),
    capabilities=("medication.manage",), feature_flag="LUCY_PHARMACY_ENABLED",
    activation_blockers=("No canonical command handlers are registered.", "No end-to-end acceptance proof is registered."),
))
register_module(ModuleManifest(
    module_id="lucy.insurance", name="Insurance authority extension", version="0.1.0", lifecycle="disabled",
    reads=("patient", "episode", "estimate", "financial_authority"),
    mutates=("financial_authority",), commands=("insurance.record_authority",),
    emits=("insurance.authority_changed",), subscribes=("estimate.changed", "estimate.threshold_crossed"),
    capabilities=("finance.authority",), feature_flag="LUCY_INSURANCE_ENABLED",
    activation_blockers=("No canonical command handler is registered.", "No end-to-end acceptance proof is registered."),
))
register_module(ModuleManifest(
    module_id="lucy.disruption", name="Disruption planning extension", version="0.1.0", lifecycle="disabled",
    reads=("patient", "episode", "staff", "room", "resource", "work_item"),
    mutates=(), commands=("replan.propose",),
    emits=("replan.proposed",), subscribes=("emergency.declared", "surgery.overran", "staff.unavailable"),
    capabilities=("hospital.replan",), feature_flag="LUCY_DISRUPTION_ENABLED",
    activation_blockers=("No canonical command handler is registered.", "No end-to-end acceptance proof is registered."),
))

register_connector_definition(ConnectorDefinition(
    definition_id="pims.generic.read",
    connector_type="patient_management",
    name="Generic PIMS read adapter",
    version="0.1.0",
    supplier="LucyWorks",
    data_classes=("patient", "episode", "appointment", "clinical_record"),
    allowed_actions=("patient.read", "episode.read", "appointment.read", "clinical_record.read"),
    purpose="Read authorised source-system data into canonical hospital context.",
))
register_connector_definition(ConnectorDefinition(
    definition_id="pacs.dicom.read",
    connector_type="imaging",
    name="PACS/DICOM read adapter",
    version="0.1.0",
    supplier="LucyWorks",
    data_classes=("diagnostic_order", "study", "result"),
    allowed_actions=("diagnostic_order.read", "study.read", "result.read"),
    purpose="Resolve authorised imaging studies and reports without exposing PACS internals.",
))
