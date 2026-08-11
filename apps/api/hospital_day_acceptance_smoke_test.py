from app.hospital_day_acceptance import evaluate_hospital_day


def scenario(kind: str, *, severity: str = "amber", **extra):
    row = {
        "scenarioType": kind,
        "severity": severity,
        "detected": True,
        "acknowledged": True,
        "ackSeconds": 60,
        "ownerRole": "ops_manager",
        "unsafeContinuationBlocked": severity in {"red", "critical"},
        "clientCommunicationRequired": False,
        "clientCommunicationCompleted": True,
        "chargeReconciled": True,
        "staffConflictSurfaced": True,
    }
    row.update(extra)
    return row


healthy = [
    scenario("emergency_arrival", severity="critical", ownerRole="clinical_director", handoverRequired=True, handoverCompleted=True),
    scenario("theatre_overrun", severity="red", clientCommunicationRequired=True, clientCommunicationCompleted=True),
    scenario("staffing_gap", severity="red", ownerRole="ops_manager", handoverRequired=True, handoverCompleted=True),
    scenario("imaging_delay", severity="amber", clientCommunicationRequired=True, clientCommunicationCompleted=True),
    scenario("estimate_overrun", severity="amber", estimateUpdateRequired=True, estimateUpdateCompleted=True, clientCommunicationRequired=True, clientCommunicationCompleted=True),
    scenario("critical_result", severity="critical", ownerRole="senior_clinician", handoverRequired=True, handoverCompleted=True),
]

result = evaluate_hospital_day(scenarios=healthy)
assert result["status"] == "PASS", result
assert result["decision"] == "GO", result
assert all(value["passed"] for value in result["dimensions"].values()), result

unsafe = [dict(item) for item in healthy]
unsafe[-1]["unsafeContinuationBlocked"] = False
unsafe[-1]["ackSeconds"] = 601
result = evaluate_hospital_day(scenarios=unsafe)
assert result["status"] == "FAIL", result
assert result["decision"] == "NO_GO", result
assert not result["dimensions"]["patientSafety"]["passed"], result

client_failure = [dict(item) for item in healthy]
client_failure[4]["estimateUpdateCompleted"] = False
result = evaluate_hospital_day(scenarios=client_failure)
assert result["status"] == "FAIL", result
assert not result["dimensions"]["clientClarity"]["passed"], result

commercial_failure = [dict(item) for item in healthy]
commercial_failure[1]["chargeReconciled"] = False
result = evaluate_hospital_day(scenarios=commercial_failure)
assert result["status"] == "FAIL", result
assert not result["dimensions"]["commercialControl"]["passed"], result

missing = evaluate_hospital_day(scenarios=healthy[:-1])
assert missing["status"] == "FAIL", missing
assert any("Missing required hospital-day scenarios" in item for item in missing["blockers"]), missing

print("HOSPITAL_DAY_ACCEPTANCE_OK")
