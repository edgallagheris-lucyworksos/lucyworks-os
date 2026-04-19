import pandas as pd

ADMISSION_FIELDS = [
    {"field": "case_id", "meaning": "linked case"},
    {"field": "admitted_to", "meaning": "ICU, ward, or other"},
    {"field": "admitted_at", "meaning": "admission time"},
    {"field": "status", "meaning": "active, transferred, or closed"},
]


def admission_schema_table():
    return pd.DataFrame(ADMISSION_FIELDS)
