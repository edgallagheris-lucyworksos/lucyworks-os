from lucyworks.rota_store import load_assignments, load_staff, get_master_rota, get_staff_schedule
from lucyworks.messaging import load_messages, message_status_summary
from lucyworks.rooms import load_rooms, room_state_summary
from lucyworks.imaging import imaging_status_summary
from lucyworks.insurance import insurers_requiring_pre_auth
from lucyworks.admissions_flow import load_admissions
from lucyworks.handover_flow import load_handovers
from lucyworks.results_flow import load_results
from lucyworks.discharge_flow import load_discharge_blockers
from lucyworks.case_state import latest_case_states, case_state_summary


def pulse_dashboard(st):
    st.subheader("LucyPulse Dashboard")

    assignments = load_assignments()
    messages = load_messages()
    admissions = load_admissions()
    handovers = load_handovers()
    results = load_results()
    blockers = load_discharge_blockers()
    states = latest_case_states()

    total_cases = len(assignments)
    high_risk = len(assignments[assignments["rota_risk"] == "HIGH"]) if not assignments.empty else 0
    escalations = len(assignments[assignments["safeguarding_path"] == "ESCALATE"]) if not assignments.empty else 0
    total_messages = len(messages)
    total_handovers = len(handovers)
    total_blockers = len(blockers)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Cases", total_cases)
    c2.metric("HIGH rota risk", high_risk)
    c3.metric("Safeguarding escalations", escalations)
    c4.metric("Messages", total_messages)
    c5.metric("Handovers", total_handovers)
    c6.metric("Blockers", total_blockers)

    st.markdown("### Case state summary")
    st.dataframe(case_state_summary(), use_container_width=True)
    st.markdown("### Latest case states")
    st.dataframe(states, use_container_width=True)
    st.markdown("### Assignments")
    st.dataframe(assignments, use_container_width=True)
    st.markdown("### Admissions")
    st.dataframe(admissions, use_container_width=True)
    st.markdown("### Pending results")
    st.dataframe(results, use_container_width=True)
    st.markdown("### Message status")
    st.dataframe(message_status_summary(), use_container_width=True)


def rota_dashboard(st):
    st.subheader("LucyRota Dashboard")

    st.markdown("### Master Rota")
    rota = get_master_rota()
    st.dataframe(rota, use_container_width=True)

    st.markdown("### Personal Dashboard")
    staff = load_staff()
    if not staff.empty:
        person = st.selectbox("Select staff member", staff["name"].tolist())
        person_row = staff[staff["name"] == person].iloc[0]
        schedule = get_staff_schedule(person_row["staff_id"])
        st.write("Role: " + str(person_row["role"]))
        st.write("Skills: " + str(person_row["skills"]))
        st.dataframe(schedule, use_container_width=True)

        assignments = load_assignments()
        if not assignments.empty:
            st.markdown("### Assigned Cases")
            case_view = assignments[
                (assignments["assigned_vet_id"] == person_row["staff_id"])
                | (assignments["assigned_nurse_id"] == person_row["staff_id"])
            ]
            st.dataframe(case_view, use_container_width=True)


def ops_dashboard(st):
    st.subheader("Hospital Operational Dashboard")

    assignments = load_assignments()
    rooms = load_rooms()
    messages = load_messages()
    admissions = load_admissions()
    handovers = load_handovers()
    results = load_results()
    blockers = load_discharge_blockers()
    states = latest_case_states()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Open cases", len(assignments))
    c2.metric("Rooms tracked", len(rooms))
    c3.metric("Messages tracked", len(messages))
    c4.metric("Pre-auth insurers", len(insurers_requiring_pre_auth()))
    c5.metric("Admissions", len(admissions))
    c6.metric("Handovers", len(handovers))

    st.markdown("### Case lifecycle")
    st.dataframe(case_state_summary(), use_container_width=True)
    st.markdown("### Room state summary")
    st.dataframe(room_state_summary(), use_container_width=True)
    st.markdown("### Imaging resource summary")
    st.dataframe(imaging_status_summary(), use_container_width=True)
    st.markdown("### Latest case states")
    st.dataframe(states, use_container_width=True)
    st.markdown("### Message queue")
    st.dataframe(messages, use_container_width=True)
    st.markdown("### Results queue")
    st.dataframe(results, use_container_width=True)
    st.markdown("### Discharge blockers")
    st.dataframe(blockers, use_container_width=True)
