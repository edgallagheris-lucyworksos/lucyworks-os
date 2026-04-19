import os
import pandas as pd

PROCEDURES_PATH = "assets/procedures.csv"
DEFAULT_PROCEDURES = [
    {"code": "TPLO", "name": "TPLO", "category": "orthopaedics", "expected_minutes": 120, "prep_minutes": 30, "recovery_minutes": 60, "cleaning_minutes": 20},
    {"code": "DENTAL", "name": "Dental", "category": "dental", "expected_minutes": 60, "prep_minutes": 20, "recovery_minutes": 30, "cleaning_minutes": 15},
    {"code": "CASTRATION", "name": "Castration", "category": "soft_tissue", "expected_minutes": 45, "prep_minutes": 20, "recovery_minutes": 30, "cleaning_minutes": 15},
    {"code": "NEURO_SPINE", "name": "Neuro Spine", "category": "neuro", "expected_minutes": 180, "prep_minutes": 40, "recovery_minutes": 60, "cleaning_minutes": 30},
]


def load_procedure_library():
    if os.path.exists(PROCEDURES_PATH):
        return pd.read_csv(PROCEDURES_PATH)
    return pd.DataFrame(DEFAULT_PROCEDURES)


def procedure_library_table():
    return load_procedure_library()


def get_procedure(code: str):
    df = load_procedure_library()
    match = df[df["code"] == code]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def procedure_duration_summary():
    df = load_procedure_library().copy()
    if df.empty:
        return df
    df["total_cycle_minutes"] = df["expected_minutes"] + df["prep_minutes"] + df["recovery_minutes"] + df["cleaning_minutes"]
    return df[["code", "name", "total_cycle_minutes"]]
