from lucyworks.models import CaseInput, TriageOutput, RotaOutput, DischargeDraft


def build_discharge(case: CaseInput, triage_out: TriageOutput, rota_out: RotaOutput) -> DischargeDraft:
    lines = [
        "DISCHARGE (DRAFT) - LucyWorks",
        "Case ID: " + case.case_id,
        "Patient: " + case.patient_name + " (" + case.species + ")",
        "Procedure: " + case.procedure_type,
        "Priority: " + triage_out.priority,
        "Assigned Vet: " + rota_out.assigned_vet,
        "Assigned Nurse: " + rota_out.assigned_nurse,
        "",
        "Reasoning:",
    ]
    lines.extend(["- " + line for line in triage_out.reasoning])
    internal = "\n".join(lines)

    client_lines = [
        "Patient: " + case.patient_name + " (" + case.species + ")",
        "Procedure / Reason: " + case.procedure_type,
        "Priority: " + triage_out.priority,
        "",
        "At-home care (editable):",
        "- Follow clinician instructions for rest, feeding, and medication.",
        "- Monitor comfort, appetite, and toileting.",
        "- Seek urgent advice if collapse, breathing difficulty, bleeding, or seizures occur.",
    ]
    client_summary = "\n".join(client_lines)
    return DischargeDraft(internal, client_summary)
