import os
from datetime import datetime

import pandas as pd

HANDOVERS_PATH = "exports/handovers.csv"
HANDOVER_FIELDS = [
    {"field": "from_owner", "meaning": "sending clinician or team"},
    {"field": "to_owner", "meaning": "receiving clinician or team"},
    {"field": "case_id", "meaning": "linked case"},
    {"field": "note", "meaning": "handover note"},
    {"field": "acknowledged", "meaning": "receiving owner has acknowledged"},
]
HANDOVER_COLUMNS = ["case_id", "from_owner", "to_owner", "note", "acknowledged", "created_at"]


def handover_schema_table():
    return pd.DataFrame(HANDOVER_FIELDS)


def load_handovers():
    if os.path.exists(HANDOVERS_PATH):
        return pd.read_csv(HANDOVERS_PATH)
    return pd.DataFrame(columns=HANDOVER_COLUMNS)


def save_handovers(df: pd.DataFrame):
    os.makedirs("exports", exist_ok=True)
    df.to_csv(HANDOVERS_PATH, index=False)


def append_handover(case_id: str, from_owner: str, to_owner: str, note: str, acknowledged: bool = False):
    row = {
        "case_id": case_id,
        "from_owner": from_owner,
        "to_owner": to_owner,
        "note": note,
        "acknowledged": acknowledged,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    df = load_handovers()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_handovers(df)
    return row
