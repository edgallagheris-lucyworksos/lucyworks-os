import pandas as pd

SPEECH_TARGETS = [
    {"target": "case_note", "purpose": "dictated note"},
    {"target": "handover_note", "purpose": "dictated handover"},
    {"target": "discharge_summary", "purpose": "dictated discharge draft"},
]


def speech_target_table():
    return pd.DataFrame(SPEECH_TARGETS)
