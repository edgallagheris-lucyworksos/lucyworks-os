from datetime import datetime

import pandas as pd

from lucyworks.models import CaseInput, RotaOutput
from lucyworks.triage import run_triage
from lucyworks.ethics import run_ethics
from lucyworks.severity import assess_severity
from lucyworks.discharge import build_discharge
from lucyworks.rota import rota_assign
from lucyworks.procedures import get_procedure, procedure_duration_summary
from lucyworks.drugs import get_drug, controlled_drug_table
from lucyworks.rooms import room_state_summary
from lucyworks.labs import fast_turnaround_tests
from lucyworks.imaging import imaging_status_summary
from lucyworks.insurance import insurers_requiring_pre_auth
from lucyworks.messaging import build_message, load_messages, append_message, message_status_summary, case_messages
from lucyworks.admissions_flow import append_admission, load_admissions
from lucyworks.handover_flow import append_handover, load_handovers
from lucyworks.results_flow import append_result, load_results
from lucyworks.discharge_flow import append_discharge_blocker, load_discharge_blockers


def main():
    case = CaseInput(
        case_id="SMOKE-001",
        created_at=datetime.utcnow().isoformat() + "Z",
        mode="TRAINING",
        clinic="Test Clinic",
        species="Dog",
        procedure_type="TPLO",
        urgency_symptoms=["Severe pain"],
        owner_notes="Owner cooperative.",
        referring_vet="Dr Test",
        patient_name="Milo",
        weight_kg=18.0,
    )

    triage_out = run_triage(case)
    ethics_out = run_ethics(case, triage_out)

    staff = pd.DataFrame(
        [
            {"staff_id": "V001", "name": "Tom", "role": "Vet", "skills": "Surgery,Ortho,TPLO", "max_cases_per_day": 10, "current_load": 1},
            {"staff_id": "N001", "name": "Lucy", "role": "Nurse", "skills": "Theatre,Surgery", "max_cases_per_day": 20, "current_load": 2},
        ]
    )

    rota_out = rota_assign(staff, case, triage_out)
    severity_out = assess_severity(triage_out, ethics_out, rota_out)
    discharge_out = build_discharge(case, triage_out, rota_out)

    msg = build_message(case.case_id, "owner_update", "owner", "Case update", "Patient is stable.")
    append_message(msg)
    append_admission(case.case_id, "ward")
    append_handover(case.case_id, "intake", "wards", "Initial handover")
    append_result(case.case_id, "lab", "Tom")
    append_discharge_blocker(case.case_id, "notes_incomplete")

    assert triage_out.priority in {"Routine", "Urgent", "Emergency"}
    assert severity_out.severity in {"MINOR", "MODERATE", "CRITICAL"}
    assert isinstance(discharge_out.internal_text, str)
    assert isinstance(rota_out, RotaOutput)
    assert get_procedure("TPLO") is not None
    assert get_drug("METHADONE") is not None
    assert not procedure_duration_summary().empty
    assert not controlled_drug_table().empty
    assert room_state_summary() is not None
    assert fast_turnaround_tests() is not None
    assert imaging_status_summary() is not None
    assert insurers_requiring_pre_auth() is not None
    assert load_messages() is not None
    assert not message_status_summary().empty
    assert len(case_messages(case.case_id)) >= 1
    assert len(load_admissions()) >= 1
    assert len(load_handovers()) >= 1
    assert len(load_results()) >= 1
    assert len(load_discharge_blockers()) >= 1
    print("smoke test passed")


if __name__ == "__main__":
    main()
