from lucyworks.models import SeverityAssessment


def assess_severity(triage_out, ethics_out, rota_out):
    reasons = []
    severity = "MINOR"

    if triage_out.red_flags:
        severity = "CRITICAL"
        reasons.append("Critical triage red flag present.")
    if ethics_out.safeguarding_path == "ESCALATE":
        severity = "CRITICAL"
        reasons.append("Safeguarding escalation required.")
    elif rota_out.rota_risk == "HIGH":
        severity = "MODERATE"
        reasons.append("Rota risk is HIGH.")

    action = {
        "MINOR": "Log and proceed.",
        "MODERATE": "Require reviewer identity and reason if overriding.",
        "CRITICAL": "Block LIVE until safeguarding acknowledged.",
    }[severity]

    return SeverityAssessment(severity, reasons or ["No severity triggers"], action)
