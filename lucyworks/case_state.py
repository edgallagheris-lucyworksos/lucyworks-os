import os
from datetime import datetime

import pandas as pd

CASE_STATES_PATH = "exports/case_states.csv"
CASE_STATE_COLUMNS = ["case_id", "state", "owner", "note", "created_at"]
DEFAULT_STATES = [
    {"state": "ARRIVED", "meaning": "case created and logged"},
    {"state": "TRIAGED", "meaning": "triage complete"},
    {"state": "ADMITTED", "meaning": "admitted to ward or ICU"},
    {"state": "IN_PROGRESS", "meaning": "active diagnostics or treatment"},
    {"state": "RESULT_PENDING", "meaning": "awaiting review"},
    {"state": "DISCHARGE_BLOCKED", "meaning": "cannot discharge yet"},
    {"state": "READY_FOR_DISCHARGE", "meaning": "clinically ready"},
    {"state": "DISCHARGED", "meaning": "left hospital"},
]


def case_state_reference_table():
    return pd.DataFrame(DEFAULT_STATES)


def load_case_states():
    if os.path.exists(CASE_STATES_PATH):
        return pd.read_csv(CASE_STATES_PATH)
    return pd.DataFrame(columns=CASE_STATE_COLUMNS)


def save_case_states(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(CASE_STATES_PATH, index=False)


def append_case_state(case_id: str, state: str, owner: str = "system", note: str = ""):
    row = {
        "case_id": case_id,
        "state": state,
        "owner": owner,
        "note": note,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    df = load_case_states()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_case_states(df)
    return row


def latest_case_states():
    df = load_case_states()
    if df.empty:
        return df
    ordered = df.sort_values(["case_id", "created_at"])
    return ordered.groupby("case_id", as_index=False).tail(1).reset_index(drop=True)


def case_state_summary():
    df = latest_case_states()
    if df.empty:
        return pd.DataFrame(columns=["state", "count"])
    return df.groupby("state", as_index=False).size().rename(columns={"size": "count"})
