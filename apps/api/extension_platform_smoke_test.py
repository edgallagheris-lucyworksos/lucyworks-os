import inspect
import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / f"lucyworks_extension_platform_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB}",
    "AUTO_CREATE_SCHEMA": "true",
    "AUTH_MODE": "local",
    "AUTH_ENFORCEMENT": "required",
    "AUTH_DEV_LOGIN_ENABLED": "true",
    "AUTH_RETURN_BEARER_DEV": "true",
    "AUTH_JWT_SECRET": "extension-platform-smoke-secret-long-enough",
    "AUTH_ISSUER": "lucyworks-extension-platform-smoke",
    "AUTH_AUDIENCE": "lucyworks-extension-platform-smoke-api",
    "LEGACY_WRITE_MODE": "block",
    "AUTOMATION_V22_DEFAULT_MODE": "disabled",
    "AUTOMATION_V22_BACKGROUND_ENABLED": "false",
    "V26_CONTEXT_BOOTSTRAP_ENABLED": "false",
    "V27_CONFIGURATION_REQUIRED": "false",
})

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import SQLModel, Session, select

from app.auth import AuthContext
from app.canonical_event_schema import CanonicalEvent, SubjectRef, publish_canonical_event
from app.database import engine
from app.extension_registry import CommandHandler, MODULES, ModuleManifest, register_module
from app.integration_agent_gateway import authorise_gateway_call
from app.main import app
from app.models import User
from app.operational_context_v26_models import SiteMembershipV26
from app.real_hospital_connection_v28_models import IntegrationConnectorV28
from app.v7_models import DurableEvent

SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)

AUTH = AuthContext(
    subject="local-user:3131",
    actor_id="3131",
    actor_name="Extension Platform Director",
    role="hospital_director",
    email="extension-platform@example.test",
    issuer="lucyworks-extension-platform-smoke",
    auth_source="local_signed_token",
    verified=True,
)

with Session(engine) as session:
    session.add_all([
        User(
            id=3131,
            name=AUTH.actor_name,
            role=AUTH.role,
            email=AUTH.email,
        ),
        SiteMembershipV26(
            membership_ref="membership-extension-site-a",
            subject=AUTH.subject,
            actor_id=AUTH.actor_id,
            organisation_ref="group-extension",
            site_ref="hospital-extension-a",
            premises_ref="premises-extension-a",
            role=AUTH.role,
            status="active",
            is_primary=True,
            granted_by_subject=AUTH.subject,
        ),
        IntegrationConnectorV28(
            connector_ref="connector-site-a-read",
            organisation_ref="group-extension",
            site_ref="hospital-extension-a",
            premises_ref="premises-extension-a",
            connector_type="patient_management",
            vendor_name="PIMS Test Vendor",
            environment="sandbox",
            endpoint_host="pims.example.test",
            secret_env="PIMS_TEST_SECRET",
            mode="read_only",
            status="active",
            last_test_status="passed",
            created_by_subject=AUTH.subject,
            updated_by_subject=AUTH.subject,
        ),
        IntegrationConnectorV28(
            connector_ref="connector-site-a-disabled",
            organisation_ref="group-extension",
            site_ref="hospital-extension-a",
            premises_ref="premises-extension-a",
            connector_type="imaging",
            vendor_name="PACS Test Vendor",
            environment="sandbox",
            mode="disabled",
            status="draft",
            created_by_subject=AUTH.subject,
            updated_by_subject=AUTH.subject,
        ),
        IntegrationConnectorV28(
            connector_ref="connector-site-a-write-mode",
            organisation_ref="group-extension",
            site_ref="hospital-extension-a",
            premises_ref="premises-extension-a",
            connector_type="imaging",
            vendor_name="Corrupt Write-Mode PACS",
            environment="production",
            mode="write",
            status="active",
            last_test_status="passed",
            created_by_subject=AUTH.subject,
            updated_by_subject=AUTH.subject,
        ),
        IntegrationConnectorV28(
            connector_ref="connector-site-b-read",
            organisation_ref="group-extension",
            site_ref="hospital-extension-b",
            premises_ref="premises-extension-b",
            connector_type="patient_management",
            vendor_name="Other Site PIMS",
            environment="sandbox",
            mode="read_only",
            status="active",
            created_by_subject="local-user:other",
            updated_by_subject="local-user:other",
        ),
    ])
    session.commit()


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/dev-login", json={"user_id": 3131})
    assert response.status_code == 200, response.text
    token = response.json().get("accessToken")
    assert token
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def expect_http_error(call, status_code: int, code: str) -> None:
    try:
        call()
    except HTTPException as exc:
        assert exc.status_code == status_code, exc.detail
        assert isinstance(exc.detail, dict) and exc.detail.get("code") == code, exc.detail
    else:
        raise AssertionError(f"expected HTTP {status_code} {code}")


