import pandas as pd

DRUGS = [
    {"drug_code": "MELOXICAM", "name": "Meloxicam", "category": "NSAID", "form": "oral", "controlled": False},
    {"drug_code": "METHADONE", "name": "Methadone", "category": "opioid", "form": "injectable", "controlled": True},
    {"drug_code": "PROPOFOL", "name": "Propofol", "category": "anaesthetic", "form": "injectable", "controlled": False},
    {"drug_code": "ALFAXALONE", "name": "Alfaxalone", "category": "anaesthetic", "form": "injectable", "controlled": False},
]


def drug_database_table():
    return pd.DataFrame(DRUGS)
