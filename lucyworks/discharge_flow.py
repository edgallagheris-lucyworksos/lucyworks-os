import pandas as pd

DISCHARGE_BLOCKERS = [
    {"blocker": "meds_not_ready", "meaning": "medication outstanding"},
    {"blocker": "review_pending", "meaning": "clinical review not signed"},
    {"blocker": "owner_not_contacted", "meaning": "owner communication incomplete"},
    {"blocker": "notes_incomplete", "meaning": "documentation incomplete"},
]


def discharge_blocker_table():
    return pd.DataFrame(DISCHARGE_BLOCKERS)
