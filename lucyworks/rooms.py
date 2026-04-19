import os
import pandas as pd

ROOMS_PATH = "assets/rooms.csv"
ROOM_TYPES = [
    {"room_type": "consult", "purpose": "consult room"},
    {"room_type": "theatre", "purpose": "procedure room"},
    {"room_type": "prep", "purpose": "pre-procedure preparation"},
    {"room_type": "recovery", "purpose": "post-procedure recovery"},
    {"room_type": "icu_bay", "purpose": "critical care space"},
    {"room_type": "ward_kennel", "purpose": "inpatient ward space"},
    {"room_type": "isolation", "purpose": "isolation room"},
    {"room_type": "imaging_suite", "purpose": "scanner and imaging area"},
    {"room_type": "lab_area", "purpose": "lab work area"},
    {"room_type": "pharmacy_area", "purpose": "medication storage and dispense area"},
]
DEFAULT_ROOMS = [
    {"room_id": "RM001", "room_name": "Consult 1", "room_type": "consult", "department": "Front Of House", "state": "ready"},
    {"room_id": "RM002", "room_name": "Theatre 1", "room_type": "theatre", "department": "Surgery", "state": "ready"},
]


def room_type_table():
    return pd.DataFrame(ROOM_TYPES)


def load_rooms():
    if os.path.exists(ROOMS_PATH):
        return pd.read_csv(ROOMS_PATH)
    return pd.DataFrame(DEFAULT_ROOMS)


def room_state_summary():
    df = load_rooms()
    if df.empty or "state" not in df.columns:
        return pd.DataFrame(columns=["state", "count"])
    return df.groupby("state", as_index=False).size().rename(columns={"size": "count"})
