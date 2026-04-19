from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class CaseInput:
    case_id: str
    created_at: str
    mode: str
    clinic: str
    species: str
    procedure_type: str
    urgency_symptoms: List[str]
    owner_notes: str
    referring_vet: str
    patient_name: str
    weight_kg: float

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class TriageOutput:
    triage_score: int
    priority: str
    reasoning: List[str]
    red_flags: List[str]

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class EthicsOutput:
    ethics_flag: bool
    safeguarding_path: str
    ethics_notes: List[str]

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class RotaOutput:
    assigned_vet: str
    assigned_nurse: str
    skill_match_notes: List[str]
    rota_risk: str

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class DischargeDraft:
    internal_text: str
    client_summary: str

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class SeverityAssessment:
    severity: str
    reasons: List[str]
    system_action: str

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class StaffMember:
    staff_id: str
    full_name: str
    staff_type: str
    role_title: str
    team: str
    skills: List[str]
    active: bool = True

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class IntakeRecord:
    intake_id: str
    case_id: Optional[str]
    source_type: str
    source_name: str
    owner_name: str
    owner_phone: str
    urgency: str
    status: str
    notes: str

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class RoomStateRecord:
    room_id: str
    room_name: str
    room_type: str
    department: str
    state: str
    current_case_id: Optional[str]
    next_case_id: Optional[str]
    cleaning_due_minutes: Optional[int]

    def to_dict(self) -> Dict:
        return self.__dict__

@dataclass
class AlertRecord:
    alert_id: str
    alert_type: str
    severity: str
    case_id: Optional[str]
    owner: Optional[str]
    detail: str
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        return self.__dict__
