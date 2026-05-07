def canonical_triage_case(data: dict) -> str:
    condition = (data.get("condition") or data.get("presenting_problem") or "").lower()
    duration = data.get("duration", data.get("duration_days", 0)) or 0
    ethics_flag = bool(data.get("ethics_flag", False))

    if condition in ["collapse", "seizure"]:
        return "emergency"
    if condition in ["vomiting", "limping"] and duration < 2:
        return "urgent"
    if ethics_flag:
        return "review_required"
    return "routine"


TRIAGE_TO_URGENCY = {
    "emergency": "red",
    "urgent": "amber",
    "review_required": "amber",
    "routine": "green",
}


def urgency_from_triage(result: str) -> str:
    return TRIAGE_TO_URGENCY.get(result, "green")
