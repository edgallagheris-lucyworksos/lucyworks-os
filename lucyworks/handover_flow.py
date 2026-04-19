import pandas as pd

HANDOVER_FIELDS = [
    {"field": "from_owner", "meaning": "sending clinician or team"},
    {"field": "to_owner", "meaning": "receiving clinician or team"},
    {"field": "case_id", "meaning": "linked case"},
    {"field": "note", "meaning": "handover note"},
    {"field": "acknowledged", "meaning": "receiving owner has acknowledged"},
]


def handover_schema_table():
    return pd.DataFrame(HANDOVER_FIELDS)
