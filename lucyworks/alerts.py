import pandas as pd

ALERTS = [
    {"alert_type": "overdue_result", "severity": "high", "purpose": "review delay"},
    {"alert_type": "blocked_discharge", "severity": "high", "purpose": "discharge delay"},
    {"alert_type": "room_unavailable", "severity": "medium", "purpose": "resource conflict"},
    {"alert_type": "staffing_gap", "severity": "high", "purpose": "unsafe cover"},
    {"alert_type": "unacknowledged_handover", "severity": "high", "purpose": "ownership gap"},
    {"alert_type": "icu_pressure", "severity": "high", "purpose": "capacity strain"},
    {"alert_type": "imaging_backlog", "severity": "medium", "purpose": "queue pressure"},
    {"alert_type": "cleaning_overrun", "severity": "medium", "purpose": "turnover delay"},
]


def default_alert_table():
    return pd.DataFrame(ALERTS)
