from sqlmodel import Session, select

from app.models import AuditEvent, User, WorkItem


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
            linked_patient_name="Milo",
            linked_episode_ref="EP-1042",
            status="in_progress",
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
            linked_episode_ref="EP-1048",
            status="new",
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
