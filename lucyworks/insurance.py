import pandas as pd

INSURANCE_OBJECTS = [
    {"object": "insurer", "purpose": "insurer reference"},
    {"object": "policy", "purpose": "policy details linked to case"},
    {"object": "pre_auth", "purpose": "pre-authorisation status"},
    {"object": "claim", "purpose": "claim submission and status"},
    {"object": "estimate", "purpose": "cost estimate and shortfall"},
    {"object": "payment_log", "purpose": "payment and owner balance tracking"},
]


def insurance_model_table():
    return pd.DataFrame(INSURANCE_OBJECTS)
