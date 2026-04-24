from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import (
    Admission,
    AuditEvent,
    Episode,
    Handover,
    HospitalSection,
    MessageEntry,
    MessageThread,
    Patient,
    ProcedureType,
    ResultReview,
    Room,
    RoomState,
    Shift,
    StaffMember,
    User,
    WorkItem,
)


def seed_data(session: Session) -> None:
    if session.exec(select(User)).first():
        return

    users = [
        User(name="Lucy Ops", role="ops_manager", email="ops@lucyworks.local"),
        User(name="Nina Nurse", role="nurse", email="nurse@lucyworks.local"),
        User(name="Cal Clinician", role="clinician", email="clinician@lucyworks.local"),
        User(name="Ari Admin", role="admin", email="admin@lucyworks.local"),
    ]
    for user in users:
        session.add(user)

    sections = [
        HospitalSection(name="Reception", section_type="front_of_house"),
        HospitalSection(name="Triage", section_type="clinical_intake"),
        HospitalSection(name="Consults", section_type="clinical_intake"),
        HospitalSection(name="Theatres", section_type="procedures"),
        HospitalSection(name="Recovery", section_type="procedures"),
        HospitalSection(name="ICU", section_type="inpatient"),
        HospitalSection(name="Wards", section_type="inpatient"),
        HospitalSection(name="Imaging", section_type="diagnostics"),
        HospitalSection(name="Lab", section_type="diagnostics"),
        HospitalSection(name="Pharmacy", section_type="support"),
        HospitalSection(name="Discharge", section_type="front_of_house"),
    ]
    for section in sections:
        session.add(section)

    rooms = [
        Room(section_name="Reception", name="Front Desk", room_type="desk"),
        Room(section_name="Reception", name="Meet and Greet", room_type="handover"),
        Room(section_name="Triage", name="Triage Bay", room_type="triage"),
        Room(section_name="Consults", name="Consult Room 1", room_type="consult"),
        Room(section_name="Consults", name="Consult Room 2", room_type="consult"),
        Room(section_name="Theatres", name="Theatre 1", room_type="theatre"),
        Room(section_name="Theatres", name="Theatre 2", room_type="theatre"),
        Room(section_name="Recovery", name="Recovery Bay", room_type="recovery"),
        Room(section_name="ICU", name="ICU Bay Area", room_type="icu"),
        Room(section_name="Wards", name="Ward Dogs", room_type="ward"),
        Room(section_name="Wards", name="Ward Cats", room_type="ward"),
        Room(section_name="Imaging", name="Imaging Room", room_type="imaging"),
        Room(section_name="Lab", name="Lab Bench", room_type="lab"),
        Room(section_name="Pharmacy", name="Pharmacy Store", room_type="pharmacy"),
        Room(section_name="Discharge", name="Discharge Desk", room_type="discharge"),
    ]
    for room in rooms:
        session.add(room)
    session.commit()

    saved_users = session.exec(select(User)).all()
    user_by_role = {user.role: user for user in saved_users}

    staff = [
        StaffMember(user_id=user_by_role["ops_manager"].id, name="Lucy Ops", role="ops_manager", skills="flow, escalation, theatre, ward"),
        StaffMember(user_id=user_by_role["nurse"].id, name="Nina Nurse", role="nurse", skills="ward, ICU, recovery, discharge"),
        StaffMember(user_id=user_by_role["clinician"].id, name="Cal Clinician", role="clinician", skills="consult, imaging, surgery, review"),
        StaffMember(user_id=user_by_role["admin"].id, name="Ari Admin", role="admin", skills="reception, owner_comms, discharge"),
    ]
    for member in staff:
        session.add(member)
    session.commit()

    saved_staff = session.exec(select(StaffMember)).all()
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    for member in saved_staff:
        session.add(Shift(staff_member_id=member.id, department="Hospital", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=10), shift_type="standard", status="active"))
    session.commit()

    patients = [
        Patient(patient_name="Milo", species="Dog", owner_name="Sarah Reed", owner_phone="07111111111", weight_kg=24.5),
        Patient(patient_name="Nova", species="Dog", owner_name="Chris Lane", owner_phone="07222222222", weight_kg=31.0),
        Patient(patient_name="Pepper", species="Cat", owner_name="Anna Cole", owner_phone="07333333333", weight_kg=4.2),
        Patient(patient_name="Poppy", species="Dog", owner_name="James Stone", owner_phone="07444444444", weight_kg=18.3),
        Patient(patient_name="Otis", species="Cat", owner_name="Emma Bright", owner_phone="07555555555", weight_kg=5.1),
        Patient(patient_name="Rosie", species="Dog", owner_name="Mark Ellis", owner_phone="07666666666", weight_kg=12.7),
        Patient(patient_name="Luna", species="Dog", owner_name="Rachel Moss", owner_phone="07777777777", weight_kg=27.9),
        Patient(patient_name="Rex", species="Dog", owner_name="Tom Field", owner_phone="07888888888", weight_kg=22.1),
        Patient(patient_name="Bella", species="Dog", owner_name="Kate West", owner_phone="07999999999", weight_kg=29.4),
    ]
    for patient in patients:
        session.add(patient)
    session.commit()

    patient_by_name = {patient.patient_name: patient for patient in session.exec(select(Patient)).all()}
    episodes = [
        Episode(episode_ref="EP-1042", patient_id=patient_by_name["Milo"].id, current_section_name="Wards", current_room_name="Ward Dogs", current_phase="ward"),
        Episode(episode_ref="EP-1051", patient_id=patient_by_name["Nova"].id, current_section_name="ICU", current_room_name="ICU Bay Area", current_phase="critical_care"),
        Episode(episode_ref="EP-1053", patient_id=patient_by_name["Pepper"].id, current_section_name="Wards", current_room_name="Ward Cats", current_phase="ward"),
        Episode(episode_ref="EP-1057", patient_id=patient_by_name["Poppy"].id, current_section_name="Consults", current_room_name="Consult Room 1", current_phase="consult"),
        Episode(episode_ref="EP-1058", patient_id=patient_by_name["Otis"].id, current_section_name="Consults", current_room_name="Consult Room 2", current_phase="consult"),
        Episode(episode_ref="EP-1059", patient_id=patient_by_name["Rosie"].id, current_section_name="Consults", current_room_name="Consult Room 1", current_phase="follow_up"),
        Episode(episode_ref="EP-1045", patient_id=patient_by_name["Luna"].id, current_section_name="Imaging", current_room_name="Imaging Room", current_phase="result_review"),
        Episode(episode_ref="EP-1055", patient_id=patient_by_name["Rex"].id, current_section_name="Recovery", current_room_name="Recovery Bay", current_phase="recovery"),
        Episode(episode_ref="EP-1056", patient_id=patient_by_name["Bella"].id, current_section_name="Theatres", current_room_name="Theatre 1", current_phase="procedure"),
        Episode(episode_ref="EP-1048", patient_id=patient_by_name["Bella"].id, current_section_name="Theatres", current_room_name="Theatre 2", current_phase="procedure"),
    ]
    for episode in episodes:
        session.add(episode)
    session.commit()

    episode_by_ref = {episode.episode_ref: episode for episode in session.exec(select(Episode)).all()}

    for admission in [
        Admission(episode_id=episode_by_ref["EP-1042"].id, admitted_to="Wards"),
        Admission(episode_id=episode_by_ref["EP-1051"].id, admitted_to="ICU"),
        Admission(episode_id=episode_by_ref["EP-1053"].id, admitted_to="Wards"),
    ]:
        session.add(admission)

    for handover in [
        Handover(episode_id=episode_by_ref["EP-1055"].id, from_owner="theatre_team", to_owner="recovery_nurse", note="Post-op handoff pending full recovery checklist.", acknowledged=False),
        Handover(episode_id=episode_by_ref["EP-1042"].id, from_owner="clinician", to_owner="ward_nurse", note="Owner update still to be completed before discharge prep.", acknowledged=True),
    ]:
        session.add(handover)

    session.add(ResultReview(episode_id=episode_by_ref["EP-1045"].id, result_type="imaging", review_owner="Cal Clinician", status="pending_review", required_action="Review scan and contact owner"))

    for procedure in [
        ProcedureType(name="TPLO", department="Theatres", default_duration_min=90, prep_min=20, anaesthesia_min=15, recovery_min=45, cleaning_min=20, required_role="clinician", required_room_type="theatre"),
        ProcedureType(name="MRI", department="Imaging", default_duration_min=60, prep_min=15, anaesthesia_min=10, recovery_min=20, cleaning_min=15, required_role="clinician", required_room_type="imaging"),
        ProcedureType(name="Dental", department="Theatres", default_duration_min=50, prep_min=15, anaesthesia_min=10, recovery_min=25, cleaning_min=15, required_role="clinician", required_room_type="theatre"),
    ]:
        session.add(procedure)

    for room_state in [
        RoomState(room_name="Consult Room 1", room_type="consult", department="Consults", state="occupied", current_episode_ref="EP-1057", next_episode_ref="EP-1059"),
        RoomState(room_name="Consult Room 2", room_type="consult", department="Consults", state="occupied", current_episode_ref="EP-1058"),
        RoomState(room_name="Theatre 1", room_type="theatre", department="Theatres", state="occupied", current_episode_ref="EP-1056", cleaning_due_minutes=20),
        RoomState(room_name="Theatre 2", room_type="theatre", department="Theatres", state="occupied", current_episode_ref="EP-1048", cleaning_due_minutes=25),
        RoomState(room_name="Recovery Bay", room_type="recovery", department="Recovery", state="occupied", current_episode_ref="EP-1055"),
        RoomState(room_name="ICU Bay Area", room_type="icu", department="ICU", state="occupied", current_episode_ref="EP-1051"),
        RoomState(room_name="Ward Dogs", room_type="ward", department="Wards", state="occupied", current_episode_ref="EP-1042"),
        RoomState(room_name="Ward Cats", room_type="ward", department="Wards", state="occupied", current_episode_ref="EP-1053"),
        RoomState(room_name="Imaging Room", room_type="imaging", department="Imaging", state="occupied", current_episode_ref="EP-1045"),
    ]:
        session.add(room_state)

    items = [
        WorkItem(title="Communication update needed", input_type="discharge_blocker", source="ward", category="care", description="Owner update is still outstanding.", urgency="amber", owner_role="nurse", owner_user_id=user_by_role["nurse"].id, section_name="Wards", room_name="Ward Dogs", patient_location_label="Kennel B4", linked_patient_name="Milo", linked_episode_ref="EP-1042", status="in_progress"),
        WorkItem(title="ICU monitoring review overdue", input_type="inpatient_update", source="ward", category="critical_care", description="Observation review needs clinician confirmation.", urgency="red", owner_role="clinician", owner_user_id=user_by_role["clinician"].id, section_name="ICU", room_name="ICU Bay Area", patient_location_label="Bay A", linked_patient_name="Nova", linked_episode_ref="EP-1051", status="new"),
        WorkItem(title="Ward medication task not completed", input_type="ward_task", source="ward", category="care", description="Medication administration still outstanding.", urgency="amber", owner_role="nurse", owner_user_id=user_by_role["nurse"].id, section_name="Wards", room_name="Ward Cats", patient_location_label="Kennel C2", linked_patient_name="Pepper", linked_episode_ref="EP-1053", status="new"),
        WorkItem(title="Consult owner update overdue", input_type="consult_update", source="consult", category="owner_comms", description="Owner still awaiting consult outcome summary.", urgency="amber", owner_role="clinician", owner_user_id=user_by_role["clinician"].id, section_name="Consults", room_name="Consult Room 1", linked_patient_name="Poppy", linked_episode_ref="EP-1057", status="new"),
        WorkItem(title="Consult notes incomplete", input_type="consult_update", source="consult", category="documentation", description="Consult summary needs to be completed before next step.", urgency="amber", owner_role="clinician", owner_user_id=user_by_role["clinician"].id, section_name="Consults", room_name="Consult Room 2", linked_patient_name="Otis", linked_episode_ref="EP-1058", status="in_progress"),
        WorkItem(title="Consult follow-up task unassigned", input_type="consult_update", source="consult", category="follow_up", description="Follow-up booking and handoff not yet owned.", urgency="red", owner_role="admin", owner_user_id=user_by_role["admin"].id, section_name="Consults", room_name="Consult Room 1", linked_patient_name="Rosie", linked_episode_ref="EP-1059", status="new"),
        WorkItem(title="Report needs review", input_type="email", source="mail_ops", category="communications", description="Thread needs review and attachment to live episode.", urgency="red", owner_role="clinician", owner_user_id=user_by_role["clinician"].id, section_name="Imaging", room_name="Imaging Room", linked_patient_name="Luna", linked_episode_ref="EP-1045", status="new"),
        WorkItem(title="Schedule drift risk", input_type="procedure_update", source="theatre", category="timing", description="A current slot may overrun by 20 minutes.", urgency="red", owner_role="ops_manager", owner_user_id=user_by_role["ops_manager"].id, section_name="Theatres", room_name="Theatre 2", linked_episode_ref="EP-1048", status="new"),
        WorkItem(title="Recovery handoff incomplete", input_type="recovery_update", source="theatre", category="handoff", description="Post-op handoff is incomplete and discharge timing is unclear.", urgency="amber", owner_role="nurse", owner_user_id=user_by_role["nurse"].id, section_name="Recovery", room_name="Recovery Bay", patient_location_label="Bay 2", linked_patient_name="Rex", linked_episode_ref="EP-1055", status="new"),
        WorkItem(title="Theatre prep not ready", input_type="procedure_update", source="theatre", category="prep", description="Procedure cannot start until prep checklist is complete.", urgency="amber", owner_role="nurse", owner_user_id=user_by_role["nurse"].id, section_name="Theatres", room_name="Theatre 1", linked_patient_name="Bella", linked_episode_ref="EP-1056", status="in_progress"),
    ]
    for item in items:
        session.add(item)
    session.commit()

    threads = [
        MessageThread(episode_id=episode_by_ref["EP-1045"].id, source_type="email", subject="Imaging report for Luna", owner_role="clinician", owner_user_id=user_by_role["clinician"].id),
        MessageThread(episode_id=episode_by_ref["EP-1042"].id, source_type="internal_message", subject="Owner update for Milo discharge", owner_role="nurse", owner_user_id=user_by_role["nurse"].id),
    ]
    for thread in threads:
        session.add(thread)
    session.commit()

    thread_by_subject = {thread.subject: thread for thread in session.exec(select(MessageThread)).all()}
    for entry in [
        MessageEntry(thread_id=thread_by_subject["Imaging report for Luna"].id, sender_name="Imaging", direction="inbound", body="MRI report returned and requires clinician review.", material_decision_flag=True),
        MessageEntry(thread_id=thread_by_subject["Owner update for Milo discharge"].id, sender_name="Ward Nurse", direction="outbound", body="Owner updated that discharge is delayed pending clinician review.", material_decision_flag=True),
    ]:
        session.add(entry)

    session.commit()
    for item in session.exec(select(WorkItem)).all():
        session.add(AuditEvent(actor_name="System", action="seeded", entity_type="work_item", entity_id=item.id or 0, summary=f"Seeded work item: {item.title}"))
    session.commit()
