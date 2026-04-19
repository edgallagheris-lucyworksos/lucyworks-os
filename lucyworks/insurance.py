import os
import pandas as pd

INSURERS_PATH = "assets/insurers.csv"
INSURANCE_OBJECTS = [
    {"object": "insurer", "purpose": "insurer reference"},
    {"object": "policy", "purpose": "policy details linked to case"},
    {"object": "pre_auth", "purpose": "pre-authorisation status"},
    {"object": "claim", "purpose": "claim submission and status"},
    {"object": "estimate", "purpose": "cost estimate and shortfall"},
    {"object": "payment_log", "purpose": "payment and owner balance tracking"},
]
DEFAULT_INSURERS = [
    {"insurer_code": "AGRIA", "name": "Agria", "pre_auth_required": True, "notes": "Referral cases often need pre-auth"},
    {"insurer_code": "PETPLAN", "name": "Petplan", "pre_auth_required": True, "notes": "Check policy excess and exclusions"},
]


def insurance_model_table():
    return pd.DataFrame(INSURANCE_OBJECTS)


def load_insurers():
    if os.path.exists(INSURERS_PATH):
        return pd.read_csv(INSURERS_PATH)
    return pd.DataFrame(DEFAULT_INSURERS)


def insurer_reference_table():
    return load_insurers()


def insurers_requiring_pre_auth():
    df = load_insurers()
    if "pre_auth_required" not in df.columns:
        return df.head(0)
    return df[df["pre_auth_required"].astype(str).str.lower().isin(["true", "1"])]
