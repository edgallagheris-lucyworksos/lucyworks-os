import json
from datetime import datetime

import streamlit as st

from lucyworks.models import CaseInput
from lucyworks.triage import run_triage
from lucyworks.ethics import run_ethics
from lucyworks.rota import rota_assign
from lucyworks.rota_store import load_staff, append_assignment
from lucyworks.discharge import build_discharge
from lucyworks.severity import assess_severity
from lucyworks.audit import audit_event
from lucyworks.trace import trace_event
from lucyworks.policies import show_policies
from lucyworks.pulse import pulse_dashboard, rota_dashboard, ops_dashboard
from lucyworks.dashboard_map import dashboard_map_table
from lucyworks.room_state import default_room_state_table
from lucyworks.staff import default_staff_type_table
from lucyworks.intake import intake_status_table
from lucyworks.alerts import default_alert_table
from lucyworks.teams import team_table
from lucyworks.rooms import room_type_table, load_rooms, room_state_summary
from lucyworks.procedures import procedure_library_table, procedure_duration_summary, get_procedure
from lucyworks.drugs import drug_database_table, controlled_drug_table
from lucyworks.pharmacy import pharmacy_model_table, pharmacy_stock_view
from lucyworks.labs import lab_model_table, lab_test_library_table, fast_turnaround_tests
from lucyworks.imaging import imaging_model_table, imaging_resource_table, imaging_status_summary
from lucyworks.insurance import insurance_model_table, insurer_reference_table, insurers_requiring_pre_auth
from lucyworks.occupancy import occupancy_schema_table
from lucyworks.handover_flow import handover_schema_table
from lucyworks.results_flow import result_schema_table
from lucyworks.admissions_flow import admission_schema_table
from lucyworks.discharge_flow import discharge_blocker_table
from lucyworks.messaging import message_template_table, build_message, append_message, load_messages, case_messages, message_status_summary
from lucyworks.speech import speech_target_table
from lucyworks.governance import governance_object_table
from lucyworks.medication import medication_object_table

st.set_page_config(page_title="LucyWorks OS", layout="wide")
st.title("LucyWorks OS")
st.caption("Hospital workflow prototype and full model scaffold")

page = st.sidebar.radio(
    "Page",
    [
        "Intake Prototype",
        "Ops Dashboard",
        "Message Center",
        "Master Rota",
        "Pulse Dashboard",
        "Full Model Map",
        "Policies",
    ],
    index=0,
)
mode = st.sidebar.selectbox("Mode", ["TRAINING", "LIVE"], index=0)
reviewer_name = st.sidebar.text_input("Reviewer / clinician name")
override_reason = st.sidebar.text_area("Override / acknowledgement reason")
ack_safeguarding = st.sidebar.checkbox("Safeguarding acknowledged")


def export_case_bundle(case_obj, triage_out, ethics_out, rota_out, severity_out, discharge_out):
    bundle = {
        "case": case_obj.to_dict(),
        "triage": triage_out.to_dict(),
        "ethics": ethics_out.to_dict(),
        "rota": rota_out.to_dict(),
        "severity": severity_out.to_dict(),
        "discharge": discharge_out.to_dict(),
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }
    return json.dumps(bundle, indent=2)


