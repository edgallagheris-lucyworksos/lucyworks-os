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
