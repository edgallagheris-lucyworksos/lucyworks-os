from sqlmodel import Session, SQLModel, create_engine, select

from app.external_system_adapter_runtime import ingest_normalized_event
from app.hospital_ops_models import CanonicalEpisodeState
from app.real_hospital_connection_v28_models import IntegrationConnectorV28, IntegrationEventV28, ReconciliationItemV28


def run() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        episode = CanonicalEpisodeState(
            episode_ref="episode-1", patient_ref="patient-1", patient_name="Bailey",
            premises_ref="site-1", status="active",
        )
        connector = IntegrationConnectorV28(
            connector_ref="connector-pims", organisation_ref="org-1", site_ref="site-1",
            premises_ref="site-1", connector_type="patient_management", vendor_name="fixture-vendor",
            environment="sandbox", mode="shadow", status="active",
            last_test_status="passed", created_by_subject="admin", updated_by_subject="admin",
        )
        session.add(episode)
        session.add(connector)
        session.commit()

        event = {
            "externalEventId": "evt-1",
            "eventType": "patient_updated",
            "payload": {
                "externalPatientRef": "vendor-patient-44",
                "eventOccurredAt": "2026-08-11T12:00:00Z",
                "lucyPatientRef": "patient-1",
                "lucyEpisodeRef": "episode-1",
            },
        }
        accepted = ingest_normalized_event(session, "connector-pims", event)
        assert accepted.status == "accepted", accepted
        session.commit()

        duplicate = ingest_normalized_event(session, "connector-pims", event)
        assert duplicate.status == "duplicate_ignored" and duplicate.duplicate
        session.commit()
        assert len(session.exec(select(IntegrationEventV28)).all()) == 1

        conflict = {**event, "payload": {**event["payload"], "externalPatientRef": "changed"}}
        conflicting = ingest_normalized_event(session, "connector-pims", conflict)
        assert conflicting.status == "conflicting_duplicate"
        session.commit()
        connector = session.exec(select(IntegrationConnectorV28).where(IntegrationConnectorV28.connector_ref == "connector-pims")).one()
        assert connector.status == "degraded"
        reds = session.exec(select(ReconciliationItemV28).where(ReconciliationItemV28.severity == "red")).all()
        assert len(reds) == 1

        connector.status = "active"
        session.add(connector)
        session.commit()
        unmatched = {
            "externalEventId": "evt-2",
            "eventType": "patient_updated",
            "payload": {
                "externalPatientRef": "vendor-patient-unknown",
                "eventOccurredAt": "2026-08-11T12:05:00Z",
            },
        }
        result = ingest_normalized_event(session, "connector-pims", unmatched)
        assert result.status == "reconciliation_required"
        assert result.reconciliation_ref
        session.commit()

        connector.mode = "write"
        session.add(connector)
        session.commit()
        try:
            ingest_normalized_event(session, "connector-pims", {**event, "externalEventId": "evt-3"})
        except RuntimeError as exc:
            assert "not authorised" in str(exc)
        else:
            raise AssertionError("write-mode connector was not blocked")

    print("EXTERNAL_ADAPTER_RUNTIME_SMOKE=PASS")


if __name__ == "__main__":
    run()