if page == "Intake Prototype":
    st.subheader("Intake to discharge vertical slice")

    c1, c2, c3 = st.columns(3)
    case_id = c1.text_input("Case ID", value="LW-001")
    patient_name = c2.text_input("Patient name", value="Milo")
    clinic = c3.text_input("Clinic", value="Bristol Referral")

    c4, c5, c6 = st.columns(3)
    species = c4.selectbox("Species", ["Dog", "Cat", "Rabbit"], index=0)
    procedure_type = c5.selectbox(
        "Procedure type",
        ["TPLO", "Dental", "Castration", "Neuro_Spine", "Soft_Tissue", "Rabbit_GA", "Other"],
        index=0,
    )
    weight_kg = c6.number_input("Weight kg", min_value=0.0, value=18.5, step=0.5)

    symptoms = st.multiselect(
        "Urgency symptoms",
        [
            "Collapse",
            "Respiratory distress",
            "Uncontrolled bleeding",
            "Non-weight bearing lameness",
            "Seizures",
            "Pale gums",
            "Severe pain",
            "Vomiting",
            "Diarrhoea",
            "Lethargy",
        ],
        default=["Severe pain"],
    )
    owner_notes = st.text_area("Owner notes", value="Owner distressed but cooperative.")
    referring_vet = st.text_input("Referring vet", value="Dr Smith")

    proc_meta = get_procedure(procedure_type)
    if proc_meta is not None:
        st.caption("Procedure cycle minutes: " + str(proc_meta.get("expected_minutes", 0) + proc_meta.get("prep_minutes", 0) + proc_meta.get("recovery_minutes", 0) + proc_meta.get("cleaning_minutes", 0)))

    if st.button("Run workflow"):
        case = CaseInput(
            case_id=case_id,
            created_at=datetime.utcnow().isoformat() + "Z",
            mode=mode,
            clinic=clinic,
            species=species,
            procedure_type=procedure_type,
            urgency_symptoms=symptoms,
            owner_notes=owner_notes,
            referring_vet=referring_vet,
            patient_name=patient_name,
            weight_kg=weight_kg,
        )

        triage_out = run_triage(case)
        ethics_out = run_ethics(case, triage_out)
        staff = load_staff()
        rota_out = rota_assign(staff, case, triage_out)
        severity_out = assess_severity(triage_out, ethics_out, rota_out)
        discharge_out = build_discharge(case, triage_out, rota_out)

        st.markdown("### Triage")
        st.write(triage_out.to_dict())
        st.markdown("### Ethics")
        st.write(ethics_out.to_dict())
        st.markdown("### Rota")
        st.write(rota_out.to_dict())
        st.markdown("### Severity")
        st.write(severity_out.to_dict())
        st.markdown("### Discharge draft")
        st.code(discharge_out.internal_text)
        st.code(discharge_out.client_summary)

        blocked = False
        reasons = []
        if mode == "LIVE":
            if not reviewer_name.strip():
                blocked = True
                reasons.append("Reviewer identity missing")
            if rota_out.rota_risk == "HIGH" and not override_reason.strip():
                blocked = True
                reasons.append("High rota risk accepted with no reason")
            if ethics_out.safeguarding_path == "ESCALATE" and not ack_safeguarding:
                blocked = True
                reasons.append("Safeguarding escalation not acknowledged")

        if blocked:
            st.error("LIVE blocked: " + "; ".join(reasons))
        else:
            append_assignment(
                {
                    "date": datetime.utcnow().date().isoformat(),
                    "case_id": case.case_id,
                    "species": case.species,
                    "procedure_type": case.procedure_type,
                    "priority": triage_out.priority,
                    "triage_score": triage_out.triage_score,
                    "assigned_vet_id": rota_out.assigned_vet,
                    "assigned_nurse_id": rota_out.assigned_nurse,
                    "rota_risk": rota_out.rota_risk,
                    "safeguarding_path": ethics_out.safeguarding_path,
                }
            )
            ack_msg = build_message(case.case_id, "referral_ack", "referrer", "Referral acknowledged", "Case " + case.case_id + " has been logged and triaged.")
            owner_msg = build_message(case.case_id, "owner_update", "owner", "Case update", "Patient " + case.patient_name + " is in workflow with priority " + triage_out.priority + ".")
            append_message(ack_msg)
            append_message(owner_msg)
            audit_event({"event": "CASE_RUN", "case_id": case.case_id, "mode": mode})
            trace_event({"event": "CASE_RUN", "case_id": case.case_id, "mode": mode})
            st.success("Workflow completed")
            st.markdown("### Draft messages created")
            st.dataframe(case_messages(case.case_id), use_container_width=True)

        export_text = export_case_bundle(case, triage_out, ethics_out, rota_out, severity_out, discharge_out)
        st.download_button(
            "Download case bundle",
            data=export_text,
            file_name=case.case_id + "_bundle.json",
            mime="application/json",
        )

elif page == "Ops Dashboard":
    ops_dashboard(st)
elif page == "Message Center":
    st.subheader("Message Center")
    messages = load_messages()
    st.dataframe(messages, use_container_width=True)
    st.markdown("### Message status")
    st.dataframe(message_status_summary(), use_container_width=True)
elif page == "Master Rota":
    rota_dashboard(st)
elif page == "Pulse Dashboard":
    pulse_dashboard(st)
elif page == "Full Model Map":
    st.subheader("Full model map")
    st.markdown("### Teams and staff")
    st.dataframe(team_table(), use_container_width=True)
    st.dataframe(default_staff_type_table(), use_container_width=True)

    st.markdown("### Intake, rooms, and occupancy")
    st.dataframe(intake_status_table(), use_container_width=True)
    st.dataframe(room_type_table(), use_container_width=True)
    st.dataframe(load_rooms(), use_container_width=True)
    st.dataframe(room_state_summary(), use_container_width=True)
    st.dataframe(default_room_state_table(), use_container_width=True)
    st.dataframe(occupancy_schema_table(), use_container_width=True)

    st.markdown("### Procedures and medication")
    st.dataframe(procedure_library_table(), use_container_width=True)
    st.dataframe(procedure_duration_summary(), use_container_width=True)
    st.dataframe(drug_database_table(), use_container_width=True)
    st.dataframe(controlled_drug_table(), use_container_width=True)
    st.dataframe(pharmacy_model_table(), use_container_width=True)
    st.dataframe(pharmacy_stock_view(), use_container_width=True)
    st.dataframe(medication_object_table(), use_container_width=True)

    st.markdown("### Labs, imaging, insurance")
    st.dataframe(lab_model_table(), use_container_width=True)
    st.dataframe(lab_test_library_table(), use_container_width=True)
    st.dataframe(fast_turnaround_tests(), use_container_width=True)
    st.dataframe(imaging_model_table(), use_container_width=True)
    st.dataframe(imaging_resource_table(), use_container_width=True)
    st.dataframe(imaging_status_summary(), use_container_width=True)
    st.dataframe(insurance_model_table(), use_container_width=True)
    st.dataframe(insurer_reference_table(), use_container_width=True)
    st.dataframe(insurers_requiring_pre_auth(), use_container_width=True)

    st.markdown("### Flows and governance")
    st.dataframe(admission_schema_table(), use_container_width=True)
    st.dataframe(handover_schema_table(), use_container_width=True)
    st.dataframe(result_schema_table(), use_container_width=True)
    st.dataframe(discharge_blocker_table(), use_container_width=True)
    st.dataframe(default_alert_table(), use_container_width=True)
    st.dataframe(message_template_table(), use_container_width=True)
    st.dataframe(speech_target_table(), use_container_width=True)
    st.dataframe(governance_object_table(), use_container_width=True)
    st.dataframe(dashboard_map_table(), use_container_width=True)
else:
    show_policies(st)
