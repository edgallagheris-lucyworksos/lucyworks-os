import pandas as pd

INTAKE_STATUSES = [
    {"status": "received", "meaning": "intake logged"},
    {"status": "triaged", "meaning": "triage complete"},
    {"status": "booked", "meaning": "slot or review booked"},
    {"status": "arrived", "meaning": "patient arrived"},
    {"status": "handed_over", "meaning": "passed onward"},
]


def intake_status_table():
    return pd.DataFrame(INTAKE_STATUSES)
