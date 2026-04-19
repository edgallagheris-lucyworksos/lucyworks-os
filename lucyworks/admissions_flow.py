import os
from datetime import datetime

import pandas as pd

ADMISSIONS_PATH = "exports/admissions.csv"
ADMISSION_FIELDS = [
    {"field": "case_id", "meaning": "linked case"},
    {"field": "admitted_to", "meaning": "ICU, ward, or other"},
    {"field": "admitted_at", "meaning": "admission time"},
    {"field": "status", "meaning": "active, transferred, or closed"},
]
ADMISSION_COLUMNS = ["case_id", "admitted_to", "admitted_at", "status"]


def admission_schema_table():
    return pd.DataFrame(ADMISSION_FIELDS)


def load_admissions():
    if os.path.exists(ADMISSIONS_PATH):
        return pd.read_csv(ADMISSIONS_PATH)
    return pd.DataFrame(columns=ADMISSION_COLUMNS)


def save_admissions(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(ADMISSIONS_PATH, index=False)


def append_admission(case_id: str, admitted_to: str, status: str = "active"):
    row = {
        "case_id": case_id,
        "admitted_to": admitted_to,
        "admitted_at": datetime.utcnow().isoformat() + "Z",
        "status": status,
    }
    df = load_admissions()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_admissions(df)
    return row
