import statistics
from typing import Any


class LucyFlowEngine:
    def __init__(self, case_data: dict[str, Any]):
        self.case_data = case_data

    def route(self) -> str:
        urgency = (self.case_data.get("urgency") or "").lower()
        if urgency == "red":
            return "Escalate to Ethics"
        if urgency == "amber":
            return "Review by Senior Nurse"
        return "Assign to Vet Team"


class LucyPulseMonitor:
    def __init__(self, stress_scores: list[float]):
        self.scores = stress_scores

    def check_alerts(self) -> str:
        if not self.scores:
            return "NORMAL"
        avg = statistics.mean(self.scores)
        if avg > 80:
            return "CRITICAL"
        if avg > 60:
            return "WARNING"
        return "NORMAL"


class LucyRotaAssigner:
    def __init__(self, staff_list: list[dict[str, Any]]):
        self.staff = staff_list

    def assign_shift(self, date: str, role: str) -> str:
        for person in self.staff:
            certifications = person.get("certifications") or []
            availability = person.get("availability") or []
            if role in certifications and date in availability:
                return person.get("staff_name", "Unknown")
        return "No Match Found"


def flow_route_for_urgency(urgency: str) -> str:
    return LucyFlowEngine({"urgency": urgency}).route()


def pulse_status_from_scores(scores: list[float]) -> str:
    return LucyPulseMonitor(scores).check_alerts()


def rota_match(staff_list: list[dict[str, Any]], date: str, role: str) -> str:
    return LucyRotaAssigner(staff_list).assign_shift(date, role)
