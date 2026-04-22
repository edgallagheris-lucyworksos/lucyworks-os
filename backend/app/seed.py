from sqlmodel import Session, select

from app.models import AuditEvent, HospitalSection, Room, User, WorkItem


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

    items = [
        WorkItem(
            title="Communication update needed",
            input_type="discharge_blocker",
            source="ward",
            category="care",
            description="Owner update is still outstanding.",
            urgency="amber",
            owner_role="nurse",
            owner_user_id=user_by_role["nurse"].id,
            section_name="Wards",
            room_name="Ward Dogs",
            patient_location_label="Kennel B4",
            linked_patient_name="Milo",
            linked_episode_ref="EP-1042",
            status="in_progress",
        ),
        WorkItem(
            title="ICU monitoring review overdue",
            input_type="inpatient_update",
            source="ward",
            category="critical_care",
            description="Observation review needs clinician confirmation.",
            urgency="red",
            owner_role="clinician",
            owner_user_id=user_by_role["clinician"].id,
            section_name="ICU",
            room_name="ICU Bay Area",
            patient_location_label="Bay A",
            linked_patient_name="Nova",
            linked_episode_ref="EP-1051",
            status="new",
        ),
        WorkItem(
            title="Ward medication task not completed",
            input_type="ward_task",
            source="ward",
            category="care",
            description="Medication administration still outstanding.",
            urgency="amber",
            owner_role="nurse",
            owner_user_id=user_by_role["nurse"].id,
            section_name="Wards",
            room_name="Ward Cats",
            patient_location_label="Kennel C2",
            linked_patient_name="Pepper",
            linked_episode_ref="EP-1053",
            status="new",
        ),
        WorkItem(
            title="Consult owner update overdue",
            input_type="consult_update",
            source="consult",
            category="owner_comms",
            description="Owner still awaiting consult outcome summary.",
            urgency="amber",
            owner_role="clinician",
            owner_user_id=user_by_role["clinician"].id,
            section_name="Consults",
            room_name="Consult Room 1",
            linked_patient_name="Poppy",
            linked_episode_ref="EP-1057",
            status="new",
        ),
        WorkItem(
            title="Consult notes incomplete",
            input_type="consult_update",
            source="consult",
            category="documentation",
            description="Consult summary needs to be completed before next step.",
            urgency="amber",
            owner_role="clinician",
            owner_user_id=user_by_role["clinician"].id,
            section_name="Consults",
            room_name="Consult Room 2",
            linked_patient_name="Otis",
            linked_episode_ref="EP-1058",
            status="in_progress",
        ),
        WorkItem(
            title="Consult follow-up task unassigned",
            input_type="consult_update",
            source="consult",
            category="follow_up",
            description="Follow-up booking and handoff not yet owned.",
            urgency="red",
            owner_role="admin",
            owner_user_id=user_by_role["admin"].id,
            section_name="Consults",
            room_name="Consult Room 1",
            linked_patient_name="Rosie",
            linked_episode_ref="EP-1059",
            status="new",
        ),
        WorkItem(
            title="Report needs review",
            input_type="email",
            source="mail_ops",
            category="communications",
            description="Thread needs review and attachment to live episode.",
            urgency="red",
            owner_role="clinician",
            owner_user_id=user_by_role["clinician"].id,
            section_name="Imaging",
            room_name="Imaging Room",
            linked_patient_name="Luna",
            linked_episode_ref="EP-1045",
            status="new",
        ),
        WorkItem(
            title="Schedule drift risk",
            input_type="procedure_update",
            source="theatre",
            category="timing",
            description="A current slot may overrun by 20 minutes.",
            urgency="red",
            owner_role="ops_manager",
            owner_user_id=user_by_role["ops_manager"].id,
            section_name="Theatres",
            room_name="Theatre 2",
            linked_episode_ref="EP-1048",
            status="new",
        ),
        WorkItem(
            title="Recovery handoff incomplete",
            input_type="recovery_update",
            source="theatre",
            category="handoff",
            description="Post-op handoff is incomplete and discharge timing is unclear.",
            urgency="amber",
            owner_role="nurse",
            owner_user_id=user_by_role["nurse"].id,
            section_name="Recovery",
            room_name="Recovery Bay",
            patient_location_label="Bay 2",
            linked_patient_name="Rex",
            linked_episode_ref="EP-1055",
            status="new",
        ),
        WorkItem(
            title="Theatre prep not ready",
            input_type="procedure_update",
            source="theatre",
            category="prep",
            description="Procedure cannot start until prep checklist is complete.",
            urgency="amber",
            owner_role="nurse",
            owner_user_id=user_by_role["nurse"].id,
            section_name="Theatres",
            room_name="Theatre 1",
            linked_patient_name="Bella",
            linked_episode_ref="EP-1056",
            status="in_progress",
        ),
    ]
    for item in items:
        session.add(item)
    session.commit()

    created_items = session.exec(select(WorkItem)).all()
    for item in created_items:
        session.add(
            AuditEvent(
                actor_name="System",
                action="seeded",
                entity_type="work_item",
                entity_id=item.id or 0,
                summary=f"Seeded work item: {item.title}",
            )
        )
    session.commit()