try:
    required_modules = {"lucy.capture", "lucy.pharmacy", "lucy.insurance", "lucy.disruption"}
    assert required_modules <= set(MODULES)
    assert all(MODULES[item].lifecycle == "disabled" for item in required_modules)
    assert all(MODULES[item].executable is False for item in required_modules)
    assert all(not MODULES[item].command_handlers for item in required_modules)

    try:
        register_module(ModuleManifest(
            module_id="test.shadow_mutation",
            name="Shadow mutation",
            version="1.0.0",
            lifecycle="disabled",
            mutates=("patient",),
        ))
    except ValueError as exc:
        assert "must declare commands" in str(exc)
    else:
        raise AssertionError("a mutating module without a command was registered")

    try:
        register_module(ModuleManifest(
            module_id="test.unbacked",
            name="Unbacked module",
            version="1.0.0",
            lifecycle="experimental",
            commands=("test.execute",),
            executable=True,
            command_handlers=(CommandHandler("test.execute", "app.missing_handler:execute"),),
            acceptance_tests=("test_missing_handler",),
        ))
    except ValueError as exc:
        assert "does not resolve" in str(exc)
    else:
        raise AssertionError("an executable module with a missing command handler was registered")
    assert "test.unbacked" not in MODULES
    print("Registry cannot turn declarations into unbacked runtime authority OK")

    assert "write" not in inspect.signature(authorise_gateway_call).parameters
    with Session(engine) as session:
        authorised = authorise_gateway_call(
            session,
            AUTH,
            connector_ref="connector-site-a-read",
            action="patient.read",
        )
        assert authorised.connector_ref == "connector-site-a-read"
        expect_http_error(
            lambda: authorise_gateway_call(
                session,
                AUTH,
                connector_ref="connector-site-a-read",
                action="medication.administer",
            ),
            403,
            "connector_action_not_allowed",
        )
        expect_http_error(
            lambda: authorise_gateway_call(
                session,
                AUTH,
                connector_ref="connector-site-a-disabled",
                action="study.read",
            ),
            403,
            "connector_not_active",
        )
        expect_http_error(
            lambda: authorise_gateway_call(
                session,
                AUTH,
                connector_ref="connector-site-a-write-mode",
                action="study.read",
            ),
            403,
            "connector_mode_not_read_only",
        )
        expect_http_error(
            lambda: authorise_gateway_call(
                session,
                AUTH,
                connector_ref="connector-site-b-read",
                action="patient.read",
            ),
            403,
            "connector_scope_mismatch",
        )
    print("Persisted status, read-only action and active-site connector gates OK")

    try:
        CanonicalEvent(
            event_type="patient.update",
            organisation_ref="group-extension",
            site_ref="hospital-extension-a",
            premises_ref="premises-extension-a",
            subjects=[SubjectRef(kind="patient", ref="patient-1")],
            source="extension-smoke",
            correlation_id="episode-1",
            idempotency_key="extension-event-1",
        )
    except ValidationError as exc:
        assert "observed fact" in str(exc)
    else:
        raise AssertionError("a command-like event name was accepted")

    event = CanonicalEvent(
        event_id="source-event-1",
        event_type="patient.arrived",
        organisation_ref="group-extension",
        site_ref="hospital-extension-a",
        premises_ref="premises-extension-a",
        subjects=[SubjectRef(kind="patient", ref="patient-1")],
        source="extension-smoke",
        correlation_id="episode-1",
        idempotency_key="extension-event-1",
        payload={"arrivalState": "recorded"},
    )
    with Session(engine) as session:
        stored = publish_canonical_event(session, AUTH, event)
        duplicate = publish_canonical_event(session, AUTH, event)
        assert duplicate.id == stored.id
        assert stored.actor_subject == AUTH.subject
        assert stored.actor_role == AUTH.role
        assert stored.payload["organisationRef"] == "group-extension"
        assert stored.payload["siteRef"] == "hospital-extension-a"
        assert stored.payload["premisesRef"] == "premises-extension-a"
        assert stored.payload["subjects"] == [{"kind": "patient", "ref": "patient-1"}]

        conflicting = event.model_copy(update={"payload": {"arrivalState": "changed"}})
        expect_http_error(
            lambda: publish_canonical_event(session, AUTH, conflicting),
            409,
            "event_idempotency_conflict",
        )
        wrong_site = event.model_copy(update={
            "event_id": "source-event-wrong-site",
            "site_ref": "hospital-extension-b",
            "premises_ref": "premises-extension-b",
            "idempotency_key": "extension-event-wrong-site",
        })
        expect_http_error(
            lambda: publish_canonical_event(session, AUTH, wrong_site),
            409,
            "cross_site_write_rejected",
        )
        session.commit()
        events = session.exec(select(DurableEvent).where(
            DurableEvent.idempotency_key == "extension-event-1"
        )).all()
        assert len(events) == 1
    print("Fact validation, site scope, durable actor attribution and idempotency OK")

    with TestClient(app) as client:
        unauthenticated = client.get("/api/platform/connectors")
        assert unauthenticated.status_code == 401, unauthenticated.text
        headers = login(client)

        modules = client.get("/api/platform/modules", headers=headers)
        assert modules.status_code == 200, modules.text
        assert all(not item["executable"] for item in modules.json()["modules"])

        definitions = client.get("/api/platform/connector-definitions", headers=headers)
        assert definitions.status_code == 200, definitions.text
        assert all(
            not item["external_write_supported"]
            for item in definitions.json()["connectorDefinitions"]
        )

        connectors = client.get("/api/platform/connectors", headers=headers)
        assert connectors.status_code == 200, connectors.text
        body = connectors.json()
        assert body["scope"]["siteRef"] == "hospital-extension-a"
        assert {item["connectorRef"] for item in body["connectors"]} == {
            "connector-site-a-read", "connector-site-a-disabled", "connector-site-a-write-mode"
        }
        assert all(item["writeAllowed"] is False for item in body["connectors"])
        assert all("secret_env" not in item and "secretEnv" not in item for item in body["connectors"])
        by_ref = {item["connectorRef"]: item for item in body["connectors"]}
        assert by_ref["connector-site-a-read"]["authorisedActions"] == [
            "patient.read", "episode.read", "appointment.read", "clinical_record.read"
        ]
        assert by_ref["connector-site-a-disabled"]["authorisedActions"] == []
        assert by_ref["connector-site-a-write-mode"]["authorisedActions"] == []

        contract = client.get("/api/platform/extension-contract", headers=headers)
        assert contract.status_code == 200, contract.text
        contract_body = contract.json()
        controls = {item["id"]: item["status"] for item in contract_body["controls"]}
        assert controls["registry-runtime-authority"] == "enforced_and_tested"
        assert controls["canonical-event-envelope"] == "enforced_and_tested"
        assert controls["connector-write-authority"] == "enforced_and_tested"
        assert controls["external-write-back"] == "unsupported"
        assert controls["canonical-state-and-ai-policy"] == "declared_architecture_rule"
        assert "rules" not in contract_body
    print("Authenticated API exposes only site-scoped state and qualified claims OK")

    print("\n--- EXTENSION PLATFORM SAFETY SMOKE TEST PASSED ---\n")
finally:
    if TEST_DB.exists():
        TEST_DB.unlink()
