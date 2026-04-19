import pandas as pd

MEDICATION_OBJECTS = [
    {"object": "medication_item", "purpose": "drug master item"},
    {"object": "stock_movement", "purpose": "inventory movement trail"},
    {"object": "drug_order", "purpose": "supplier ordering"},
    {"object": "controlled_drug_entry", "purpose": "controlled drug register"},
]


def medication_object_table():
    return pd.DataFrame(MEDICATION_OBJECTS)
