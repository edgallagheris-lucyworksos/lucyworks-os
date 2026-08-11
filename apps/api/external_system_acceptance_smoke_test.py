from app.external_system_acceptance import evaluate_external_fixture


def main() -> None:
    known_patients = {"patient-1"}
    known_episodes = {"episode-1"}

    good_lab = [
        {
            "externalEventId": "lab-100",
            "eventType": "result.updated",
            "payload": {
                "externalPatientRef": "vendor-p-9",
                "lucyPatientRef": "patient-1",
                "lucyEpisodeRef": "episode-1",
                "resultRef": "chem-123",
                "resultStatus": "final",
                "eventOccurredAt": "2026-08-11T12:00:00Z",
            },
        },
        {
            "externalEventId": "lab-100",
            "eventType": "result.updated",
            "payload": {
                "externalPatientRef": "vendor-p-9",
                "lucyPatientRef": "patient-1",
                "lucyEpisodeRef": "episode-1",
                "resultRef": "chem-123",
                "resultStatus": "final",
                "eventOccurredAt": "2026-08-11T12:00:00Z",
            },
        },
    ]
    result = evaluate_external_fixture(
        connector_type="laboratory",
        events=good_lab,
        known_patient_refs=known_patients,
        known_episode_refs=known_episodes,
    )
    assert result["status"] == "PASS", result
    assert result["idempotentDuplicateCount"] == 1, result
    assert result["conflictingDuplicateCount"] == 0, result

    conflicting = [good_lab[0], {
        **good_lab[0],
        "payload": {**good_lab[0]["payload"], "resultStatus": "amended"},
    }]
    result = evaluate_external_fixture(
        connector_type="laboratory",
        events=conflicting,
        known_patient_refs=known_patients,
        known_episode_refs=known_episodes,
    )
    assert result["status"] == "FAIL", result
    assert result["conflictingDuplicateCount"] == 1, result

    unmatched_imaging = [{
        "externalEventId": "img-200",
        "eventType": "study.reported",
        "payload": {
            "externalPatientRef": "vendor-p-10",
            "studyRef": "study-44",
            "modality": "MRI",
            "eventOccurredAt": "2026-08-11T12:10:00Z",
        },
    }]
    result = evaluate_external_fixture(
        connector_type="imaging",
        events=unmatched_imaging,
        known_patient_refs=known_patients,
        known_episode_refs=known_episodes,
    )
    assert result["status"] == "PASS", result
    assert result["reconciliationRequiredCount"] == 1, result
    assert result["warnings"], result

    broken_pims = [{
        "externalEventId": "pims-1",
        "eventType": "patient.updated",
        "payload": {"eventOccurredAt": "not-a-time"},
    }]
    result = evaluate_external_fixture(connector_type="patient_management", events=broken_pims)
    assert result["status"] == "FAIL", result
    assert any("externalPatientRef" in blocker for blocker in result["blockers"]), result
    assert any("ISO-8601" in blocker for blocker in result["blockers"]), result

    print("EXTERNAL_SYSTEM_ACCEPTANCE=PASS")


if __name__ == "__main__":
    main()
