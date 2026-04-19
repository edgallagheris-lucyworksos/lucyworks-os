import pandas as pd

GOVERNANCE_OBJECTS = [
    {"object": "incident", "purpose": "operational or welfare incident"},
    {"object": "approval", "purpose": "sign-off and explicit approval"},
    {"object": "consent_record", "purpose": "consent checkpoint"},
    {"object": "exception_note", "purpose": "deviation from normal process"},
    {"object": "audit_log", "purpose": "durable audit trail"},
]


def governance_object_table():
    return pd.DataFrame(GOVERNANCE_OBJECTS)
