import os
import pandas as pd

DRUGS_PATH = "assets/drugs.csv"
DEFAULT_DRUGS = [
    {"drug_code": "MELOXICAM", "name": "Meloxicam", "category": "NSAID", "form": "oral", "controlled": False},
    {"drug_code": "METHADONE", "name": "Methadone", "category": "opioid", "form": "injectable", "controlled": True},
    {"drug_code": "PROPOFOL", "name": "Propofol", "category": "anaesthetic", "form": "injectable", "controlled": False},
    {"drug_code": "ALFAXALONE", "name": "Alfaxalone", "category": "anaesthetic", "form": "injectable", "controlled": False},
]


def load_drug_database():
    if os.path.exists(DRUGS_PATH):
        return pd.read_csv(DRUGS_PATH)
    return pd.DataFrame(DEFAULT_DRUGS)


def drug_database_table():
    return load_drug_database()


def get_drug(drug_code: str):
    df = load_drug_database()
    match = df[df["drug_code"] == drug_code]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def controlled_drug_table():
    df = load_drug_database()
    if "controlled" not in df.columns:
        return df.head(0)
    return df[df["controlled"].astype(str).str.lower().isin(["true", "1"])]
