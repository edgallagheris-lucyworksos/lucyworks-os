import os
from datetime import datetime

import pandas as pd

DISCHARGE_BLOCKERS_PATH = "exports/discharge_blockers.csv"
DISCHARGE_BLOCKERS = [
    {"blocker": "meds_not_ready", "meaning": "medication outstanding"},
    {"blocker": "review_pending", "meaning": "clinical review not signed"},
    {"blocker": "owner_not_contacted", "meaning": "owner communication incomplete"},
    {"blocker": "notes_incomplete", "meaning": "documentation incomplete"},
]
BLOCKER_COLUMNS = ["case_id", "blocker", "status", "created_at"]


def discharge_blocker_table():
    return pd.DataFrame(DISCHARGE_BLOCKERS)


def load_discharge_blockers():
    if os.path.exists(DISCHARGE_BLOCKERS_PATH):
        return pd.read_csv(DISCHARGE_BLOCKERS_PATH)
    return pd.DataFrame(columns=BLOCKER_COLUMNS)


def save_discharge_blockers(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(DISCHARGE_BLOCKERS_PATH, index=False)


def append_discharge_blocker(case_id: str, blocker: str, status: str = "open"):
    row = {
        "case_id": case_id,
        "blocker": blocker,
        "status": status,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    df = load_discharge_blockers()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_discharge_blockers(df)
    return row
