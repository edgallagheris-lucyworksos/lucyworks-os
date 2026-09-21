from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext
from app.extension_registry import ConnectorDefinition, connector_definition_for_type
from app.operating_context_v26_service import OperatingContext, resolve_context
from app.real_hospital_connection_v28_models import IntegrationConnectorV28


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=403, detail={"code": code, "message": message})


def connectors_for_active_context(
    session: Session,
    auth: AuthContext,
) -> tuple[OperatingContext, list[IntegrationConnectorV28]]:
    context = resolve_context(session, auth)
    rows = session.exec(
        select(IntegrationConnectorV28).where(
            IntegrationConnectorV28.organisation_ref == context.organisation_ref,
            IntegrationConnectorV28.site_ref == context.site_ref,
            IntegrationConnectorV28.premises_ref == context.premises_ref,
        )
    ).all()
    return context, sorted(rows, key=lambda item: item.connector_ref)


def authorise_gateway_call(
    session: Session,
    auth: AuthContext,
    *,
    connector_ref: str,
    action: str,
) -> IntegrationConnectorV28:
    """Authorise a declared read through a persisted, site-scoped v28 connector.

    There is intentionally no caller-supplied ``write`` flag. The action must
    exist in a read-only connector definition, while runtime authority comes
    from the persisted connector and the caller's active operating context.
    """

    context = resolve_context(session, auth)
    connector = session.exec(
        select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == connector_ref)
    ).first()
    if not connector:
        raise _forbidden("connector_not_authorised", "connector is not authorised for this context")
    if (
        connector.organisation_ref != context.organisation_ref
        or connector.site_ref != context.site_ref
        or connector.premises_ref != context.premises_ref
    ):
        raise _forbidden("connector_scope_mismatch", "connector is outside the active hospital-site context")
    if connector.status != "active":
        raise _forbidden("connector_not_active", "connector is not active")

    definition = connector_definition_for_type(connector.connector_type)
    if not definition:
        raise _forbidden("connector_type_not_registered", "connector type has no extension-gateway definition")
    if connector.mode not in definition.supported_modes:
        raise _forbidden("connector_mode_not_read_only", "connector mode has no external read authority")
    if action not in definition.allowed_actions:
        raise _forbidden("connector_action_not_allowed", "connector action is not a declared read action")
    return connector


def public_connector(
    connector: IntegrationConnectorV28,
    definition: ConnectorDefinition | None = None,
) -> dict[str, Any]:
    definition = definition or connector_definition_for_type(connector.connector_type)
    runtime_read_authorised = bool(
        definition
        and connector.status == "active"
        and connector.mode in definition.supported_modes
    )
    return {
        "connectorRef": connector.connector_ref,
        "organisationRef": connector.organisation_ref,
        "siteRef": connector.site_ref,
        "premisesRef": connector.premises_ref,
        "connectorType": connector.connector_type,
        "vendorName": connector.vendor_name,
        "environment": connector.environment,
        "mode": connector.mode,
        "status": connector.status,
        "definitionId": definition.definition_id if definition else None,
        "declaredActions": list(definition.allowed_actions) if definition else [],
        "authorisedActions": list(definition.allowed_actions) if runtime_read_authorised and definition else [],
        "writeAllowed": False,
        "externalWriteSupported": False,
        "lastTestStatus": connector.last_test_status,
        "lastTestAt": connector.last_test_at.isoformat() if connector.last_test_at else None,
        "lastEventAt": connector.last_event_at.isoformat() if connector.last_event_at else None,
    }
