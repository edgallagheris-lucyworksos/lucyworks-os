from app.extension_registry import MODULES, CONNECTORS, ModuleManifest, register_module
from app.canonical_event_schema import CanonicalEvent, SubjectRef, event_name_is_fact
from app.integration_agent_gateway import authorise_gateway_call


def test_required_modules_are_registered():
    assert {"lucy.capture", "lucy.pharmacy", "lucy.insurance", "lucy.disruption"} <= set(MODULES)


def test_mutating_module_requires_commands():
    try:
        register_module(ModuleManifest(
            module_id="test.invalid", name="Invalid", version="1", lifecycle="experimental",
            mutates=("patient",),
        ))
    except ValueError as exc:
        assert "must declare commands" in str(exc)
    else:
        raise AssertionError("shadow mutation was accepted")


def test_canonical_event_is_scoped_and_fact_named():
    event = CanonicalEvent(
        event_type="patient.arrived",
        organisation_ref="org-1", site_ref="site-1", premises_ref="prem-1",
        subjects=[SubjectRef(kind="patient", ref="p-1")],
        source="test", correlation_id="corr-1",
    )
    assert event.premises_ref == "prem-1"
    assert event_name_is_fact(event.event_type)
    assert not event_name_is_fact("patient.update")


def test_connectors_default_to_disabled_read_only():
    connector = CONNECTORS["pims.generic.read"]
    assert connector.mode == "read"
    assert connector.enabled is False
    try:
        authorise_gateway_call(connector.connector_id, action="patient.read")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("disabled connector was authorised")
