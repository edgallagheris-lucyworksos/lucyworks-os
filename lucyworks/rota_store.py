import os
import pandas as pd

STAFF_PATH = "assets/staff.csv"
ROTA_PATH = "assets/rota.csv"
ASSIGNMENTS_PATH = "exports/assignments.csv"


def load_staff():
    if os.path.exists(STAFF_PATH):
        return pd.read_csv(STAFF_PATH)
    return pd.DataFrame(columns=["staff_id", "name", "role", "skills", "max_cases_per_day", "current_load", "active"])


def load_rota():
    if os.path.exists(ROTA_PATH):
        return pd.read_csv(ROTA_PATH)
    return pd.DataFrame(columns=["date", "shift", "staff_id", "role", "team", "notes"])


def load_assignments():
    if os.path.exists(ASSIGNMENTS_PATH):
        return pd.read_csv(ASSIGNMENTS_PATH)
    return pd.DataFrame(columns=[
        "date", "case_id", "species", "procedure_type", "priority",
        "triage_score", "assigned_vet_id", "assigned_nurse_id",
        "rota_risk", "safeguarding_path"
    ])


def save_assignments(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(ASSIGNMENTS_PATH, index=False)


def append_assignment(row: dict):
    df = load_assignments()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_assignments(df)


def get_master_rota(date_from=None, date_to=None):
    df = load_rota()
    if date_from is not None:
        df = df[df["date"] >= str(date_from)]
    if date_to is not None:
        df = df[df["date"] <= str(date_to)]
    return df


def get_staff_schedule(staff_id: str, date_from=None, date_to=None):
    df = load_rota()
    df = df[df["staff_id"] == staff_id]
    if date_from is not None:
        df = df[df["date"] >= str(date_from)]
    if date_to is not None:
        df = df[df["date"] <= str(date_to)]
    return df
