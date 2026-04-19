from lucyworks.rota_store import load_assignments, load_staff, get_master_rota, get_staff_schedule


def pulse_dashboard(st):
    st.subheader("LucyPulse Dashboard")

    assignments = load_assignments()
    total_cases = len(assignments)
    high_risk = len(assignments[assignments["rota_risk"] == "HIGH"]) if not assignments.empty else 0
    escalations = len(assignments[assignments["safeguarding_path"] == "ESCALATE"]) if not assignments.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Cases", total_cases)
    c2.metric("HIGH rota risk", high_risk)
    c3.metric("Safeguarding escalations", escalations)

    st.markdown("### Assignments")
    st.dataframe(assignments, use_container_width=True)


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
                (assignments["assigned_vet_id"] == person_row["staff_id"]) |
                (assignments["assigned_nurse_id"] == person_row["staff_id"])
            ]
            st.dataframe(case_view, use_container_width=True)
