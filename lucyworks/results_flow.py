import pandas as pd

RESULT_FIELDS = [
    {"field": "result_type", "meaning": "imaging, lab, or procedure"},
    {"field": "case_id", "meaning": "linked case"},
    {"field": "review_owner", "meaning": "clinician responsible"},
    {"field": "status", "meaning": "pending_review, reviewed, or actioned"},
    {"field": "reviewed_at", "meaning": "review timestamp"},
]


def result_schema_table():
    return pd.DataFrame(RESULT_FIELDS)
