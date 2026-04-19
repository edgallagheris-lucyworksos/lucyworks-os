import pandas as pd
from lucyworks.models import CaseInput, TriageOutput, RotaOutput


def parse_skills(skills: str) -> set:
    return set(part.strip() for part in str(skills).split(",") if part.strip())


def pick_staff(staff: pd.DataFrame, role: str, required_skills: list):
    req = set(required_skills)
    pool = staff[staff["role"] == role].copy()

    if pool.empty:
        return "UNASSIGNED", ["No available staff for role: " + role], "HIGH"

    pool["skill_set"] = pool["skills"].apply(parse_skills)
    pool["skill_match"] = pool["skill_set"].apply(lambda values: len(req.intersection(values)))
    pool["load_ratio"] = pool["current_load"] / pool["max_cases_per_day"].replace(0, 1)
    pool = pool.sort_values(["skill_match", "load_ratio"], ascending=[False, True])

    best = pool.iloc[0]
    risk = "LOW" if best["load_ratio"] < 0.7 else "MED"
    if best["skill_match"] == 0:
        risk = "HIGH"

    notes = [
        "Assigned " + str(best["name"]) + " (" + role + ")",
        "Skill match=" + str(best["skill_match"]),
        "Load ratio=" + format(best["load_ratio"], ".2f"),
    ]
    return best["name"], notes, risk


def rota_assign(staff: pd.DataFrame, case: CaseInput, triage_out: TriageOutput) -> RotaOutput:
    vet_skills = ["Surgery"]
    nurse_skills = ["Theatre"]

    if case.procedure_type == "TPLO":
        vet_skills += ["Ortho", "TPLO"]
        nurse_skills += ["Surgery"]
    elif case.procedure_type == "Dental":
        vet_skills += ["Dental"]
        nurse_skills += ["Dental"]
    elif case.procedure_type == "Neuro_Spine":
        vet_skills += ["Neuro"]
        nurse_skills += ["Neuro", "Surgery"]
    elif case.species == "Rabbit":
        nurse_skills += ["Rabbit"]

    vet_name, vet_notes, vet_risk = pick_staff(staff, "Vet", vet_skills)
    nurse_name, nurse_notes, nurse_risk = pick_staff(staff, "Nurse", nurse_skills)

    if "HIGH" in [vet_risk, nurse_risk]:
        rota_risk = "HIGH"
    elif "MED" in [vet_risk, nurse_risk]:
        rota_risk = "MED"
    else:
        rota_risk = "LOW"

    return RotaOutput(
        assigned_vet=vet_name,
        assigned_nurse=nurse_name,
        skill_match_notes=vet_notes + nurse_notes,
        rota_risk=rota_risk,
    )
