from lucyworks.models import CaseInput, TriageOutput

PROCEDURE_BASE = {
    "TPLO": 3,
    "Dental": 2,
    "Castration": 1,
    "Neuro_Spine": 4,
    "Soft_Tissue": 2,
    "Rabbit_GA": 3,
    "Other": 2
}

SYMPTOM_WEIGHTS = {
    "Collapse": 2,
    "Respiratory distress": 3,
    "Uncontrolled bleeding": 3,
    "Non-weight bearing lameness": 1,
    "Seizures": 3,
    "Pale gums": 2,
    "Severe pain": 2,
    "Vomiting": 1,
    "Diarrhoea": 1,
    "Lethargy": 1
}

SPECIES_MOD = {"Dog": 0, "Cat": 0, "Rabbit": 1}

def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))

def run_triage(case: CaseInput) -> TriageOutput:
    reasoning = []
    red_flags = []

    base = PROCEDURE_BASE.get(case.procedure_type, 2)
    reasoning.append(f"Base acuity from procedure '{case.procedure_type}' = {base}")

    symptom_score = 0
    for symptom in case.urgency_symptoms:
        weight = SYMPTOM_WEIGHTS.get(symptom, 0)
        symptom_score += weight
        if weight:
            reasoning.append(f"Symptom '{symptom}' adds {weight}")

    species_mod = SPECIES_MOD.get(case.species, 0)
    if species_mod:
        reasoning.append(f"Species modifier '{case.species}' adds {species_mod}")

    raw = base + symptom_score + species_mod

    if "Respiratory distress" in case.urgency_symptoms:
        red_flags.append("AIRWAY_BREATHING_RISK")
    if "Uncontrolled bleeding" in case.urgency_symptoms:
        red_flags.append("HAEMORRHAGE_RISK")
    if "Seizures" in case.urgency_symptoms:
        red_flags.append("NEURO_EMERGENCY_RISK")
    if case.weight_kg <= 0:
        red_flags.append("DATA_QUALITY_WEIGHT_INVALID")

    score = clamp(raw // 2 + 1, 1, 5)

    if score >= 5:
        priority = "Emergency"
    elif score >= 3:
        priority = "Urgent"
    else:
        priority = "Routine"

    reasoning.append(f"Raw={raw} -> triage_score={score} -> priority={priority}")
    return TriageOutput(score, priority, reasoning, red_flags)
