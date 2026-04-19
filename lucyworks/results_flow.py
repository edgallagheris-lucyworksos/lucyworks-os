import os
import pandas as pd

RESULTS_PATH = "exports/results.csv"
RESULT_FIELDS = [
    {"field": "result_type", "meaning": "imaging, lab, or procedure"},
    {"field": "case_id", "meaning": "linked case"},
    {"field": "review_owner", "meaning": "clinician responsible"},
    {"field": "status", "meaning": "pending_review, reviewed, or actioned"},
    {"field": "reviewed_at", "meaning": "review timestamp"},
]
RESULT_COLUMNS = ["case_id", "result_type", "review_owner", "status", "reviewed_at"]


def result_schema_table():
    return pd.DataFrame(RESULT_FIELDS)


def load_results():
    if os.path.exists(RESULTS_PATH):
        return pd.read_csv(RESULTS_PATH)
    return pd.DataFrame(columns=RESULT_COLUMNS)


def save_results(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(RESULTS_PATH, index=False)


def append_result(case_id: str, result_type: str, review_owner: str, status: str = "pending_review"):
    row = {
        "case_id": case_id,
        "result_type": result_type,
        "review_owner": review_owner,
        "status": status,
        "reviewed_at": "",
    }
    df = load_results()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_results(df)
    return row
