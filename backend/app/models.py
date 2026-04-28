from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    role: str
    email: str
    active: bool = True


class HospitalSection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    section_type: str
    active: bool = True


class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    section_name: str
    name: str
    room_type: str
    active: bool = True


class Patient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_name: str
    species: str
    owner_name: str
    owner_phone: Optional[str] = None
    weight_kg: Optional[float] = None


class Episode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_ref: str
    patient_id: int = Field(foreign_key="patient.id")
    status: str = "active"
    current_section_name: Optional[str] = None
    current_room_name: Optional[str] = None
    current_phase: str = "intake"
    created_at: datetime = Field(default_factory=utc_now)


class TriageAssessment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    species: str
    presenting_signs: str
    urgency: str
    route: str
    confidence: float = 0.75
    reasoning: str
    red_flags: str = ""
    advice_mode: str = "information_only"
    handoff_required: bool = False
    ethics_triggered: bool = False
    owner_contact_required: bool = False
    decision_required: bool = False
    assigned_owner_role: str = "clinician"
    status: str = "open"
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class EthicsFlag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    flag_type: str
    severity: str
    detail: str
    clinical_reasoning: str = ""
    owner_state: str = "unknown"
    decision_required: str = "senior_clinician_review"
    escalation_path: str = "clinician_to_ops_manager"
    owner_role: str = "clinician"
    status: str = "open"
    escalation_required: bool = True
    linked_work_item_id: Optional[int] = Field(default=None, foreign_key="workitem.id")
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


class DecisionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    decision_type: str
    decision_needed: str
    owner_role: str
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    section_name: Optional[str] = None
    status: str = "open"
    urgency: str = "amber"
    source: str = "manual"
    linked_work_item_id: Optional[int] = Field(default=None, foreign_key="workitem.id")
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None


class Blocker(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    blocker_type: str
    section_name: str
    detail: str
    impact: str
    urgency: str = "amber"
    owner_role: str
    status: str = "open"
    linked_decision_id: Optional[int] = Field(default=None, foreign_key="decisionrecord.id")
    linked_work_item_id: Optional[int] = Field(default=None, foreign_key="workitem.id")
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class EscalationEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    escalation_type: str
    severity: str
    reason: str
    from_role: str
    to_role: str
    status: str = "open"
    linked_blocker_id: Optional[int] = Field(default=None, foreign_key="blocker.id")
    linked_ethics_flag_id: Optional[int] = Field(default=None, foreign_key="ethicsflag.id")
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class LucyCareTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    task_type: str
    care_area: str
    detail: str
    owner_role: str
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    due_at: Optional[datetime] = None
    status: str = "open"
    escalation_required: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class OwnerCommsRequirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    reason: str
    required_message: str
    owner_role: str = "clinician"
    urgency: str = "amber"
    status: str = "due"
    linked_message_thread_id: Optional[int] = Field(default=None, foreign_key="messagethread.id")
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class PulseSignal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    signal_type: str
    section_name: str
    severity: str
    detail: str
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    source: str
    status: str = "open"
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class Admission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    admitted_to: str
    admitted_at: datetime = Field(default_factory=utc_now)
    status: str = "active"


class Handover(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    from_owner: str
    to_owner: str
    note: str
    acknowledged: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ResultReview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    result_type: str
    review_owner: str
    status: str = "pending_review"
    required_action: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class MessageThread(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    source_type: str
    subject: str
    owner_role: str
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    status: str = "open"
    created_at: datetime = Field(default_factory=utc_now)


class MessageEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="messagethread.id")
    sender_name: str
    direction: str
    body: str
    material_decision_flag: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class StaffMember(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    name: str
    role: str
    skills: str
    active: bool = True


class Shift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_member_id: int = Field(foreign_key="staffmember.id")
    department: str
    starts_at: datetime
    ends_at: datetime
    shift_type: str = "standard"
    status: str = "planned"


class ProcedureType(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    department: str
    default_duration_min: int
    prep_min: int
    anaesthesia_min: int
    recovery_min: int
    cleaning_min: int
    required_role: str
    required_room_type: str


class CaseProcedure(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    procedure_type_id: int = Field(foreign_key="proceduretype.id")
    status: str = "planned"
    scheduled_start: Optional[datetime] = None
    complexity: str = "standard"


class ScheduleBlock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    case_procedure_id: int = Field(foreign_key="caseprocedure.id")
    block_type: str
    room_name: Optional[str] = None
    owner_role: Optional[str] = None
    assigned_staff_member_id: Optional[int] = Field(default=None, foreign_key="staffmember.id")
    starts_at: datetime
    ends_at: datetime
    status: str = "planned"


class RoomState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_name: str
    room_type: str
    department: str
    state: str
    current_episode_ref: Optional[str] = None
    next_episode_ref: Optional[str] = None
    cleaning_due_minutes: Optional[int] = None


class ConflictAction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conflict_type: str
    severity: str
    detail: str
    status: str = "open"
    linked_work_item_id: Optional[int] = Field(default=None, foreign_key="workitem.id")
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class WorkItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    input_type: str
    source: str
    category: str
    description: str
    urgency: str
    owner_role: str
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    section_name: Optional[str] = None
    room_name: Optional[str] = None
    patient_location_label: Optional[str] = None
    linked_patient_name: Optional[str] = None
    linked_episode_ref: Optional[str] = None
    status: str = "new"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    due_at: Optional[datetime] = None


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_name: str
    action: str
    entity_type: str
    entity_id: int
    summary: str
    created_at: datetime = Field(default_factory=utc_now)
