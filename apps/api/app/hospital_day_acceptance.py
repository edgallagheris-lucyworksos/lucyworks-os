from __future__ import annotations

from typing import Any

REQUIRED_SCENARIOS = {
    "emergency_arrival",
    "theatre_overrun",
    "staffing_gap",
    "imaging_delay",
    "estimate_overrun",
    "critical_result",
}

CRITICAL_ACK_SECONDS = 300
HIGH_RISK_ACK_SECONDS = 900


def evaluate_hospital_day(*, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate whether a simulated/reflected referral-hospital day is safe enough for pilot progression.

    The evaluator intentionally scores patient safety, client clarity, staff control and
    commercial reconciliation separately. A commercial pass can never cancel a safety fail.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    by_type = {str(item.get("scenarioType")): item for item in scenarios if item.get("scenarioType")}

    missing = sorted(REQUIRED_SCENARIOS - set(by_type))
    if missing:
        blockers.append(f"Missing required hospital-day scenarios: {', '.join(missing)}")

    patient = {"passed": True, "findings": []}
    client = {"passed": True, "findings": []}
    staff = {"passed": True, "findings": []}
    commercial = {"passed": True, "findings": []}

    for scenario in scenarios:
        kind = str(scenario.get("scenarioType") or "unknown")
        severity = str(scenario.get("severity") or "amber").lower()
        detected = bool(scenario.get("detected"))
        acknowledged = bool(scenario.get("acknowledged"))
        ack_seconds = scenario.get("ackSeconds")
        owner_role = str(scenario.get("ownerRole") or "").strip()
        safe_block = bool(scenario.get("unsafeContinuationBlocked"))
        client_required = bool(scenario.get("clientCommunicationRequired"))
        client_done = bool(scenario.get("clientCommunicationCompleted"))
        charge_reconciled = bool(scenario.get("chargeReconciled", True))
        estimate_required = bool(scenario.get("estimateUpdateRequired"))
        estimate_done = bool(scenario.get("estimateUpdateCompleted"))
        unresolved = bool(scenario.get("unresolvedHighRisk"))

        if not detected:
            patient["passed"] = False
            patient["findings"].append(f"{kind}: operational risk was not detected")
        if severity in {"red", "critical"}:
            if not acknowledged:
                patient["passed"] = False
                patient["findings"].append(f"{kind}: high-risk event was not acknowledged")
            elif isinstance(ack_seconds, (int, float)):
                limit = CRITICAL_ACK_SECONDS if severity == "critical" else HIGH_RISK_ACK_SECONDS
                if ack_seconds > limit:
                    patient["passed"] = False
                    patient["findings"].append(f"{kind}: acknowledgement took {ack_seconds}s (limit {limit}s)")
            else:
                patient["passed"] = False
                patient["findings"].append(f"{kind}: acknowledgement latency was not measured")
            if not safe_block:
                patient["passed"] = False
                patient["findings"].append(f"{kind}: unsafe continuation was not blocked")
        if unresolved:
            patient["passed"] = False
            patient["findings"].append(f"{kind}: unresolved high-risk state remained at end of run")

        if not owner_role:
            staff["passed"] = False
            staff["findings"].append(f"{kind}: no accountable owner role")
        if scenario.get("staffConflictSurfaced") is False:
            staff["passed"] = False
            staff["findings"].append(f"{kind}: staff/resource conflict was not surfaced")
        if scenario.get("handoverRequired") and not scenario.get("handoverCompleted"):
            staff["passed"] = False
            staff["findings"].append(f"{kind}: required handover was not completed")

        if client_required and not client_done:
            client["passed"] = False
            client["findings"].append(f"{kind}: required client communication was not completed")
        if estimate_required and not estimate_done:
            client["passed"] = False
            client["findings"].append(f"{kind}: required written estimate update was not completed")

        if not charge_reconciled:
            commercial["passed"] = False
            commercial["findings"].append(f"{kind}: performed work was not reconciled to charge evidence")
        if scenario.get("supplierCostKnown") and not scenario.get("supplierCostCaptured"):
            commercial["passed"] = False
            commercial["findings"].append(f"{kind}: known supplier cost was not captured")

    dimensions = {
        "patientSafety": patient,
        "clientClarity": client,
        "staffControl": staff,
        "commercialControl": commercial,
    }
    for name, result in dimensions.items():
        if not result["passed"]:
            blockers.extend(f"{name}: {finding}" for finding in result["findings"])

    if commercial["passed"] and not patient["passed"]:
        warnings.append("Commercial controls passed, but patient-safety failure still makes the run NO_GO.")

    status = "PASS" if not blockers else "FAIL"
    decision = "GO" if status == "PASS" else "NO_GO"
    return {
        "status": status,
        "decision": decision,
        "scenarioCount": len(scenarios),
        "requiredScenarioCount": len(REQUIRED_SCENARIOS),
        "dimensions": dimensions,
        "blockers": blockers,
        "warnings": warnings,
        "releaseBoundary": "A PASS is evidence for bounded shadow/read-only pilot progression only; it is not proof of live clinical production readiness.",
    }
