from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LoginDemoRequest(BaseModel):
    user_id: int


class WorkItemCreate(BaseModel):
    title: str
    input_type: str
    source: str
    category: str
    description: str
    urgency: str
    owner_role: str
    owner_user_id: Optional[int] = None
    section_name: Optional[str] = None
    room_name: Optional[str] = None
    patient_location_label: Optional[str] = None
    linked_patient_name: Optional[str] = None
    linked_episode_ref: Optional[str] = None
    due_at: Optional[datetime] = None


class WorkItemAssign(BaseModel):
    owner_role: str
    owner_user_id: Optional[int] = None
    actor_name: str = "System"


class WorkItemStatusUpdate(BaseModel):
    status: str
    actor_name: str = "System"


class ScheduleGenerateRequest(BaseModel):
    episode_ref: str
    procedure_type_id: int
    room_name: str
    start_time: datetime
    actor_name: str = "System"


class ScheduleShiftRequest(BaseModel):
    minutes: int
    actor_name: str = "System"


class ResultActionRequest(BaseModel):
    status: str
    actor_name: str = "System"
    required_action: Optional[str] = None


class MessageThreadCreate(BaseModel):
    episode_ref: Optional[str] = None
    source_type: str
    subject: str
    owner_role: str
    owner_user_id: Optional[int] = None


class MessageEntryCreate(BaseModel):
    sender_name: str
    direction: str
    body: str
    material_decision_flag: bool = False
    actor_name: str = "System"


class StaffAllocateRequest(BaseModel):
    schedule_block_id: int
    staff_member_id: int
    actor_name: str = "System"
