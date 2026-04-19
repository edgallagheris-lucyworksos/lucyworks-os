from lucyworks.models import CaseInput, TriageOutput, EthicsOutput

def run_ethics(case: CaseInput, triage_out: TriageOutput) -> EthicsOutput:
    notes = []
    ethics_flag = False
    safeguarding_path = "NONE"

    critical_flags = {
        "AIRWAY_BREATHING_RISK",
        "HAEMORRHAGE_RISK",
        "NEURO_EMERGENCY_RISK",
        "DATA_QUALITY_WEIGHT_INVALID"
    }

    if any(flag in critical_flags for flag in triage_out.red_flags):
        ethics_flag = True
        safeguarding_path = "ESCALATE"
        notes.append("Critical red flag present -> safeguarding escalation required.")

    owner_keywords = [
        "threat",
        "aggressive",
        "refused",
        "no consent",
        "won't consent",
        "refusing"
    ]

    if any(word in case.owner_notes.lower() for word in owner_keywords):
        ethics_flag = True
        safeguarding_path = "ESCALATE"
        notes.append("Owner/consent risk keyword detected -> escalate for review.")

    if not notes:
        notes = ["No ethics escalation triggered."]

    return EthicsOutput(ethics_flag, safeguarding_path, notes)
