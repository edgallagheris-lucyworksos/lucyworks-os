import pandas as pd

PROCEDURES = [
    {"code": "TPLO", "name": "TPLO", "category": "orthopaedics", "expected_minutes": 120, "prep_minutes": 30, "recovery_minutes": 60, "cleaning_minutes": 20},
    {"code": "DENTAL", "name": "Dental", "category": "dental", "expected_minutes": 60, "prep_minutes": 20, "recovery_minutes": 30, "cleaning_minutes": 15},
    {"code": "CASTRATION", "name": "Castration", "category": "soft_tissue", "expected_minutes": 45, "prep_minutes": 20, "recovery_minutes": 30, "cleaning_minutes": 15},
    {"code": "NEURO_SPINE", "name": "Neuro Spine", "category": "neuro", "expected_minutes": 180, "prep_minutes": 40, "recovery_minutes": 60, "cleaning_minutes": 30},
]


def procedure_library_table():
    return pd.DataFrame(PROCEDURES)
