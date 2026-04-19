import pandas as pd
from lucyworks.drugs import load_drug_database

PHARMACY_OBJECTS = [
    {"object": "drug_item", "purpose": "drug master item"},
    {"object": "formulation", "purpose": "dose form and strength"},
    {"object": "stock_batch", "purpose": "batch and expiry tracking"},
    {"object": "dispense_record", "purpose": "drug dispensed against case"},
    {"object": "prescription", "purpose": "prescribed medication record"},
    {"object": "controlled_drug_entry", "purpose": "controlled drug trail"},
    {"object": "supplier_order", "purpose": "pharmacy order to supplier"},
    {"object": "wastage_record", "purpose": "discarded or wasted stock"},
]


def pharmacy_model_table():
    return pd.DataFrame(PHARMACY_OBJECTS)


def pharmacy_stock_view():
    df = load_drug_database().copy()
    if df.empty:
        return df
    df["dispense_ready"] = True
    return df
